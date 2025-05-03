import os
# TEMP: Check if module is loaded
print("--- DEBUG: Loading celery_app.py module ---")

from celery import Celery
# TEMP: Comment out settings import for now
# from app.config import settings 
import logging

# TEMP: Hardcode broker URL for basic test (ensure env var is still primary method)
# This is ONLY to see if the Celery object itself can be created without relying on settings module initially
# Replace with your actual broker URL if different, but ideally keep reading from env
broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis-queue.email-knowledge-base-2.internal:6379/0")
backend_url = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis-queue.email-knowledge-base-2.internal:6379/0")

logger = logging.getLogger(__name__)

logger.info(f"TEMP DEBUG: Initializing Celery with Broker: {broker_url}")
logger.info(f"TEMP DEBUG: Initializing Celery with Backend: {backend_url}")

if not broker_url:
    logger.error("CELERY_BROKER_URL is not set. Celery cannot start.")
    raise ValueError("CELERY_BROKER_URL environment variable not set.")

# Define the Celery application instance
# TEMP: Comment out include list
celery_app = Celery(
    'app',
    broker=broker_url,
    backend=backend_url,
    # include=[
    #     'app.tasks.email_tasks', 
    #     'app.tasks.sharepoint_tasks', 
    #     'app.tasks.s3_tasks', 
    #     'app.tasks.azure_tasks',
    #     'app.tasks.export_tasks', 
    #     'app.tasks.outlook_sync',
    #     'app.tasks.email_parser',
    #     'app.tasks.knowledge_updater',
    #     'app.tasks.sharepoint_sync' 
    # ]
)

# TEMP: Check if app object is created
print(f"--- DEBUG: Celery app object created. Broker: {broker_url} ---")

# TEMP: Comment out conf updates
# celery_app.conf.update(
#     task_serializer='json',
#     accept_content=['json'],
#     result_serializer='json',
#     timezone='UTC',
#     enable_utc=True,
#     broker_connection_retry_on_startup=True,
#     beat_schedule={
#         'outlook-sync-dispatcher': {
#             'task': 'tasks.outlook_sync.dispatch_sync_tasks',
#             'schedule': 60.0, 
#         },
#     },
# )

if __name__ == '__main__':
    logger.info("Starting Celery worker from __main__ context.")
    celery_app.start() 