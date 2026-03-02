import json
import signal
import sys
from services.resume_matcher_service import ResumeMatcherService
from services.ollama_generator_service import OllamaGeneratorService
from utils.logger import logger

shutdown_requested = False # This flag will tell our loop if it's time to stop

def signal_handler(sig, frame):
    global shutdown_requested
    print("\n\n🛑 Shutdown signal received! Finishing Current task...")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)

def run_automation(job_description):
    global shutdown_requested
    logger.info("___ Starting Resume Automation ___")

    matcher = ResumeMatcherService()
    generator = OllamaGeneratorService()

    if not matcher.skills_data or not matcher.experience_data:
        logger.warning("Error: Essential data files (skills/experience) are missing or empty")
        return None
    
    if not generator.is_ready:
        logger.warning("Warning: LLM is offline.")
        return None
    
    logger.info("Analyzing Job Description")
    matched_skills = matcher.match_skills(job_description)
    if not matched_skills:
        logger.warning("STOPPING: No matching skills found between your profile and job description.")
        return None

    relevant_skills = matcher.match_experience(matched_skills)

    if not relevant_skills:
        logger.warning("STOPPING: No matching relevant skills found between your profile and job description.")
        return None

    final_resume_data = {
        "skills_to_list": matched_skills,
        "project_bullets": []
    }

    # --- The Loop with a Shutdown Check ---
    for project in relevant_skills:
        if shutdown_requested:
            logger.info("Operation cancelled by user. Saving Progress...")
            break

        logger.info(f"Generating bullets for: {project['title']}...")

        try:
            bullets = generator.generator_latex_bullets(
                project_title=project['title'],
                project_details=project.get('description') or project.get('details', ""),
                matched_skills=matched_skills.get("Backend", []) + matched_skills.get("Language", [])
            )

            final_resume_data["project_bullets"].append({
                "title": project['title'],
                "bullets": bullets
            })
        
        except Exception as e:
            logger.error(f"Error generating {project['title']}: {e}")

    with open("data/generated_content.json", "w") as f:
        json.dump(final_resume_data, f, indent=2)

    if shutdown_requested:
        logger.info("Partial data saved. Exiting safely.")
        sys.exit(0)

    logger.info("\n Success! All Bullets generated.")
    print(f"Final Resume Data: {final_resume_data}")

    return final_resume_data

if __name__ == "__main__":
    target_jd = """
    About the job
Job Ad

What if you could use your technology skills to develop a product that impacts the way communities’ hospitals, homes, sports stadiums, and schools across the world are built? Construction impacts the lives of nearly everyone in the world, and yet it’s also one of the world’s least digitized industries, not to mention one of the most dangerous. That’s why we’re looking for a talented Staff Full-Stack Software Engineer to join Procore’s journey to revolutionize a historically underserved industry.

As a Software Engineer 1 at Procore, you’re given the unique opportunity to partner intimately with our customer base, translating their fundamental needs into technological SaaS solutions. Backed by the might of our teams, we’ll provide you with the tools and resources needed to achieve extraordinary results that render a significant impact extending beyond the boundaries of traditional engineering roles. We’re looking for someone to join our team immediately.

What you’ll do:

Collaborate with senior engineers and product managers to design, develop, and test software solutions.
Write clean, efficient, and maintainable code following best practices and coding standards.
Participate in code reviews to ensure code quality and provide constructive feedback to peers.
Troubleshoot and debug issues reported by customers or internal teams, and implement solutions in a timely manner.
Stay updated on emerging technologies and industry trends, and actively contribute to technical discussions and knowledge sharing within the team.
Assist in documentation efforts including technical specifications, user manuals, and other relevant documentation.
Contribute to continuous improvement initiatives by identifying opportunities for process optimization and automation.

What we're looking for: 

Bachelor's Degree in Engineering/Technology
Strong understanding of computer science fundamentals including data structures, algorithms, and object-oriented programming.
Proficiency in at least one programming language (e.g., Java, Python, C++, etc.).
Excellent problem-solving skills and attention to detail.
Ability to work effectively both independently and collaboratively in a team environment.
Strong communication skills with the ability to convey technical concepts clearly and concisely.
Eagerness to learn new technologies and adapt to a dynamic work environment.
    """
    run_automation(target_jd)