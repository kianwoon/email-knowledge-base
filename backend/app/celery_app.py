import os
# TEMP: Check if module is loaded
# print("--- DEBUG: Loading celery_app.py module ---") # REMOVE DEBUG PRINT

from celery import Celery
# Restore settings import
from app.config import settings 
import logging

# # TEMP: Hardcode broker URL for basic test (ensure env var is still primary method)
# # This is ONLY to see if the Celery object itself can be created without relying on settings module initially
# # Replace with your actual broker URL if different, but ideally keep reading from env
# broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis-queue.email-knowledge-base-2.internal:6379/0")
# backend_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis-queue.email-knowledge-base-2.internal:6379/0")

logger = logging.getLogger(__name__)


# Get broker and backend URLs from settings
broker_url = settings.CELERY_BROKER_URL
backend_url = settings.CELERY_RESULT_BACKEND

logger.info(f"Celery App Definition: Using Broker URL: {broker_url}")
logger.info(f"Celery App Definition: Using Backend URL: {backend_url}")

if not broker_url:
    logger.error("CELERY_BROKER_URL is not set. Celery cannot start.")
    # Optional: raise error or exit if critical
    # raise ValueError("CELERY_BROKER_URL environment variable not set.")
if not backend_url:
    logger.warning("CELERY_RESULT_BACKEND is not set. Task results may not be stored reliably.")

# Define the include list separately for logging
include_modules = [
    'app.tasks.email_tasks',
    'app.tasks.sharepoint_tasks',
    'app.tasks.s3_tasks',
    'app.tasks.azure_tasks',
    'app.tasks.export_tasks',
    'app.tasks.outlook_sync'
]
logger.info(f"Celery App Definition: Including modules: {include_modules}")

# Define the Celery application instance
celery_app = Celery(
    'app',  # Main name matches the directory
    broker=broker_url,
    backend=backend_url,
    include=include_modules
)

# Log registered tasks *after* Celery app object might have processed includes
# Note: Task discovery often happens lazily, this might not show all tasks immediately
try:
    logger.info(f"Celery App Definition: Initial registered tasks (may be incomplete): {list(celery_app.tasks.keys())}")
except Exception as e:
    logger.error(f"Celery App Definition: Error listing initial tasks: {e}")

# Restore Celery configuration updates
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    # Restore beat schedule configuration
    beat_schedule={
        'outlook-sync-dispatcher': {
            'task': 'tasks.outlook_sync.dispatch_sync_tasks',
            # Use getattr for safer access to settings, assuming uppercase env var
            'schedule': float(getattr(settings, 'OUTLOOK_SYNC_DISPATCH_INTERVAL_SECONDS', 900.0)), # Default 15 mins
        },
        # Add other beat schedules here if needed
    },
)

# Log the final effective beat schedule
logger.info(f"Celery App Definition: Effective beat_schedule: {celery_app.conf.beat_schedule}")

if __name__ == '__main__':
    # This part is typically only for running worker directly, not usually hit in FastAPI context
    logger.info("Starting Celery worker from __main__ context (celery_app.py).")
    celery_app.start() 
# --- End Original Code Reinstated --- 