import os
from jinja2 import Environment, FileSystemLoader
from utils.logger import logger
import subprocess
import shutil

class LatexBuilderService:
    def __init__(self, template_dir='templates', template_name='resume_template.tex'):
        # Configure Jinja2 with unique markers for each type of action
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            block_start_string='((*',    # Used for: ((* for project in projects *))
            block_end_string='*))',      # Used for: ((* endfor *))
            variable_start_string='((',  # Used for: (( project.title ))
            variable_end_string='))',
            comment_start_string='((=',  # Unique comment marker
            comment_end_string='=))'
        )
        self.template_name = template_name

    def build_tex(self, resume_data, output_path='output/tailored_resume.tex', shutdown_flag=False):
        """
        Injects data into the template with a check for shutdown signals.
        If shutdown_flag is True, it stops before writing to disk.
        """
        # 1. Graceful Shutdown Check
        if shutdown_flag:
            logger.warning("LatexBuilderService: Shutdown detected. Aborting build to prevent corrupted file.")
            return None

        try:
            template = self.env.get_template(self.template_name)


            formatted_skills = []
            skills_dict = resume_data.get('skills_to_list', {})
            for category, items in skills_dict.items():
                # Join list of skills into a comma-separated string
                skills_str = ", ".join(items) if isinstance(items, list) else items
                formatted_skills.append({
                    "category": category,
                    "content": skills_str
                })
                
            # 2. Fallback Logic: Prepare Project Data
            final_projects = []
            for project in resume_data.get('project_bullets', []):
                # If the AI bullets are missing or failed, we use a fallback message 
                # or original data so the LaTeX doesn't crash.
                bullet_content = project.get('bullets')
                if not bullet_content or "% Error" in bullet_content:
                    logger.warning(f"Using fallback for project: {project['title']}")
                    bullet_content = "\\item Original project details from portfolio[cite: 4, 13]."

                final_projects.append({
                    "title": project['title'],
                    "bullets": bullet_content
                })

            # 3. Render Template
            rendered_tex = template.render(
                skills=resume_data.get('skills_to_list', {}),
                projects=final_projects
            )

            # 4. Final Verification before Disk I/O
            if shutdown_flag:
                return None

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                f.write(rendered_tex)
            
            logger.info(f"Successfully generated tailored LaTeX file: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to build LaTeX: {e}")
            return None
        
    def compile_pdf(self, tex_path):
        """
        Compiles the .tex file into a PDF using pdflatex.
        """
        if not tex_path or not os.path.exists(tex_path):
            logger.error("Cannot compile: .tex file does not exist.")
            return None

        output_dir = os.path.dirname(tex_path)
        file_name = os.path.basename(tex_path)
        
        logger.info(f"Compiling {file_name} into PDF...")

        try:
            # Run pdflatex twice to ensure references and layout are correct
            # -interaction=nonstopmode prevents the terminal from hanging on errors
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', f'-output-directory={output_dir}', tex_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"LaTeX Compilation Error: {result.stdout}")
                return None

            pdf_path = tex_path.replace('.tex', '.pdf')
            logger.info(f"✅ Success! PDF created at: {pdf_path}")
            
            self._cleanup_temp_files(output_dir)
            return pdf_path

        except FileNotFoundError:
            logger.error("pdflatex command not found. Install it using: sudo dnf install texlive-scheme-basic")
            return None

    def _cleanup_temp_files(self, directory):
        """Removes auxiliary files like .log, .aux, and .out."""
        extensions = ['.aux', '.log', '.out', '.toc']
        for file in os.listdir(directory):
            if any(file.endswith(ext) for ext in extensions):
                os.remove(os.path.join(directory, file))
        logger.info("Temporary LaTeX files cleaned up.")

    def render_as_string(self, resume_data: dict, user_data: dict) -> str:
        """
        Renders the LaTeX template as a string using all user data from the DB.

        Args:
            resume_data: { skills_to_list: {...}, project_bullets: [...] }
                         — output from the matcher + generator pipeline
            user_data:   full dict from SupabaseService.get_full_profile()
                         { profile: {...}, experience: [...], education: [...], ... }
        """
        template = self.env.get_template(self.template_name)

        # Format project bullets: merge AI-generated bullets into project rows
        # so the template has one unified `projects` list to loop over
        project_bullets_map = {
            p["title"]: p.get("bullets", "")
            for p in resume_data.get("project_bullets", [])
        }

        projects_with_bullets = []
        for p in user_data.get("projects", []):
            projects_with_bullets.append({
                **p,
                # Attach AI bullets if generated for this project; else fall back
                # to description/metrics so the section is never empty
                "bullets": project_bullets_map.get(p["title"], ""),
            })

        return template.render(
            profile    = user_data.get("profile", {}),
            skills     = resume_data.get("skills_to_list", {}),
            experience = user_data.get("experience", []),
            projects   = projects_with_bullets,
            education  = user_data.get("education", []),
        )