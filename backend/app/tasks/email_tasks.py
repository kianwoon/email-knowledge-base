import logging
from celery import Task
from msal import ConfidentialClientApplication # Assuming msal_app is configured elsewhere or recreated
import asyncio # Import asyncio
from asyncio import TimeoutError # Explicit import for clarity
from fastapi.concurrency import run_in_threadpool # Import run_in_threadpool

# Qdrant Imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.celery_app import celery_app
# from ..core.config import settings # OLD Relative import (wrong path)
from ..config import settings # CORRECTED Relative import
from app.db.session import SessionLocal # Assuming SessionLocal is available for creating new sessions
from app.crud import user_crud # Assuming user_crud is available
from app.services.outlook import OutlookService # Assuming OutlookService is available
from app.models.email import EmailFilter # Import EmailFilter
# Import the new service function and Qdrant client getter
from app.services.knowledge_service import _process_and_store_emails
from app.db.qdrant_client import get_qdrant_client, ensure_collection_exists
# Add other necessary imports for email processing (e.g., Qdrant client, analysis service)
# from app.services.qdrant_service import QdrantService
# from app.services.analysis_service import AnalysisService
# --- Import for manual encryption/decryption --- 
from app.utils.security import decrypt_token
# --- End Import ---


logger = logging.getLogger(__name__)

# Helper function to get a new MSAL app instance if needed within the task
# Or potentially pass the configured msal_app if safe and feasible
def get_msal_app():
    return ConfidentialClientApplication(
        settings.MS_CLIENT_ID,
        authority=settings.MS_AUTHORITY,
        client_credential=settings.MS_CLIENT_SECRET,
        # token_cache=... # Consider token caching strategy for workers if applicable
    )

class EmailProcessingTask(Task):
    """Custom Task class for potential shared logic or state"""
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f'{self.name}[{task_id}] failed: {exc}', exc_info=exc)
        # Add custom failure logic if needed (e.g., notification, specific cleanup)
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f'{self.name}[{task_id}] succeeded. Result: {retval}')
        # Add custom success logic if needed
        super().on_success(retval, task_id, args, kwargs)

# Task Name reflects new location
@celery_app.task(bind=True, base=EmailProcessingTask, name='tasks.email_tasks.process_user_emails') 
def process_user_emails(self: Task, user_id: str, filter_criteria_dict: dict):
    """
    Celery task to fetch, process (generate tags), and store emails based on criteria.
    Uses OutlookService for fetching, OpenAI for tagging, and Qdrant for storage.
    Args:
        user_id (str): The email address of the user whose emails are being processed.
        filter_criteria_dict (dict): A dictionary representation of EmailFilter criteria.
    Returns:
        dict: A summary dictionary indicating success or failure.
    """
    task_id = self.request.id
    logger.info(f"Starting email processing task {task_id} for user '{user_id}' with filter: {filter_criteria_dict}")
    self.update_state(state='STARTED', meta={'user_email': user_id, 'progress': 0, 'status': 'Initializing...'})
    
    db = None # Initialize db to None
    try:
        # --- Parse Filter Criteria ---
        try:
            filter_criteria = EmailFilter(**filter_criteria_dict)
            logger.debug(f"Task {task_id}: Parsed filter criteria: {filter_criteria.model_dump_json()}")
        except Exception as parse_error:
            logger.error(f"Task {task_id}: Failed to parse filter_criteria_dict: {parse_error}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Invalid filter criteria provided'})
            return {'status': 'ERROR', 'message': 'Invalid filter criteria'}

        # --- Get DB Session & Qdrant Client ---
        db = SessionLocal()
        if not db:
             raise Exception("Could not create database session.")
        logger.debug(f"Task {task_id}: Database session created.")

        qdrant_client = get_qdrant_client() # Get Qdrant client instance
        if not qdrant_client:
            raise Exception("Could not create Qdrant client.")
        logger.debug(f"Task {task_id}: Qdrant client obtained.")

        # --- Retrieve User and Refresh Token ---
        db_user = user_crud.get_user_full_instance(db=db, email=user_id)

        if not db_user:
            logger.error(f"Task {task_id}: User with email '{user_id}' not found in database.")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'User not found'})
            return {'status': 'ERROR', 'message': 'User not found'}

        logger.debug(f"Task {task_id}: Found user {db_user.email}.")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 5, 'status': 'User found'})

        encrypted_token_bytes = db_user.ms_refresh_token
        if not encrypted_token_bytes:
            logger.error(f"Task {task_id}: No encrypted refresh token found in DB for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Missing refresh token data'})
            return {'status': 'ERROR', 'message': 'Refresh token data not found'}

        refresh_token = decrypt_token(encrypted_token_bytes)
        if not refresh_token:
            logger.error(f"Task {task_id}: Failed to decrypt refresh token for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Failed to decrypt token'})
            return {'status': 'ERROR', 'message': 'Could not decrypt session token'}
        
        logger.debug(f"Task {task_id}: Refresh token retrieved and decrypted for user {db_user.email}.")

        # --- Acquire New Access Token ---
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 10, 'status': 'Acquiring access token...'})
        msal_instance = get_msal_app()

        reserved_scopes = {'openid', 'profile', 'offline_access'}
        required_scopes = [s for s in settings.MS_SCOPE if s not in reserved_scopes]
        logger.debug(f"Task {task_id}: Requesting access token with filtered scopes: {required_scopes}")

        token_result = None
        try:
            # Define the blocking function call
            refresh_call = lambda: msal_instance.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=required_scopes
            )

            # --- Define an async function to run the call with timeout ---
            async def run_refresh_with_timeout():
                logger.info(f"Task {task_id}: Attempting token refresh in threadpool for user {db_user.email}.")
                # Use a timeout value from settings, defaulting if not present
                timeout_seconds = getattr(settings, 'MS_REFRESH_TIMEOUT_SECONDS', 30)
                result = await asyncio.wait_for(
                    run_in_threadpool(refresh_call),
                    timeout=timeout_seconds
                )
                logger.info(f"Task {task_id}: Token refresh call completed successfully for user {db_user.email}.")
                return result

            # --- Run the async function using asyncio.run() ---
            token_result = asyncio.run(run_refresh_with_timeout())
            # --- End wrapped call ---

        except TimeoutError: # Catch timeout specifically
            timeout_seconds = getattr(settings, 'MS_REFRESH_TIMEOUT_SECONDS', 30)
            logger.error(f"Task {task_id}: Timeout ({timeout_seconds}s) occurred while acquiring access token for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Token acquisition timed out'})
            return {'status': 'ERROR', 'message': 'Token acquisition timed out'}
        except Exception as refresh_exc: # Catch any other errors during run_refresh_with_timeout
            logger.error(f"Task {task_id}: Error during token refresh execution for user {db_user.email}: {refresh_exc}", exc_info=True)
            # Attempt to extract MSAL-specific error if possible (structure might vary)
            error_desc = str(refresh_exc)
            if hasattr(refresh_exc, 'error_response') and isinstance(refresh_exc.error_response, dict):
                 error_desc = refresh_exc.error_response.get('error_description', str(refresh_exc))
                 logger.error(f"Task {task_id}: MSAL error during refresh: {error_desc}")

            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Token acquisition failed: {error_desc}'})
            return {'status': 'ERROR', 'message': f'Token acquisition failed: {error_desc}'}


        # Check the result dictionary *after* successful execution (no timeout/exception)
        if not token_result or "error" in token_result:
            error_desc = token_result.get('error_description', 'Unknown token acquisition error') if token_result else "No result from refresh call"
            logger.error(f"Task {task_id}: Failed to acquire access token (MSAL error) for user {db_user.email}. Error: {token_result.get('error') if token_result else 'N/A'}, Desc: {error_desc}")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Token acquisition failed (MSAL): {error_desc}'})
            return {'status': 'ERROR', 'message': f'Token acquisition failed (MSAL): {error_desc}'}

        access_token = token_result.get('access_token')
        if not access_token:
             logger.error(f"Task {task_id}: Acquired token result does not contain an access token for user {db_user.email}.")
             self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Acquired token missing access_token key'})
             return {'status': 'ERROR', 'message': 'Internal error during token acquisition'}

        logger.info(f"Task {task_id}: Successfully acquired new access token for user {db_user.email}.")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 15, 'status': 'Access token acquired'})

        # --- Initialize Outlook Service ---
        outlook_service = OutlookService(access_token)

        # --- Define Target Qdrant Collection --- 
        sanitized_email = user_id.replace('@', '_').replace('.', '_')
        target_collection_name = f"{sanitized_email}_email_knowledge"
        logger.info(f"Task {task_id}: Target Qdrant collection: {target_collection_name}")

        # --- Ensure Target Collection Exists --- 
        try:
            logger.info(f"Task {task_id}: Ensuring collection '{target_collection_name}' exists.")
            qdrant_client.create_collection(
                collection_name=target_collection_name,
                vectors_config=models.VectorParams(
                    size=settings.EMBEDDING_DIMENSION, # Use settings
                    distance=models.Distance.COSINE  # Use settings or default
                )
            )
            logger.info(f"Task {task_id}: Collection '{target_collection_name}' created.")
        except UnexpectedResponse as e:
            if e.status_code == 409 or (e.status_code == 400 and "already exists" in str(e.content).lower()):
                logger.warning(f"Task {task_id}: Collection '{target_collection_name}' already exists.")
                pass 
            else: raise e
        except Exception as create_err:
             logger.error(f"Task {task_id}: Failed to ensure/create collection '{target_collection_name}': {create_err}", exc_info=True)
             raise Exception(f"Failed to create target collection: {create_err}")

        # --- Perform Email Processing using Knowledge Service --- 
        logger.info(f"Task {task_id}: Calling knowledge service to process emails for user {user_id}")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 20, 'status': 'Processing emails...'})

        def update_progress(state, meta):
            full_meta = {'user_email': user_id, **meta}
            self.update_state(state=state, meta=full_meta)
        
        processed_count, failed_count, points_to_upsert = asyncio.run(
            _process_and_store_emails(
                operation_id=task_id,
                owner_email=user_id,
                filter_criteria=filter_criteria,
                outlook_service=outlook_service,
                qdrant_client=qdrant_client, 
                target_collection_name=target_collection_name, 
                update_state_func=update_progress 
            )
        )

        logger.info(f"Task {task_id}: Email processing completed. Processed: {processed_count}, Failed: {failed_count}. Points to upsert: {len(points_to_upsert)}")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 90, 'status': 'Upserting data...'})

        # --- Upsert Points to Qdrant ---
        if points_to_upsert:
            try:
                qdrant_client.upsert(
                    collection_name=target_collection_name,
                    points=points_to_upsert,
                    wait=True # Wait for operation to complete
                )
                logger.info(f"Task {task_id}: Successfully upserted {len(points_to_upsert)} points to {target_collection_name}.")
            except Exception as upsert_err:
                logger.error(f"Task {task_id}: Failed to upsert points to Qdrant: {upsert_err}", exc_info=True)
                # Decide how to handle upsert failure (e.g., mark task as failed?)
                # For now, log error and potentially update status
                failed_count += len(points_to_upsert) # Count these as failed
                self.update_state(state='FAILURE', meta={'user_email': user_id, 'progress': 95, 'status': f'Failed to save data: {upsert_err}'})
                return {'status': 'ERROR', 'message': f'Failed final save: {upsert_err}', 'processed': processed_count, 'failed': failed_count}

        # --- Task Completion ---
        final_status = 'SUCCESS' if failed_count == 0 else 'PARTIAL_FAILURE'
        final_message = f"Completed. Processed: {processed_count}, Failed: {failed_count}."
        result = {'status': final_status, 'message': final_message, 'processed': processed_count, 'failed': failed_count}
        logger.info(f"Task {task_id}: {final_message}")
        
        self.update_state(state='SUCCESS' if final_status == 'SUCCESS' else 'FAILURE', meta={
            'user_email': user_id, 
            'progress': 100, 
            'status': 'Completed' if final_status == 'SUCCESS' else 'Completed with errors', 
            'result': result
        })
        return result

    except Exception as e:
        logger.exception(f"Task {task_id}: An unexpected error occurred during email processing for user '{user_id}': {e}")
        failure_meta = {'user_email': user_id, 'status': f'Failed: {str(e)}'}
        try:
             self.update_state(state='FAILURE', meta=failure_meta)
        except Exception as state_update_err:
             logger.error(f"Task {task_id}: Could not update task state to FAILURE after exception: {state_update_err}")
        raise e

    finally:
        if db:
            try:
                db.close()
                logger.debug(f"Task {task_id}: Database session closed successfully.")
            except Exception as close_err:
                logger.error(f"Task {task_id}: Error closing database session: {close_err}", exc_info=True)
        # Qdrant client closing might not be needed if managed elsewhere 