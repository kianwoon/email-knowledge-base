import logging
from celery import shared_task, Task
from msal import ConfidentialClientApplication # Assuming msal_app is configured elsewhere or recreated
import asyncio # Import asyncio

# Qdrant Imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.celery_app import celery_app
from app.config import settings
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


@celery_app.task(bind=True, base=EmailProcessingTask, name='app.tasks.process_user_emails')
def process_user_emails(self: Task, user_id: str, filter_criteria_dict: dict):
    """
    Celery task to fetch, analyze, and store emails for a given user based on criteria.

    Args:
        user_id (str): The email address of the user whose emails need processing.
        filter_criteria_dict (dict): A dictionary representing the EmailFilter criteria.
    """
    task_id = self.request.id
    # Use user_id (email) in log messages
    logger.info(f"Starting email processing task {task_id} for user: {user_id}")
    self.update_state(state='STARTED', meta={'user_email': user_id, 'progress': 0, 'status': 'Initializing...'})

    db = None
    qdrant_client = None
    processed_count = 0
    failed_count = 0
    
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
        # User lookup is by email (user_id is the email)
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

        # --- Decrypt Refresh Token (Manual Encryption) ---
        refresh_token = decrypt_token(encrypted_token_bytes)
        if not refresh_token:
            logger.error(f"Task {task_id}: Failed to decrypt refresh token for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Failed to decrypt token'})
            return {'status': 'ERROR', 'message': 'Could not decrypt session token'}
        # --- End Decrypt --- 

        logger.debug(f"Task {task_id}: Refresh token retrieved and decrypted for user {db_user.email}.")

        # --- Acquire New Access Token --- 
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 10, 'status': 'Acquiring access token...'})
        msal_instance = get_msal_app()
        
        # Filter out reserved OIDC scopes before requesting token
        reserved_scopes = {'openid', 'profile', 'offline_access'}
        required_scopes = [s for s in settings.MS_SCOPE if s not in reserved_scopes]
        logger.debug(f"Task {task_id}: Requesting access token with filtered scopes: {required_scopes}")
        
        token_result = msal_instance.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=required_scopes # Use the filtered list
        )

        if "error" in token_result:
            error_desc = token_result.get('error_description', 'Unknown token acquisition error')
            logger.error(f"Task {task_id}: Failed to acquire access token for user {db_user.email}. Error: {token_result.get('error')}, Desc: {error_desc}")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Token acquisition failed: {error_desc}'})
            return {'status': 'ERROR', 'message': f'Token acquisition failed: {error_desc}'}

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
        # Construct the user-specific collection name for embeddings
        sanitized_email = user_id.replace('@', '_').replace('.', '_')
        target_collection_name = f"{sanitized_email}_email_knowledge" # Reverted to original/correct name
        logger.info(f"Task {task_id}: Target Qdrant collection: {target_collection_name}")

        # --- Ensure Target Collection Exists --- 
        # Wrap ensure_collection_exists in run_sync if it's async, or make it sync
        # Assuming ensure_collection_exists is synchronous or adaptable
        try:
            logger.info(f"Task {task_id}: Ensuring collection '{target_collection_name}' exists.")
            # Directly call ensure_collection_exists (assuming it handles sync/async appropriately or is sync)
            # If it's async, it needs to be run within the asyncio event loop managed below.
            qdrant_client.create_collection(
                collection_name=target_collection_name,
                vectors_config=models.VectorParams(
                    size=settings.QDRANT_VECTOR_SIZE,
                    distance=settings.QDRANT_DISTANCE_METRIC
                )
            )
            logger.info(f"Task {task_id}: Collection '{target_collection_name}' created.")
        except UnexpectedResponse as e:
            if e.status_code == 409: # Conflict - already exists
                logger.warning(f"Task {task_id}: Collection '{target_collection_name}' already exists.")
                pass # Collection exists, proceed
            else:
                raise e # Re-raise other unexpected Qdrant errors
        except Exception as create_err:
             logger.error(f"Task {task_id}: Failed to ensure/create collection '{target_collection_name}': {create_err}", exc_info=True)
             raise Exception(f"Failed to create target collection: {create_err}") # Make it a fatal task error

        # --- Perform Email Processing using Knowledge Service --- 
        logger.info(f"Task {task_id}: Calling knowledge service to process emails for user {user_id}")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 20, 'status': 'Processing emails...'})

        # Define the update_state callback function for the service
        def update_progress(state, meta):
            # Merge task-specific info with progress info
            full_meta = {'user_email': user_id, **meta}
            self.update_state(state=state, meta=full_meta)
        
        # Run the async service function within an event loop
        # Revert to receiving PointStructs
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

        # --- Upsert PointStructs to Qdrant --- 
        if points_to_upsert:
            try:
                logger.info(f"Task {task_id}: Upserting {len(points_to_upsert)} points (with placeholder vectors) to Qdrant collection '{target_collection_name}'.")
                # Use points argument again
                qdrant_client.upsert(
                    collection_name=target_collection_name,
                    points=points_to_upsert, # Pass list of PointStructs
                    wait=True
                )
                logger.info(f"Task {task_id}: Successfully upserted {len(points_to_upsert)} points.")
            except Exception as upsert_err:
                failed_count += len(points_to_upsert) # Count these as failed if upsert fails
                logger.error(f"Task {task_id}: Failed to upsert {len(points_to_upsert)} points to Qdrant: {upsert_err}", exc_info=True)
                self.update_state(state='FAILURE', meta={'user_email': user_id, 'progress': 95, 'status': f'Qdrant upsert failed: {upsert_err}'})
                return {'status': 'ERROR', 'message': f'Failed to save processed data: {upsert_err}'}
        else:
            logger.warning(f"Task {task_id}: No points were generated by the processing service.")

        # --- Final Result --- 
        final_status = 'SUCCESS' if failed_count == 0 else 'PARTIAL_SUCCESS'
        final_message = f"Email processing finished. Processed: {processed_count}, Failed: {failed_count}."
        result = {
            'status': final_status,
            'message': final_message,
            'processed_count': processed_count,
            'failed_count': failed_count
        }
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
        # Reraise the exception so Celery knows the task failed
        raise e

    finally:
        # --- Close DB Session & Qdrant Client ---
        if db:
            db.close()
            logger.debug(f"Task {task_id}: Database session closed.")
        # Qdrant client closing might depend on how it's managed (e.g., context manager)
        # If get_qdrant_client provides a singleton or pooled client, closing might not be needed here.
        # if qdrant_client and hasattr(qdrant_client, 'close'):
        #     qdrant_client.close()
        #     logger.debug(f"Task {task_id}: Qdrant client closed.") 