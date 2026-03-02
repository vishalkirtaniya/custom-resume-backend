import spacy
import json

nlp = spacy.load("en_core_web_md")

class ResumeMatcherService():

    def __init__(self, skills_path="data/skills.json", experience_path="data/experience.json"):
        self.nlp = spacy.load("en_core_web_md")
        self.skills_data = self._load_json(skills_path)
        self.experience_data = self._load_json(experience_path)

    def _load_json(self, path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: File not found at {path}")
            return {}

    # method takes a messy job description and clean it up
    def extract_keywords_from_jd(self, jd_text):
        doc = self.nlp(jd_text.lower())

        # 1. token.lemma_: This gets the root word (e.g "running" becomes "run").
        # 2. token.pos_: in ["NOUN", "PROPN"], it only keeps proper nouns
        # 3. { ... }: This puts them in a SET, which automatically removes duplicates.
        keywords = {token.lemma_ for token in doc if token.pos_ in ["NOUN", "PROPN"]}
        return keywords
    
    def match_skills(self, jd_text):
        jd_keywords = self.extract_keywords_from_jd(jd_text)
        matched_skills = {}

        for category, skill_list in self.skills_data.items():
            matches = [skill for skill in skill_list if skill.lower() in jd_keywords]
            if matches:
                matched_skills[category] = matches

        return matched_skills
    
    def match_experience(self, matched_skills):
        relevant_projects = []
        all_matches = [skill.lower() for sublist in matched_skills.values() for skill in sublist]

        for project in self.experience_data.get("technical_projects", []):
            project_stack = [s.lower() for s in project.get('stack', [])]
            if any(skill in project_stack for skill in all_matches):
                relevant_projects.append(project)

        return relevant_projects
    

if __name__ == "__main__":
    matcher_service = ResumeMatcherService()

    sample_jd = """
    We need a Software Engineer with Python experience. 
    Expertise in gRPC and real-time data pipelines is required.
    Knowledge of AI prompts and Next.js is a plus.
    """
   
    found_skills = matcher_service.match_skills(sample_jd)
    found_projects = matcher_service.match_experience(found_skills)

    if found_skills:
       print("Matched Skills:")
       print(json.dumps(found_skills, indent=2))

    if found_projects:
        print("Matched Relevant Projects to highlight: ")
        for p in found_projects:
            print(f"- {p['title']} (stack: {", ".join(p['stack'])})")

