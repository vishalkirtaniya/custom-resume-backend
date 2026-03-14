import re
from utils.logger import logger


# Common English stop words — filters out noise from JD text
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "we", "you", "they", "it",
    "this", "that", "these", "those", "our", "your", "their", "its", "we",
    "as", "if", "so", "not", "no", "can", "about", "what", "which", "who",
    "how", "when", "where", "why", "all", "any", "both", "each", "more",
    "most", "other", "some", "such", "than", "then", "too", "very", "just",
    "also", "into", "over", "after", "work", "team", "role", "using",
    "strong", "good", "new", "use", "used", "well", "able", "help", "make",
    "within", "across", "ensure", "required", "including", "looking",
}


class ResumeMatcherService:
    """
    Matches resume skills and projects against a job description.
    Uses lightweight regex-based keyword extraction — no spaCy required.
    """

    def __init__(self, user_data: dict = None, skills_path="data/skills.json", experience_path="data/experience.json"):
        if user_data:
            # ── DB path: data comes from Supabase via SupabaseService.get_full_profile()
            self.skills_data     = user_data.get("skills", {})
            self.experience_data = self._shape_experience(user_data)
        else:
            # ── Legacy path: read from local JSON files (old CLI flow still works)
            self.skills_data     = self._load_json(skills_path)
            self.experience_data = self._load_json(experience_path)

    # ── Data shapers ──────────────────────────────────────────────────────────

    def _shape_experience(self, user_data: dict) -> dict:
        """
        Converts flat DB rows from Supabase into the shape match_experience() expects.
        """
        work_exp = []
        for exp in user_data.get("experience", []):
            work_exp.append({
                "company":       exp.get("company", ""),
                "role":          exp.get("role", ""),
                "location":      exp.get("location", ""),
                "stack":         exp.get("stack") or [],
                "highlights":    exp.get("highlights") or [],
                "start_date":    exp.get("start_date", ""),
                "end_date":      exp.get("end_date", ""),
                "is_internship": exp.get("is_internship", False),
            })

        projects = []
        for p in user_data.get("projects", []):
            projects.append({
                "title":       p.get("title", ""),
                "description": p.get("description", ""),
                "stack":       p.get("stack") or [],
                "metrics":     p.get("metrics") or [],
                "link":        p.get("link", ""),
            })

        education = []
        for e in user_data.get("education", []):
            education.append({
                "institution":     e.get("institution", ""),
                "degree":          e.get("degree", ""),
                "field_of_study":  e.get("field_of_study", ""),
                "graduation_year": e.get("graduation_year", ""),
                "status":          e.get("status", ""),
            })

        return {
            "work_experience":    work_exp,
            "technical_projects": projects,
            "education":          education,
        }

    def _load_json(self, path):
        import json
        try:
            with open(path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found at {path}")
            return {}

    # ── Keyword extraction ────────────────────────────────────────────────────

    def extract_keywords_from_jd(self, jd_text: str) -> set:
        """
        Extracts meaningful keywords from a job description using regex.
        Handles tech terms like C++, Node.js, .NET, GraphQL, CI/CD correctly —
        spaCy would sometimes mangle these during lemmatization.
        """
        # Tokenize — keep alphanumeric plus common tech punctuation (. + # /)
        tokens = re.findall(r'\b[a-zA-Z][a-zA-Z0-9+#./]*\b', jd_text.lower())

        keywords = set()
        for token in tokens:
            if token not in STOP_WORDS and len(token) > 1:
                # Simple suffix stripping for common plurals/verb forms
                # e.g. "apis" → "api", "databases" → "database", "working" → "work"
                lemma = token
                if token.endswith("ing") and len(token) > 5:
                    lemma = token[:-3]          # working → work
                elif token.endswith("ies") and len(token) > 4:
                    lemma = token[:-3] + "y"    # libraries → library
                elif token.endswith("es") and len(token) > 4:
                    lemma = token[:-2]          # databases → databas (close enough)
                elif token.endswith("s") and len(token) > 3:
                    lemma = token[:-1]          # apis → api, tools → tool

                keywords.add(token)             # original
                keywords.add(lemma)             # lemmatized form

        return keywords

    # ── Matching methods ──────────────────────────────────────────────────────

    def match_skills(self, jd_text: str) -> dict:
        """Returns dict of { category: [matched skills] } from the JD."""
        jd_keywords = self.extract_keywords_from_jd(jd_text)
        logger.info(f"JD Keywords: {jd_keywords}")

        matched = {}
        for category, skill_list in self.skills_data.items():
            matches = [s for s in skill_list if s.lower() in jd_keywords]
            if matches:
                matched[category] = matches

        logger.info(f"Matched: {matched}")
        return matched

    def match_experience(self, matched_skills: dict) -> list:
        """Returns projects whose stack overlaps with matched skills."""
        relevant = []
        all_matches = [s.lower() for sublist in matched_skills.values() for s in sublist]

        for project in self.experience_data.get("technical_projects", []):
            stack = [s.lower() for s in project.get("stack", [])]
            if any(skill in stack for skill in all_matches):
                relevant.append(project)

        return relevant