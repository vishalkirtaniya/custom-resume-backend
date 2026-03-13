import os
from fastapi import FastAPI, Depends, HTTPException, Header, Response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import List, Optional
import tempfile, subprocess, os

# Services
from services.supabase_service import SupabaseService
from services.resume_matcher_service import ResumeMatcherService
from services.cloud_generator_service import GroqGeneratorService
from services.latex_builder_service import LatexBuilderService
from utils.cache import cache
from utils.logger import logger

# All new routes (auth, profile, experience, skills, etc.)
from routes import router

load_dotenv()

# ── Schemas used ONLY in this file (do not duplicate in routes.py) ────────────

class ExperienceSchema(BaseModel):
    company: str
    role: str
    location: Optional[str]
    start_date: str
    end_date: str
    stack: List[str]
    highlights: List[str]

class ProfileSchema(BaseModel):
    full_name: str
    phone: str
    location: str
    summary: str
    experience: List[ExperienceSchema]

class ResumeRequest(BaseModel):
    job_description: str

class TexToPdfRequest(BaseModel):
    tex: str

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Resume Autobot Engine")

origins = [
    "http://localhost:3000",
    "https://your-resume-app.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    user = SupabaseService.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user

@app.get("/")
async def health_check():
    return {
        "status": "online",
        "supabase_connected": bool(os.getenv("SUPABASE_URL")),
        "ollama_ready": True,
    }

@app.post("/generate")
async def generate_resume(request: ResumeRequest, user=Depends(get_current_user)):
    try:
        db = SupabaseService(user_id=user.id)
        user_data = db.get_full_profile()
 
        matcher   = ResumeMatcherService(user_data=user_data)
        generator = GroqGeneratorService()
        builder   = LatexBuilderService()
 
        matched_skills    = matcher.match_skills(request.job_description)
        relevant_projects = matcher.match_experience(matched_skills)
 
        designation = generator.extract_designation(request.job_description)
 
        tailored_summary = generator.generate_summary(
            original_summary = user_data.get("profile", {}).get("summary", ""),
            job_description  = request.job_description,
            experience       = user_data.get("experience", []),
        )
 
        final_projects_data = []
        for project in relevant_projects:
            # Extract keywords first so they can be woven into bullets
            keywords = generator.extract_project_keywords(
                project_title   = project["title"],
                project_details = project.get("description", ""),
                job_description = request.job_description,
            )
            # Pass keywords into bullets so they appear naturally in the text
            bullets = generator.generator_latex_bullets(
                project_title   = project["title"],
                project_details = project.get("description", ""),
                matched_skills  = matched_skills.get("Backend", []) + matched_skills.get("Languages", []),
                keywords        = keywords,
            )
            final_projects_data.append({
                "title":   project["title"],
                "bullets": bullets,
            })
 
        final_resume_payload = {
            "skills_to_list":   matched_skills,
            "project_bullets":  final_projects_data,
            "designation":      designation,
            "tailored_summary": tailored_summary,
        }
 
        tex_code = builder.render_as_string(final_resume_payload, user_data)
 
        return {
            "status":         "success",
            "tex":            tex_code,
            "matched_skills": matched_skills,
            "designation":    designation,
        }
 
    except Exception as e:
        print(f"Error during generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync-profile")
async def sync_profile(data: ProfileSchema, user=Depends(get_current_user)):
    db = SupabaseService(user_id=user.id)
    try:
        db.supabase.table("profiles").upsert({
            "id": user.id,
            "full_name": data.full_name,
            "phone": data.phone,
            "location": data.location,
            "summary": data.summary,
        }).execute()

        db.supabase.table("experience").delete().eq("user_id", user.id).execute()

        for exp in data.experience:
            db.supabase.table("experience").insert({
                "user_id": user.id,
                "company": exp.company,
                "role": exp.role,
                "stack": exp.stack,
                "highlights": exp.highlights,
                "start_date": exp.start_date,
                "end_date": exp.end_date,
            }).execute()
        
        cache.invalidate(user.id, "profile")
        cache.invalidate(user.id, "experience")

        return {"status": "success", "message": "Profile and Experience synced to Supabase"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/compile-pdf")
async def compile_pdf(request: TexToPdfRequest, user=Depends(get_current_user)):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = os.path.join(tmpdir, "resume.tex")
            pdf_path = os.path.join(tmpdir, "resume.pdf")

            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(request.tex)

            # Run twice — second pass fixes any cross-references
            for _ in range(2):
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, tex_path],
                    capture_output=True, text=True, timeout=30
                )

            if not os.path.exists(pdf_path):
                # Return the compiler log so you can debug LaTeX errors
                raise HTTPException(
                    status_code=422,
                    detail=f"pdflatex failed:\n{result.stdout[-1000:]}"
                )

            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=tailored_resume.pdf"}
            )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="pdflatex timed out after 30s")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)