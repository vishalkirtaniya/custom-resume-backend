"""
resume_autobot/routes.py
Drop-in additions to main.py — paste these AFTER your existing routes.
DO NOT modify your existing /, /generate, /sync-profile endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from services.supabase_service import SupabaseService
from utils.cache import cache

router = APIRouter()


# ── Shared auth dependency (mirrors your existing get_current_user) ─────────

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    user = SupabaseService.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

class RegisterSchema(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class LoginSchema(BaseModel):
    email: EmailStr
    password: str


@router.post("/auth/register", status_code=201)
async def register_user(data: RegisterSchema):
    """
    Creates a Supabase auth user, then inserts a profiles row
    with only the NOT NULL fields (full_name + email).
    All other profile fields are filled later via PATCH /profile.
    """
    try:
        result = SupabaseService.sign_up(email=data.email, password=data.password)
        user = result.user

        if not user:
            raise HTTPException(status_code=400, detail="Signup failed — no user returned")

        # Insert minimal profile row (only NOT NULL columns)
        client = SupabaseService.get_client()
        client.table("profiles").insert({
            "id": user.id,
            "full_name": data.full_name,
            "email": data.email,
        }).execute()

        return {"status": "success", "user_id": user.id}

    except Exception as e:
        error_msg = str(e)
        # Supabase throws this when email is already registered
        if "already registered" in error_msg or "duplicate" in error_msg.lower():
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/auth/login")
async def login_user(data: LoginSchema):
    """
    Authenticates via Supabase and returns an access_token.
    The frontend stores this and sends it as: Authorization: Bearer <token>
    """
    try:
        result = SupabaseService.sign_in(email=data.email, password=data.password)
        session = result.session

        if not session:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "status": "success",
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE — optional fields updated after signup
# ══════════════════════════════════════════════════════════════════════════════

class ProfileUpdateSchema(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    website_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    summary: Optional[str] = None


@router.patch("/profile")
async def update_profile(data: ProfileUpdateSchema, user=Depends(get_current_user)):
    """
    Partial update of the profiles row. Only provided fields are written.
    Email and id are never updated here.
    """
    # Strip None values so we only PATCH what was actually sent
    payload = {k: v for k, v in data.model_dump().items() if v is not None}

    if not payload:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    try:
        client = SupabaseService.get_client()
        client.table("profiles").update(payload).eq("id", user.id).execute()
        cache.invalidate(user.id, "profile")
        return {"status": "success", "updated_fields": list(payload.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile")
async def get_profile(user=Depends(get_current_user)):
    """Returns the current user's full profiles row."""
    cached = cache.get(user.id, "profile")
    if cached is not None:
        return {
            "status": "success",
            "profile": cached,
            "cached": True
        }
    try:
        client = SupabaseService.get_client()
        result = client.table("profiles").select("*").eq("id", user.id).single().execute()
        cache.set(user.id, "profile", result.data)
        return {"status": "success", "profile": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# EXPERIENCE
# ══════════════════════════════════════════════════════════════════════════════

class ExperienceItemSchema(BaseModel):
    company: str
    role: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_internship: Optional[bool] = False
    stack: Optional[List[str]] = []
    highlights: Optional[List[str]] = []


@router.get("/profile/experience")
async def get_experience(user=Depends(get_current_user)):
    cached = cache.get(user.id, "experience")
    if cached is not None:
        return {
            "status": "success",
            "items": cached,
            "cached": True
        }
    try:
        client = SupabaseService.get_client()
        result = client.table("experience").select("*").eq("user_id", user.id).execute()
        cache.set(user.id, "experience", result.data)
        return {"status": "success", "items": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile/experience")
async def sync_experience(items: List[ExperienceItemSchema], user=Depends(get_current_user)):
    """Full replace: deletes all existing experience rows for user, inserts fresh."""
    try:
        client = SupabaseService.get_client()
        client.table("experience").delete().eq("user_id", user.id).execute()
        if items:
            rows = [{"user_id": user.id, **item.model_dump()} for item in items]
            client.table("experience").insert(rows).execute()
        cache.invalidate(user.id, "experience")
        return {"status": "success", "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# EDUCATION
# ══════════════════════════════════════════════════════════════════════════════

class EducationItemSchema(BaseModel):
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    graduation_year: Optional[str] = None
    status: Optional[str] = None

@router.get("/profile/education")
async def get_education(user=Depends(get_current_user)):
    cached = cache.get(user.id, "education")
    if cached is not None:
        return {
            "status": "success",
            "items": cached,
            "cached": True
        }
    try:
        client = SupabaseService.get_client()
        result = client.table("education").select("*").eq("user_id", user.id).execute()
        cache.set(user.id, "education", result.data)
        return {"status": "success", "items": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile/education")
async def sync_education(items: List[EducationItemSchema], user=Depends(get_current_user)):
    """Full replace for education rows."""
    try:
        client = SupabaseService.get_client()
        client.table("education").delete().eq("user_id", user.id).execute()
        if items:
            rows = [{"user_id": user.id, **item.model_dump()} for item in items]
            client.table("education").insert(rows).execute()
        cache.invalidate(user.id, "education")
        return {"status": "success", "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SKILLS
# ══════════════════════════════════════════════════════════════════════════════

class SkillItemSchema(BaseModel):
    category: str
    skill_name: str

@router.get("/profile/skills")
async def get_skills(user=Depends(get_current_user)):
    cached = cache.get(user.id, "skills")
    if cached is not None:
        return {"status": "success", "items": cached, "cached": True}
    try:
        client = SupabaseService.get_client()
        result = client.table("skills").select("*").eq("user_id", user.id).execute()
        cache.set(user.id, "skills", result.data)
        return {"status": "success", "items": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile/skills")
async def sync_skills(items: List[SkillItemSchema], user=Depends(get_current_user)):
    """Full replace for skills rows."""
    try:
        client = SupabaseService.get_client()
        client.table("skills").delete().eq("user_id", user.id).execute()
        if items:
            rows = [{"user_id": user.id, **item.model_dump()} for item in items]
            client.table("skills").insert(rows).execute()

        cache.invalidate(user.id, "skills")
        return {"status": "success", "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

class ProjectItemSchema(BaseModel):
    title: str
    description: Optional[str] = None
    stack: Optional[List[str]] = []
    metrics: Optional[List[str]] = []
    link: Optional[str] = None

@router.get("/profile/projects")
async def get_projects(user=Depends(get_current_user)):
    cached = cache.get(user.id, "projects")
    if cached is not None:
        return {
            "status": "success",
            "items": cached,
            "cached": True
        }
    try:
        client = SupabaseService.get_client()
        result = client.table("projects").select("*").eq("user_id", user.id).execute()
        cache.set(user.id, "projects", result.data)
        return {"status": "success", "items": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile/projects")
async def sync_projects(items: List[ProjectItemSchema], user=Depends(get_current_user)):
    """Full replace for projects rows."""
    try:
        client = SupabaseService.get_client()
        client.table("projects").delete().eq("user_id", user.id).execute()
        if items:
            rows = [{"user_id": user.id, **item.model_dump()} for item in items]
            client.table("projects").insert(rows).execute()
        cache.invalidate(user.id, "projects")
        return {"status": "success", "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# CERTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

class CertificationItemSchema(BaseModel):
    name: str
    issuer: str
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None

@router.get("/profile/certifications")
async def get_certifications(user=Depends(get_current_user)):
    cached = cache.get(user.id, "certifications")
    if cached is not None:
        return {
            "status": "success",
            "items": cached,
            "cached": True
        }
    try:
        client = SupabaseService.get_client()
        result = client.table("certifications").select("*").eq("user_id", user.id).execute()
        cache.set(user.id, "certifications", result.data)
        return {"status": "success", "items": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/profile/certifications")
async def sync_certifications(items: List[CertificationItemSchema], user=Depends(get_current_user)):
    """Full replace for certifications rows."""
    try:
        client = SupabaseService.get_client()
        client.table("certifications").delete().eq("user_id", user.id).execute()
        if items:
            rows = [{"user_id": user.id, **item.model_dump()} for item in items]
            client.table("certifications").insert(rows).execute()
        cache.invalidate(user.id, "certifications")
        return {"status": "success", "count": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))