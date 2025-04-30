import os
from celery import Celery
from app.config import settings
import logging

# Ensure logging is configured before Celery imports modules
# (Assuming you have a logger setup, e.g., in app.utils.logger)
# from app.utils.logger import setup_logging
# setup_logging()

logger = logging.getLogger(__name__)

# Ensure environment variables are loaded (config should handle this)
# from dotenv import load_dotenv
# load_dotenv()

# Get broker and backend URLs from settings
broker_url = settings.CELERY_BROKER_URL
backend_url = settings.CELERY_RESULT_BACKEND

logger.info(f"Initializing Celery with Broker: {broker_url}")
logger.info(f"Initializing Celery with Backend: {backend_url}")

if not broker_url:
    logger.error("CELERY_BROKER_URL is not set. Celery cannot start.")
    # Optionally raise an exception or exit
    raise ValueError("CELERY_BROKER_URL environment variable not set.")
if not backend_url:
    logger.warning("CELERY_RESULT_BACKEND is not set. Task results will not be stored.")
    # Depending on requirements, you might want to raise an error here too.

# Define the Celery application instance
# We use 'app' as the main name, which corresponds to the directory structure
celery_app = Celery(
    'app', # Main name of the application module package
    broker=broker_url,
    backend=backend_url,
    include=[
        'app.tasks.email_tasks', 
        'app.tasks.sharepoint_tasks', 
        'app.tasks.s3_tasks', 
        'app.tasks.azure_tasks',
        'app.tasks.export_tasks' # Add the new export tasks module
    ]
)

# Optional configuration settings
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Allow json content
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Example: Set task time limits
    # task_time_limit=300, # soft time limit (seconds)
    # task_soft_time_limit=240, # hard time limit (seconds)
    broker_connection_retry_on_startup=True,
)

# Autodiscover tasks from the 'include' list
# celery_app.autodiscover_tasks() # Not strictly needed if using 'include'

if __name__ == '__main__':
    # This allows running the worker directly using:
    # python -m app.celery_app worker --loglevel=info
    # (Adjust the command based on your project structure if needed)
    logger.info("Starting Celery worker from __main__ context.")
    celery_app.start() 