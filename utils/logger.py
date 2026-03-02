import logging
import sys

def setup_logger(name="resume_autobot"):
    """
    Configures a centralized logger for the entire application.
    """
    logger = logging.getLogger(name)
    
    # If the logger is already configured, don't add more handlers
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Create a format for the logs
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')

        # Console Handler (Prints to your Fedora terminal)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File Handler (Optional: Saves logs to a file for later debugging)
        file_handler = logging.FileHandler("app.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

# Create a singleton instance that can be imported anywhere
logger = setup_logger()