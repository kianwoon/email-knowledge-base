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

# # TEMP: Comment out settings import for now
# # from app.config import settings 
# import logging

# # TEMP: Hardcode broker URL for basic test (ensure env var is still primary method)
# # This is ONLY to see if the Celery object itself can be created without relying on settings module initially
# # Replace with your actual broker URL if different, but ideally keep reading from env
# broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis-queue.email-knowledge-base-2.internal:6379/0")
# backend_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis-queue.email-knowledge-base-2.internal:6379/0")

# logger = logging.getLogger(__name__)

# # logger.info(f"TEMP DEBUG: Initializing Celery with Broker: {broker_url}")
# # logger.info(f"TEMP DEBUG: Initializing Celery with Backend: {backend_url}")

# # if not broker_url:
# #     logger.error("CELERY_BROKER_URL is not set. Celery cannot start.")
# #     raise ValueError("CELERY_BROKER_URL environment variable not set.")

# # Define the Celery application instance
# # TEMP: Comment out include list
# celery_app = Celery(
#     'app',
#     broker=broker_url,
#     backend=backend_url,
#     # include=[
#     #     'app.tasks.email_tasks', 
#     #     'app.tasks.sharepoint_tasks', 
#     #     'app.tasks.s3_tasks', 
#     #     'app.tasks.azure_tasks',
#     #     'app.tasks.export_tasks', 
#     #     'app.tasks.outlook_sync',
#     #     'app.tasks.email_parser',
#     #     'app.tasks.knowledge_updater',
#     #     'app.tasks.sharepoint_sync' 
#     # ]
# )

# # TEMP: Check if app object is created
# print(f"--- DEBUG: Celery app object created. Broker: {broker_url} ---") # REMOVE DEBUG PRINT

# # TEMP: Comment out conf updates
# # celery_app.conf.update(
# #     task_serializer='json',
# #     accept_content=['json'],
# #     result_serializer='json',
# #     timezone='UTC',
# #     enable_utc=True,
# #     broker_connection_retry_on_startup=True,
# #     beat_schedule={
# #         'outlook-sync-dispatcher': {
# #             'task': 'tasks.outlook_sync.dispatch_sync_tasks',
# #             'schedule': 60.0, 
# #         },
# #     },
# # )

# # if __name__ == '__main__':
# #     logger.info("Starting Celery worker from __main__ context.")
# #     celery_app.start()

# --- Start Original Code Reinstated ---

# Ensure logging is configured early if needed by settings or tasks
# logger = logging.getLogger(__name__)

# Get broker and backend URLs from settings
broker_url = settings.CELERY_BROKER_URL
backend_url = settings.CELERY_RESULT_BACKEND

logger.info(f"Initializing Celery with Broker: {broker_url}")
logger.info(f"Initializing Celery with Backend: {backend_url}")

if not broker_url:
    logger.error("CELERY_BROKER_URL is not set. Celery cannot start.")
    raise ValueError("CELERY_BROKER_URL environment variable not set.")
if not backend_url:
    logger.warning("CELERY_RESULT_BACKEND is not set. Task results will not be stored.")

# Define the Celery application instance
celery_app = Celery(
    'app', # Main name matches the directory
    broker=broker_url,
    backend=backend_url,
    # Restore task includes
    include=[
        'app.tasks.email_tasks', 
        'app.tasks.sharepoint_tasks', 
        'app.tasks.s3_tasks', 
        'app.tasks.azure_tasks',
        'app.tasks.export_tasks', 
        'app.tasks.outlook_sync',
        'app.tasks.email_parser',
        'app.tasks.knowledge_updater',
        'app.tasks.sharepoint_sync' 
    ]
)

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
            'schedule': settings.outlook_sync_dispatch_interval_seconds,
        },
        # Add other beat schedules here if needed
    },
)

if __name__ == '__main__':
    logger.info("Starting Celery worker from __main__ context.")
    celery_app.start() 
# --- End Original Code Reinstated --- 