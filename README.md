<div align="center">

# ⚡ Resume Autobot — Backend

**FastAPI backend powering AI resume tailoring, LaTeX generation, and PDF compilation**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat-square&logo=supabase)](https://supabase.com/)
[![Groq](https://img.shields.io/badge/Groq-LLM-F55036?style=flat-square)](https://groq.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)

🚀 **[Live API](http://43.205.211.233:8000/health)**  •  **[Frontend →](https://github.com/vishalkirtaniya/custom-resume-frontend)**

</div>

---

## What is Resume Autobot?

Resume Autobot is a full-stack AI-powered resume builder. This backend handles authentication, profile storage, skill matching against job descriptions, LLM-powered LaTeX generation, and PDF compilation via `pdflatex` — all exposed as a REST API consumed by the Next.js frontend.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Language | Python 3.11 |
| Database | Supabase (PostgreSQL) |
| Auth | Supabase JWT |
| LLM | Groq (`llama-3.1-8b-instant`) / Gemini fallback |
| PDF | pdflatex (TeX Live minimal) |
| Templates | Jinja2 (custom LaTeX delimiters) |
| Cache | In-memory TTL cache |
| Rate limiting | slowapi |
| Deployment | Docker + AWS EC2 |

---

## Project Structure

```
resume_autobot/
├── app.py                          # FastAPI app, CORS, /health, /generate, /compile-pdf
├── routes.py                       # Auth + all profile endpoints
├── services/
│   ├── supabase_service.py         # DB client, token verification, auth methods
│   ├── cloud_generator_service.py  # Groq + Gemini LLM services
│   ├── latex_builder_service.py    # Jinja2 LaTeX renderer + bold_metrics filter
│   └── resume_matcher_service.py   # Keyword-based skill + project matching
├── templates/
│   └── resume_template.tex         # Jinja2 LaTeX template
├── utils/
│   ├── cache.py                    # In-memory TTL cache
│   └── logger.py                   # Structured logger
├── requirements.txt
├── .dockerfile
└── .dockerignore
```

---

## Database Schema

```sql
profiles       (id, full_name, email, phone, location, website_url, linkedin_url, github_url, summary)
experience     (id, user_id → profiles, company, role, location, start_date, end_date, is_internship, stack[], highlights[])
education      (id, user_id → profiles, institution, degree, field_of_study, graduation_year, status)
projects       (id, user_id → profiles, title, description, stack[], metrics[], link)
skills         (id, user_id → profiles, category, skill_name)
certifications (id, user_id → profiles, name, issuer, issue_date, expiry_date, credential_id, credential_url)
```

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create new account |
| POST | `/auth/login` | Sign in, returns JWT tokens |
| POST | `/auth/refresh` | Refresh access token |

### Profile (Bearer token required)
| Method | Endpoint | Description |
|---|---|---|
| GET / PATCH | `/profile` | Get or update personal info |
| GET / POST | `/profile/skills` | Get or replace skills |
| GET / POST | `/profile/experience` | Get or replace experience |
| GET / POST | `/profile/projects` | Get or replace projects |
| GET / POST | `/profile/education` | Get or replace education |
| GET / POST | `/profile/certifications` | Get or replace certifications |

### Generation (Bearer token required)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/generate` | Match skills, generate LaTeX resume |
| POST | `/compile-pdf` | Compile `.tex` string to PDF |
| GET | `/health` | Health check |

### Example: Generate Resume
```bash
curl -X POST http://43.205.211.233:8000/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"job_description": "We are looking for a Python Developer..."}'
```

Response:
```json
{
  "status": "success",
  "tex": "\\documentclass[11pt,a4paper]{article}...",
  "matched_skills": { "Backend": ["Python", "FastAPI"], "Tools": ["Docker"] },
  "designation": "Python Developer"
}
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project
- A [Groq](https://console.groq.com) API key (free)
- `pdflatex` installed (for local PDF compilation)

### Local Development

```bash
# Clone the repo
git clone https://github.com/vishalkirtaniya/custom-resume-backend.git
cd custom-resume-backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
```

Edit `.env`:
```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
CACHE_TIME=300
```

```bash
# Run the server
uvicorn app:app --reload --port 8000
```

API available at [http://localhost:8000](http://localhost:8000)
Interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Docker

### Build and run standalone

```bash
docker build -f .dockerfile -t resume-backend .
docker run -d -p 8000:8000 --env-file .env resume-backend
```

### With Docker Compose (recommended)

Run frontend + backend together from the parent directory:

```bash
# Parent folder structure:
# resume/
# ├── docker-compose.yml
# ├── .env
# ├── resume_autobot/     ← this repo
# └── resume-frontend/    ← frontend repo

docker compose up --build -d
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (bypasses RLS) |
| `GROQ_API_KEY` | Groq API key for LLM generation |
| `GEMINI_API_KEY` | Google Gemini API key (fallback) |
| `CACHE_TIME` | Profile cache TTL in seconds (default: 300) |

---

## How the AI Generation Works

1. **Skill matching** — extracts keywords from the JD using regex, matches against your saved skills by category
2. **Designation extraction** — Groq LLM reads the JD and returns the exact job title (e.g. "Python Developer")
3. **Summary tailoring** — Groq rewrites your profile summary to align with the JD, keeping only real experience
4. **Keyword extraction** — for each relevant project, Groq extracts 3–5 JD keywords that match the project
5. **Bullet generation** — Groq writes 3 LaTeX `\item` bullets per project using the Google XYZ formula with `\textbf{}` on metrics and tech
6. **LaTeX rendering** — Jinja2 renders the full `.tex` file with all sections, with `bold_metrics` filter auto-bolding numbers
7. **PDF compilation** — `pdflatex` compiles the `.tex` to PDF in a temp directory, returned as binary response

---

## Deployment

Deployed on **AWS EC2 t3.small** in **ap-south-1** region.

```bash
# SSH into your server
ssh -i your-key.pem ubuntu@YOUR_SERVER_IP

# Clone and deploy
git clone https://github.com/vishalkirtaniya/custom-resume-backend.git
cd custom-resume-backend

docker build -f .dockerfile -t resume-backend .
docker run -d -p 8000:8000 --env-file .env \
  --restart unless-stopped \
  --name resume-backend \
  resume-backend
```

Live API: **[http://43.205.211.233:8000/health](http://43.205.211.233:8000/health)**

---

## Related

- **Frontend repo:** [custom-resume-frontend](https://github.com/vishalkirtaniya/custom-resume-frontend)

---

<div align="center">
Made by <a href="https://github.com/vishalkirtaniya">Vishal Kirtaniya</a>
</div>