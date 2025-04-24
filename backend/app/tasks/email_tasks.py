import logging
from celery import Task
from msal import ConfidentialClientApplication # Assuming msal_app is configured elsewhere or recreated
import asyncio # Import asyncio
from asyncio import TimeoutError # Explicit import for clarity
from fastapi.concurrency import run_in_threadpool # Import run_in_threadpool

# Remove Qdrant Imports
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.exceptions import UnexpectedResponse
# Import Milvus
from pymilvus import MilvusClient

from app.celery_app import celery_app
# from ..core.config import settings # OLD Relative import (wrong path)
from ..config import settings # CORRECTED Relative import
from app.db.session import SessionLocal # Assuming SessionLocal is available for creating new sessions
from app.crud import user_crud, crud_ingestion_job # Assuming user_crud and crud_ingestion_job are available
from app.services.outlook import OutlookService # Assuming OutlookService is available
from app.models.email import EmailFilter # Import EmailFilter
# Import the new service function and Milvus client getter
from app.services.knowledge_service import _process_and_store_emails
from app.db.milvus_client import get_milvus_client, ensure_collection_exists
# Add other necessary imports for email processing (e.g., Milvus client, analysis service)
# from app.services.qdrant_service import QdrantService
# from app.services.analysis_service import AnalysisService
# --- Import for manual encryption/decryption --- 
from app.utils.security import decrypt_token
# --- End Import ---
from app.schemas.ingestion_job import IngestionJobCreate # Import schema


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
    Uses OutlookService for fetching, OpenAI for tagging, and Milvus for storage.
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

        # --- Get DB Session & Milvus Client ---
        db = SessionLocal()
        if not db:
             raise Exception("Could not create database session.")
        logger.debug(f"Task {task_id}: Database session created.")

        milvus_client = get_milvus_client() # Get Milvus client instance
        if not milvus_client:
            raise Exception("Could not create Milvus client.")
        logger.debug(f"Task {task_id}: Milvus client obtained.")

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

        # +++ Create IngestionJob Record +++
        job_record = None
        try:
            job_schema = IngestionJobCreate(
                source_type='email',
                job_details=filter_criteria_dict # Store the original filter dict
            )
            job_record = crud_ingestion_job.create_ingestion_job(db=db, job_in=job_schema, user_id=user_id)
            if not job_record:
                raise Exception("CRUD function failed to create IngestionJob record.")
            logger.info(f"Task {task_id}: Created IngestionJob ID {job_record.id} for user {user_id}.")
            # Immediately update status to processing and link Celery task ID
            updated_job = crud_ingestion_job.update_job_status(
                db=db, 
                job_id=job_record.id, 
                status='processing', 
                celery_task_id=task_id
            )
            if not updated_job:
                raise Exception(f"Failed to update IngestionJob ID {job_record.id} status to processing.")
            db.commit() # Commit job creation and initial status update
            logger.info(f"Task {task_id}: Updated IngestionJob ID {job_record.id} status to processing.")
            ingestion_job_db_id = job_record.id # Store the integer ID
        except Exception as job_create_err:
            logger.error(f"Task {task_id}: Failed to create/update initial IngestionJob record: {job_create_err}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Failed to initialize job tracking: {job_create_err}'})
            db.rollback() # Ensure rollback if job creation failed
            return {'status': 'ERROR', 'message': 'Failed to initialize job tracking'}
        # --- End Create IngestionJob Record ---

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

        # --- Define Target Milvus Collection --- 
        sanitized_email = user_id.replace('@', '_').replace('.', '_')
        target_collection_name = f"{sanitized_email}_email_knowledge"
        logger.info(f"Task {task_id}: Target Milvus collection: {target_collection_name}")

        # --- Ensure Target Collection Exists --- 
        try:
            logger.info(f"Task {task_id}: Ensuring Milvus collection '{target_collection_name}' exists with dim {settings.DENSE_EMBEDDING_DIMENSION}.")
            # Use the Milvus helper function ensure_collection_exists
            ensure_collection_exists(milvus_client, target_collection_name, settings.DENSE_EMBEDDING_DIMENSION)
            logger.info(f"Task {task_id}: Milvus collection '{target_collection_name}' is ready.")
        except Exception as create_err:
             # Catch potential errors from ensure_collection_exists (e.g., connection, schema mismatch)
             logger.error(f"Task {task_id}: Failed to ensure Milvus collection '{target_collection_name}': {create_err}", exc_info=True)
             self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Failed to prepare vector collection: {create_err}'})
             # Propagate exception to main handler
             raise Exception(f"Failed to prepare target collection: {create_err}")

        # --- Perform Email Processing using Knowledge Service --- 
        logger.info(f"Task {task_id}: Calling knowledge service to process emails for user {user_id}")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 20, 'status': 'Processing emails...'})

        def update_progress(state, meta):
            full_meta = {'user_email': user_id, **meta}
            self.update_state(state=state, meta=full_meta)
        
        # Unpack the return values including attachment counts
        email_processed_count, email_failed_count, att_processed_count, att_failed_count, data_to_insert = asyncio.run(
            _process_and_store_emails(
                operation_id=task_id,
                owner_email=user_id,
                filter_criteria=filter_criteria,
                outlook_service=outlook_service,
                vector_db_client=milvus_client,
                target_collection_name=target_collection_name,
                update_state_func=update_progress,
                db_session=db,
                ingestion_job_id=ingestion_job_db_id # Use the integer ID from the created DB job record
            )
        )

        logger.info(f"Task {task_id}: Email processing completed. Emails: {email_processed_count} processed, {email_failed_count} failed. Attachments: {att_processed_count} processed, {att_failed_count} failed. Data points to insert: {len(data_to_insert)}")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 90, 'status': 'Inserting data...'})

        # --- Insert Data into Milvus ---
        if data_to_insert:
            try:
                logger.info(f"Task {task_id}: Inserting {len(data_to_insert)} data points into Milvus collection {target_collection_name}.")
                # Use Milvus client insert method
                insert_result = milvus_client.insert(
                    collection_name=target_collection_name,
                    data=data_to_insert
                )
                # Log success based on input length, as result structure might vary
                logger.info(f"Task {task_id}: Successfully called Milvus insert for {len(data_to_insert)} points into {target_collection_name}.")
            except Exception as insert_err:
                logger.error(f"Task {task_id}: Failed to insert data into Milvus: {insert_err}", exc_info=True)
                # If insert fails, consider all items (emails + attachments) as failed for this task run
                email_failed_count = email_processed_count + email_failed_count
                att_failed_count = att_processed_count + att_failed_count
                self.update_state(state='FAILURE', meta={'user_email': user_id, 'progress': 95, 'status': f'Failed to save data: {insert_err}'})
                # Consider if we need to return partial success or just failure
                return {'status': 'ERROR', 'message': f'Failed final save step: {insert_err}', 'emails_processed': 0, 'emails_failed': email_failed_count, 'attachments_processed': 0, 'attachments_failed': att_failed_count}
        else:
             logger.warning(f"Task {task_id}: No data points were generated by the processing service, nothing to insert.")

        # --- Task Completion ---
        final_status = 'SUCCESS'
        final_message = f"Email processing completed. Emails: {email_processed_count} processed, {email_failed_count} failed. Attachments: {att_processed_count} processed, {att_failed_count} failed."
        if email_failed_count > 0 or att_failed_count > 0:
             final_status = 'PARTIAL_SUCCESS'
             logger.warning(f"Task {task_id}: Completed with {email_failed_count} email failures and {att_failed_count} attachment failures.")
        
        logger.info(f"Task {task_id}: {final_message}")
        self.update_state(state='SUCCESS', meta={
            'user_email': user_id, 
            'progress': 100, 
            'status': final_message, 
            'emails_processed': email_processed_count, 
            'emails_failed': email_failed_count,
            'attachments_processed': att_processed_count,
            'attachments_failed': att_failed_count
            })
        return {
            'status': final_status, 
            'message': final_message, 
            'emails_processed': email_processed_count, 
            'emails_failed': email_failed_count,
            'attachments_processed': att_processed_count,
            'attachments_failed': att_failed_count
            }

    except Exception as e:
        task_id_exc = getattr(self.request, 'id', 'UNKNOWN_TASK_ID')
        user_id_exc = user_id if 'user_id' in locals() else 'UNKNOWN_USER'
        logger.error(f"Task {task_id_exc} failed for user '{user_id_exc}': {e}", exc_info=True)
        job_id_exc = job_record.id if 'job_record' in locals() and job_record else None
        error_msg_exc = str(e)
        try:
            # Attempt to update state one last time on general failure
            self.update_state(state='FAILURE', meta={'user_email': user_id_exc, 'status': f'Internal task error: {error_msg_exc}'})
            # ++ Update IngestionJob status on failure ++
            if db and job_id_exc is not None:
                try:
                    crud_ingestion_job.update_job_status(db=db, job_id=job_id_exc, status='failed', error_message=error_msg_exc)
                    db.commit()
                    logger.info(f"Task {task_id_exc}: Updated IngestionJob ID {job_id_exc} status to failed.")
                except Exception as update_fail_err:
                    db.rollback()
                    logger.error(f"Task {task_id_exc}: Failed to update IngestionJob ID {job_id_exc} status to failed during exception handling: {update_fail_err}")
            # -- End Update --
        except Exception as state_update_error:
            logger.error(f"Task {task_id_exc}: Failed to update state/job during exception handling: {state_update_error}")
        # Reraise the exception to let Celery handle it (logging, retries etc.)
        raise e # Reraise after logging and state update attempt
    finally:
        # ++ Update IngestionJob status on completion (if successful/partial) ++
        final_job_status = None
        final_job_error = None
        if 'final_status' in locals(): # Check if task reached completion logic
            if final_status == 'SUCCESS':
                final_job_status = 'completed'
            elif final_status == 'PARTIAL_SUCCESS':
                 final_job_status = 'partial_complete'
                 final_job_error = final_message # Store the partial success message
            
            if db and job_record and final_job_status:
                try:
                    crud_ingestion_job.update_job_status(db=db, job_id=job_record.id, status=final_job_status, error_message=final_job_error)
                    db.commit()
                    logger.info(f"Task {task_id}: Updated IngestionJob ID {job_record.id} status to {final_job_status}.")
                except Exception as final_update_err:
                    db.rollback()
                    logger.error(f"Task {task_id}: Failed to update final IngestionJob ID {job_record.id} status to {final_job_status}: {final_update_err}")
        # -- End Update --

        # Ensure DB session is closed
        if db:
            db.close()
            logger.debug(f"Task {getattr(self.request, 'id', 'UNKNOWN')}: Database session closed.")
        # Milvus client closing might not be needed if managed elsewhere 