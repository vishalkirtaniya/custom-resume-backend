import os
from utils.logger import logger
 
BULLETS_SYSTEM = (
    "You are an expert technical resume writer. Write impactful bullet points "
    "using the Google XYZ formula: 'Accomplished [X] as measured by [Y], by doing [Z]'. "
    "Wrap important keywords, metrics, and technologies in LaTeX \\textbf{} for bold formatting."
)
 
 
def _build_bullets_prompt(project_title: str, project_details: str, matched_skills: list, keywords: list = None) -> str:
    skills_str = ", ".join(matched_skills)
    keywords_str = ", ".join(keywords) if keywords else skills_str
    return f"""
Project: {project_title}
Original Details: {project_details}
Target technologies/keywords to weave in naturally: {keywords_str}
 
Task: Write 3 bullet points for this project.
Constraints:
1. Output ONLY the LaTeX \\item lines — no preamble, no explanation, no markdown.
2. Each bullet must be ONE line max — 15 words or fewer after \\item.
3. ALWAYS wrap every metric/number/percentage in \\textbf{{}} — e.g. \\textbf{{40\\%}}, \\textbf{{100ms}}.
4. ALWAYS wrap the primary technology used in \\textbf{{}} — e.g. \\textbf{{FastAPI}}, \\textbf{{Redis}}.
5. Naturally include 1-2 of the target keywords per bullet — do NOT list them, weave them in.
6. Start each bullet with a strong past-tense action verb.
   Example: \\item Reduced API latency by \\textbf{{40\\%}} using \\textbf{{Redis}} caching layer.
"""
 
 
def _build_designation_prompt(job_description: str) -> str:
    return f"""
Read this job description and extract the exact job title/designation being hired for.
 
Job Description:
{job_description}
 
Rules:
1. Return ONLY the job title — nothing else. No punctuation, no explanation.
2. Keep it concise: 2-5 words max (e.g. "Python Developer", "Full Stack Engineer").
3. Use title case.
4. If unclear, return the most prominent technical role mentioned.
 
Examples of good output:
Python Developer
Full Stack Engineer
Machine Learning Engineer
"""
 
 
def _build_summary_prompt(original_summary: str, job_description: str, experience_highlights: str) -> str:
    return f"""
You are rewriting a resume summary to match a specific job description.
Keep the candidate's real experience — do NOT invent new skills or roles.
Only reframe and emphasize what already exists to align with what the job needs.
 
Candidate's current summary:
{original_summary}
 
Candidate's experience highlights:
{experience_highlights}
 
Job Description:
{job_description}
 
Rules:
1. Return ONLY the new summary — 2-3 sentences, plain text, no LaTeX, no bullet points.
2. Naturally incorporate 2-3 key skills or technologies the job emphasizes.
3. Wrap the most important keywords in \\textbf{{}} for LaTeX bold.
   Example: Experienced \\textbf{{Full Stack Engineer}} with expertise in \\textbf{{Python}} and \\textbf{{FastAPI}}.
4. Keep it factual — do not exaggerate or invent metrics.
5. Do not start with "I" — use third-person or impersonal phrasing.
"""
 
 
def _build_keywords_prompt(project_title: str, project_details: str, job_description: str) -> str:
    return f"""
Match a project to a job description. Extract 3-5 keywords from the job description
that are relevant to this specific project so a recruiter can quickly see the connection.
 
Project Title: {project_title}
Project Details: {project_details}
 
Job Description:
{job_description}
 
Rules:
1. Return ONLY a comma-separated list of keywords — nothing else.
2. Keywords must be technologies or skills relevant to BOTH the project and the job.
3. Keep each keyword short (1-3 words).
4. No explanation, no numbering, no bullet points.
 
Example output: REST APIs, Python, PostgreSQL, System Design
"""
 
 
# ══════════════════════════════════════════════════════════════════════════════
# GROQ — recommended (fastest, free: 14,400 req/day)
# pip install groq
# ══════════════════════════════════════════════════════════════════════════════
 
class GroqGeneratorService:
    def __init__(self, model_name: str = "llama-3.1-8b-instant"):
        self.model_name = model_name
        self.is_ready = self._check_model_status()
 
    def _check_model_status(self) -> bool:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not set.")
            return False
        try:
            from groq import Groq
            self._client = Groq(api_key=api_key)
            logger.info(f"Groq ready. Model: {self.model_name}")
            return True
        except ImportError:
            logger.error("groq not installed. Run: pip install groq")
            return False
        except Exception as e:
            logger.error(f"Groq init failed: {e}")
            return False
 
    def _call(self, system: str, prompt: str, max_tokens: int = 512) -> str:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
 
    def extract_designation(self, job_description: str) -> str:
        """Returns job title e.g. 'Python Developer' or '' on failure."""
        if not self.is_ready:
            return ""
        try:
            result = self._call(
                system="Extract job titles from job descriptions. Return only the title, nothing else.",
                prompt=_build_designation_prompt(job_description),
                max_tokens=20,
            )
            return result.replace('"', '').replace("'", '').strip().splitlines()[0]
        except Exception as e:
            logger.error(f"Groq designation extraction failed: {e}")
            return ""
 
    def generate_summary(self, original_summary: str, job_description: str, experience: list) -> str:
        """
        Rewrites the candidate's summary to align with the job description.
        Uses their real experience — does not fabricate anything.
        Returns plain LaTeX string with \\textbf{} on key terms.
        """
        if not self.is_ready:
            return original_summary  # fall back to original if service down
 
        # Flatten experience highlights into a short paragraph for context
        highlights = []
        for exp in experience:
            role = f"{exp.get('role', '')} at {exp.get('company', '')}"
            for h in (exp.get("highlights") or [])[:2]:  # max 2 per role
                highlights.append(f"{role}: {h}")
        experience_highlights = "\n".join(highlights[:6]) or "No experience details provided."
 
        try:
            return self._call(
                system="You rewrite resume summaries to align with job descriptions. Be factual and concise.",
                prompt=_build_summary_prompt(original_summary, job_description, experience_highlights),
                max_tokens=150,
            )
        except Exception as e:
            logger.error(f"Groq summary generation failed: {e}")
            return original_summary  # safe fallback
 
    def extract_project_keywords(self, project_title: str, project_details: str, job_description: str) -> list:
        """Returns list of keyword strings e.g. ['REST APIs', 'Python', 'PostgreSQL']"""
        if not self.is_ready:
            return []
        try:
            result = self._call(
                system="Match projects to job descriptions by extracting relevant keywords. Return only a comma-separated list.",
                prompt=_build_keywords_prompt(project_title, project_details, job_description),
                max_tokens=60,
            )
            return [kw.strip() for kw in result.split(",") if kw.strip()]
        except Exception as e:
            logger.error(f"Groq keyword extraction failed for '{project_title}': {e}")
            return []
 
    def generator_latex_bullets(self, project_title: str, project_details: str, matched_skills: list, keywords: list = None) -> str:
        """Generates 3 LaTeX \\item bullet points with keywords woven in naturally."""
        if not self.is_ready:
            return "% Error: Groq service not ready. Check GROQ_API_KEY."
        try:
            return self._call(
                system=BULLETS_SYSTEM,
                prompt=_build_bullets_prompt(project_title, project_details, matched_skills, keywords),
            )
        except Exception as e:
            logger.error(f"Groq bullets failed for '{project_title}': {e}")
            return f"% Failed to generate for {project_title}."