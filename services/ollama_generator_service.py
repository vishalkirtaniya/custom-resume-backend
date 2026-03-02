import ollama
from utils.logger import logger

class OllamaGeneratorService():
    #  Service to generate professional, ATS-optimized resme content using a local LLM

    def __init__(self, model_name="qwen2.5-coder:3b"):
        self.model_name = model_name
        self.is_ready = self._check_model_status()

    def _check_model_status(self):
        """Verifies if the model is available. Returns True or False."""
        try:
            # 1. Get the response from Ollama
            response = ollama.list()

            # 2. Extract the list of models
            models_list = response.models if hasattr(response, 'models') else []

            if not models_list:
                logger.warning(f"No models found in Ollama. Pull it using: ollama pull {self.model_name}")
                return False

            # 3. Check for the model name using the '.model' attribute
            for m in models_list:
                # Based on your log, the attribute is called 'model' (e.g., m.model)
                if m.model.startswith(self.model_name):
                    logger.info(f"Ollama model {self.model_name} is ready.")
                    return True
            
            logger.warning(f"Model '{self.model_name}' not found in your local list.")
            return False
            
        except Exception as e:
            logger.error(f"Could not connect to Ollama: {e}")
            return False

    def generator_latex_bullets(self, project_title, project_details, matched_skills):
        # this is will 3-4 high impact bullet points for a specific project.
        if not self.is_ready:
            return "% Error: Service not ready. Check Ollama Connection"
        
        try:
            skills_str = ", ".join(matched_skills) # converts list to single string for prompt

            system_prompt = (
                "You are an expert technical resume writer. Your goal is to write "
                "impactful bullet points using Google XYZ formula: "
                "'Accomplished [X] as measured by [Y], by doing [Z]'."
            )

            user_prompt = f"""
            Project: {project_title}
            Original Details: {project_details}
            Target Keywords to include: {skills_str}

            Task: Write 4 bullet points that highlights the larget keywords.
            Constraints:
            1. Output ONLY the LaTeX code for the bullets (e.g., \\item ...).
            2. Focus on quantifiable metrics (e.g., improved by 20%, 100% uptime).
            3. Use professional, action-oriented language.
            4. Do not include any introductory text or explanation
            """

            # Call the local model
            response = ollama.generate(
                model=self.model_name,
                system=system_prompt,
                prompt=user_prompt
            )

            return response['response'].strip()
        
        except ollama.ResponseError as e:
            logger.error(f"Ollama API Error: {e}")
            return f"% Failed to generate for {project_title} due to API error."
        except Exception as e:
            logger.error(f"% Unexpected error occurred for {project_title}.")
        