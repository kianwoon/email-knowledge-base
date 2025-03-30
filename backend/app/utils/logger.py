import logging
import sys
from app.config import settings

# Configure logging
def setup_logger():
    """Set up application logger"""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    # Create logger
    logger = logging.getLogger("email_knowledge_app")
    logger.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

# Create logger instance
logger = setup_logger()
