import os
from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import List, Optional

# Services
from services.supabase_service import SupabaseService
from services.resume_matcher_service import ResumeMatcherService
from services.ollama_generator_service import OllamaGeneratorService
from services.latex_builder_service import LatexBuilderService
from utils.cache import cache

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

        matcher = ResumeMatcherService(user_data=user_data)
        generator = OllamaGeneratorService()
        builder = LatexBuilderService()

        matched_skills = matcher.match_skills(request.job_description)
        print(f"Matched_skills: {matched_skills}")
        relevant_projects = matcher.match_experience(matched_skills)

        final_projects_data = []
        for project in relevant_projects:
            bullets = generator.generator_latex_bullets(
                project_title=project["title"],
                project_details=project.get("description", ""),
                matched_skills=matched_skills.get("Backend", []) + matched_skills.get("Languages", []),
            )
            final_projects_data.append({"title": project["title"], "bullets": bullets})

        final_resume_payload = {
            "skills_to_list": matched_skills,
            "project_bullets": final_projects_data,
        }

        tex_code = builder.render_as_string(final_resume_payload, user_data)

        return {"status": "success", "tex": tex_code, "matched_skills": matched_skills}

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)