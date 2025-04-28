# backend/app/tasks/azure_tasks.py
import logging
import uuid
from typing import List, Tuple, Dict, Optional, Any
import pathlib
import asyncio
import os
import json # Import json

from celery import Task
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.db.session import SessionLocal
from app.celery_app import celery_app
from app.config import settings
from app.models.azure_blob_sync_item import AzureBlobSyncItem
from app.crud import crud_azure_blob_sync_item, crud_azure_blob, user_crud
from app.crud import crud_ingestion_job, crud_processed_file # Keep
from app.db.models.ingestion_job import IngestionJob
from app.db.models.processed_file import ProcessedFile # Keep
from app.services.azure_blob_service import AzureBlobService
# Use s3_service for R2 upload as before
from app.services import s3 as s3_service

logger = logging.getLogger(__name__)

# Define a namespace for generating UUIDs based on Azure Blob objects
AZURE_BLOB_NAMESPACE_UUID = uuid.UUID('b6e3f8a2-8d5e-4c1b-9f7d-4e2a8b0d5f1b')

# Helper function to generate R2 object key for Azure Blob
def generate_azure_r2_key(container: str, blob_path: str, blob_name: str) -> str:
    """Generates a unique R2 object key for an Azure blob."""
    unique_id_string = f"azure://{container}/{blob_path}"
    deterministic_id = str(uuid.uuid5(AZURE_BLOB_NAMESPACE_UUID, unique_id_string))
    original_extension = "".join(pathlib.Path(blob_name).suffixes)
    # Structure: provider/deterministic_id/filename.ext
    return f"azure_blob/{deterministic_id}{original_extension}"

# Remove old _process_items_for_connection function (logic moved)
# async def _process_items_for_connection(...) -> Tuple[List[Dict[str, Any]], int, int]: ...

# Remove old _execute_azure_ingestion_logic function (logic moved)
# async def _execute_azure_ingestion_logic(ingestion_job_id: int, task_id: str): ...

# --- Base Task Class (Unchanged) ---
class AzureProcessingTask(Task):
    _db: Optional[Session] = None

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self._db:
            try: self._db.close(); logger.debug(f"Task {task_id}: DB session closed.")
            except Exception as e: logger.error(f"Task {task_id}: Error closing DB session: {e}", exc_info=True)

    @property
    def db(self) -> Session:
        if self._db is None: self._db = SessionLocal()
        elif not self._db.is_active:
            logger.warning(f"Task {self.request.id}: DB session inactive, creating new one.")
            try: self._db.close()
            except Exception: pass
            self._db = SessionLocal()
        return self._db


# --- Core Processing Logic Helper ---
async def _process_azure_connection_items_and_save(
    task_instance: Task,
    db_session: Session,
    azure_service: AzureBlobService,
    items_to_process: List[AzureBlobSyncItem],
    user_email: str,
    ingestion_job_id: int
) -> Tuple[int, int]: # Return processed_count, failed_count
    task_id = task_instance.request.id
    processed_count = 0
    failed_count = 0

    for item in items_to_process:
        item_processed_successfully = False
        
        try:
            logger.info(f"Task {task_id}: Processing item {item.id}: {item.item_type} - {item.container_name}/{item.item_path}")
            if item.status == 'pending':
                crud_azure_blob_sync_item.update_sync_item_status(db_session, db_item=item, status='processing')

            blobs_to_process: List[Dict[str, Any]] = [] # Store full blob info
            if item.item_type == 'blob':
                # Need to fetch metadata for single blob if not already available
                # Assuming item_path is the full path
                try:
                     # Use list_blobs to get metadata for the single blob
                     # This might be slightly inefficient but ensures consistent metadata structure
                     blob_list = await azure_service.list_blobs(item.container_name, prefix=item.item_path)
                     # Find the exact match (list_blobs with prefix might return others if names overlap)
                     exact_match = next((b for b in blob_list if b.get('path') == item.item_path and not b.get('isDirectory')), None)
                     if exact_match:
                          blobs_to_process.append(exact_match)
                     else:
                          logger.warning(f"Task {task_id}: Single blob item {item.id} path '{item.item_path}' not found via list_blobs. Skipping item.")
                          raise FileNotFoundError(f"Blob '{item.item_path}' not found.")
                except FileNotFoundError as fnf_err:
                     raise fnf_err # Re-raise to fail the item
                except Exception as list_err:
                     logger.error(f"Task {task_id}: Error fetching metadata for single blob item {item.id} ('{item.item_path}'): {list_err}", exc_info=True)
                     raise Exception(f"Could not fetch metadata for blob '{item.item_path}'.") from list_err

            elif item.item_type == 'prefix':
                blobs_under_prefix = await azure_service.list_blobs(item.container_name, item.item_path)
                blobs_to_process.extend([b for b in blobs_under_prefix if not b.get('isDirectory')])
            
            if not blobs_to_process:
                logger.info(f"Task {task_id}: No actual blobs found to process for item {item.id}. Marking as completed.")
                item_processed_successfully = True
            else:
                all_blobs_in_item_succeeded = True # Assume success
                logger.info(f"Task {task_id}: Found {len(blobs_to_process)} blob(s) to process for item {item.id}.")
                
                for blob_meta in blobs_to_process:
                    blob_container = item.container_name # Use container from sync item
                    blob_path = blob_meta.get('path')
                    blob_name = blob_meta.get('name')
                    content_type = blob_meta.get('content_type')
                    size_bytes = blob_meta.get('size')
                    last_modified_iso = blob_meta.get('lastModified') # Already ISO string from service
                    etag = blob_meta.get('etag')

                    if not blob_path or not blob_name:
                         logger.warning(f"Task {task_id}: Skipping blob with missing path or name in item {item.id}. Metadata: {blob_meta}")
                         all_blobs_in_item_succeeded = False # Treat missing essential info as failure for this blob
                         continue

                    source_identifier = f"azure://{blob_container}/{blob_path}"
                    r2_object_key: Optional[str] = None
                    blob_processing_error: Optional[str] = None

                    try:
                        # --- Check if already processed ---
                        existing_record = crud_processed_file.get_processed_file_by_source_id(db=db_session, source_identifier=source_identifier)
                        if existing_record:
                            logger.info(f"Task {task_id}: Blob {source_identifier} already processed (DB ID: {existing_record.id}). Skipping re-processing.")
                            continue # Skip to the next blob
                        # --- End Check ---

                        # 1. Download Content
                        logger.debug(f"Task {task_id}: Downloading content for {source_identifier}")
                        blob_content_bytes = await azure_service.download_blob_content(blob_container, blob_path)
                        if blob_content_bytes is None: # Check explicitly for None
                            logger.warning(f"Task {task_id}: No content downloaded for blob {blob_path}. Skipping.")
                            raise FileNotFoundError(f"Content not found or inaccessible for {blob_path}")
                        # Ensure size is updated if metadata was missing it
                        if size_bytes is None:
                             size_bytes = len(blob_content_bytes)
                            
                        # 2. Upload to R2
                        generated_r2_key = generate_azure_r2_key(blob_container, blob_path, blob_name)
                        # Use run_in_threadpool for potentially blocking I/O
                        upload_successful = await run_in_threadpool(
                            s3_service.upload_bytes_to_r2,
                            bucket_name=settings.R2_BUCKET_NAME,
                            object_key=generated_r2_key,
                            data_bytes=blob_content_bytes
                        )
                        if not upload_successful:
                            raise Exception("Failed to upload to R2")
                        r2_object_key = generated_r2_key
                        logger.info(f"Task {task_id}: Uploaded {source_identifier} to R2: {r2_object_key}")

                        # 3. Prepare ProcessedFile Data
                        additional_metadata = {
                            "azure_connection_id": str(item.connection_id),
                            "container": blob_container,
                            "path": blob_path,
                            "last_modified_utc": last_modified_iso, # Store ISO string
                            "etag": etag
                        }
                        processed_file_dict = {
                            "ingestion_job_id": ingestion_job_id,
                            "source_type": 'azure_blob',
                            "source_identifier": source_identifier,
                            "additional_data": additional_metadata, # Store Azure info
                            "r2_object_key": r2_object_key,
                            "owner_email": user_email,
                            "status": 'pending_analysis', # SET CORRECT STATUS
                            "original_filename": blob_name,
                            "content_type": content_type, 
                            "size_bytes": size_bytes, 
                        }
                        processed_file_dict_cleaned = {k: v for k, v in processed_file_dict.items() if v is not None}

                        # 4. Save ProcessedFile Record
                        processed_file_model = ProcessedFile(**processed_file_dict_cleaned)
                        created_record = crud_processed_file.create_processed_file_entry(db=db_session, file_data=processed_file_model)
                        if not created_record:
                            raise Exception(f"Failed to save ProcessedFile record for {source_identifier}")
                        logger.info(f"Task {task_id}: Saved ProcessedFile {created_record.id} for {source_identifier}")
                        
                    except Exception as blob_err:
                         logger.error(f"Task {task_id}: Failed processing blob {source_identifier}: {blob_err}", exc_info=True)
                         all_blobs_in_item_succeeded = False # Mark item failure if any blob fails
                         blob_processing_error = str(blob_err)[:1024] # Store truncated error
                         # Attempt to save failure record
                         try:
                              failed_file_entry = ProcessedFile(
                                   ingestion_job_id=ingestion_job_id,
                                   source_type='azure_blob',
                                   source_identifier=source_identifier,
                                   owner_email=user_email,
                                   status='failed',
                                   error_message=blob_processing_error,
                                   original_filename=blob_name,
                                   size_bytes=size_bytes,
                                   r2_object_key=None # Ensure R2 key is None on failure
                              )
                              # DIRECTLY use the created instance
                              crud_processed_file.create_processed_file_entry(db=db_session, file_data=failed_file_entry)
                              logger.info(f"Task {task_id}: Saved FAILED ProcessedFile record for {source_identifier}")
                         except Exception as db_fail_err:
                              logger.error(f"Task {task_id}: Could not save FAILED ProcessedFile record for {source_identifier}: {db_fail_err}", exc_info=True)
                # --- End Blob Loop ---
                item_processed_successfully = all_blobs_in_item_succeeded

        except Exception as item_level_err:
            logger.error(f"Task {task_id}: Error processing sync item {item.id} ({item.item_path}): {item_level_err}", exc_info=True)
            item_processed_successfully = False

        # Update item status based on overall success/failure
        final_item_status = 'completed' if item_processed_successfully else 'failed'
        if item.status == 'processing': # Only update if we set it to processing
            try:
                crud_azure_blob_sync_item.update_sync_item_status(db_session, db_item=item, status=final_item_status)
            except Exception as update_err:
                logger.error(f"Task {task_id}: CRITICAL - Failed to update sync item {item.id} status to {final_item_status}: {update_err}", exc_info=True)
                # If status update fails, the job might reprocess this item. Log prominently.

        # Increment cumulative counters
        if item_processed_successfully:
            processed_count += 1
        else:
            failed_count += 1

    # --- End Sync Item Loop ---
    logger.info(f"Task {task_id}: Finished item processing loop. Processed: {processed_count}, Failed: {failed_count}")
    return processed_count, failed_count

# --- Main Celery Task --- 
@celery_app.task(bind=True, base=AzureProcessingTask, name="tasks.azure.process_ingestion", max_retries=3, default_retry_delay=60)
def process_azure_ingestion_task(self: Task, ingestion_job_id: int):
    task_id = self.request.id
    logger.info(f"Task {task_id}: Received Azure Blob ingestion job ID: {ingestion_job_id}")
    self.update_state(state='PENDING', meta={'details': 'Initializing job processing...'})

    job: Optional[IngestionJob] = None
    db: Optional[Session] = None

    try:
        db = self.db # Get session from base class
        job = crud_ingestion_job.get_ingestion_job(db, job_id=ingestion_job_id)
        if not job:
            logger.error(f"Task {task_id}: IngestionJob with ID {ingestion_job_id} not found.")
            # Use Celery failure state
            self.update_state(state='FAILURE', meta={'details': f'Job ID {ingestion_job_id} not found.'})
            # Optionally raise an exception to signify failure clearly
            raise ValueError(f"IngestionJob ID {ingestion_job_id} not found.")

        # job.user_id contains the user's UUID
        user_id_uuid = job.user_id
        if not user_id_uuid:
             logger.error(f"Task {task_id}: Job {ingestion_job_id} is missing user ID. Cannot proceed.")
             raise ValueError(f"Job {ingestion_job_id} is missing user ID.")

        # Fetch the user object using the UUID to get the email
        user = user_crud.get_user_by_id(db, user_id=user_id_uuid)
        if not user:
            logger.error(f"Task {task_id}: User with ID {user_id_uuid} associated with Job {ingestion_job_id} not found.")
            raise ValueError(f"User ID {user_id_uuid} not found.")
        
        # Now get the actual user email
        user_email = user.email
        if not user_email:
             logger.error(f"Task {task_id}: User {user_id_uuid} is missing email address. Cannot proceed.")
             raise ValueError(f"User {user_id_uuid} is missing email address.")
             
        logger.info(f"Task {task_id}: Processing job {ingestion_job_id} for user {user_email} (ID: {user_id_uuid})")
        if job.status in ['completed', 'failed', 'partial_complete']:
             logger.warning(f"Task {task_id}: Job {ingestion_job_id} already in terminal state '{job.status}'. Skipping.")
             self.update_state(state='SUCCESS', meta={'details': f'Job already completed or failed ({job.status}).'})
             return {'status': 'skipped', 'reason': f'Job already in state {job.status}', 'processed': 0, 'failed': 0}

        # Use job.id which is confirmed to exist after fetching the job
        crud_ingestion_job.update_job_status(db=db, job_id=job.id, status='processing')
        self.update_state(state='STARTED', meta={'details': 'Job status set to processing.'})
        
        # Get connection_id from job_details (assuming it's stored there)
        connection_id_str = job.job_details.get('azure_connection_id')
        if not connection_id_str:
             # Use job.id for logging
             logger.error(f"Task {task_id}: Job {job.id} details missing 'azure_connection_id'.")
             raise ValueError("Missing Azure connection ID in job details.")
        try:
            connection_id = uuid.UUID(connection_id_str)
        except ValueError:
            logger.error(f"Task {task_id}: Invalid Azure connection ID format in job details: {connection_id_str}")
            raise ValueError("Invalid Azure connection ID format.")
            
        # Get Azure Credentials for this connection
        credential_result = crud_azure_blob.get_connection_with_decrypted_credentials(
            db=db, connection_id=connection_id, user_id=job.user_id
        )
        if not credential_result:
            raise ValueError(f"Could not retrieve credentials for Azure connection {connection_id}")
        connection, connection_string = credential_result
        if not connection_string:
             raise ValueError(f"Empty connection string for Azure connection {connection_id}")

        # Fetch pending sync items for THIS connection
        # We need to fetch them again here, as the helper needs the list
        pending_items = crud_azure_blob_sync_item.get_items_by_user_and_connection(
            db=db,
            user_id=job.user_id,
            connection_id=connection_id,
            status_filter=['pending'] # Fetch only pending for processing
        )
        
        if not pending_items:
            # Use job.id for logging and updating
            logger.warning(f"Task {task_id}: No PENDING Azure sync items found for job {job.id} / connection {connection_id}. Job may be redundant or items already processed/failed.")
            # Mark job as completed if no pending items were found
            crud_ingestion_job.update_job_status(db=db, job_id=job.id, status='completed')
            db.commit()
            self.update_state(state='SUCCESS', meta={'details': 'No pending items found to process.', 'processed': 0, 'failed': 0})
            return {'status': 'completed', 'message': 'No pending items found', 'processed': 0, 'failed': 0}

        logger.info(f"Task {task_id}: Found {len(pending_items)} pending items for connection {connection_id} to process.")

        # --- Define the async part of the work ---
        async def run_async_processing():
            async with AzureBlobService(connection_string=connection_string) as azure_service:
                # Pass db session obtained from the sync task context
                processed_count, failed_count = await _process_azure_connection_items_and_save(
                    task_instance=self,
                    db_session=db, # Pass the synchronous session
                    azure_service=azure_service,
                    items_to_process=pending_items,
                    user_email=user_email, # Pass the correct user email string
                    ingestion_job_id=job.id
                )
            return processed_count, failed_count
        # --- End async definition ---

        # --- Execute the async part using asyncio.run --- 
        processed_count, failed_count = asyncio.run(run_async_processing())
        # --- End async execution ---

        # --- Update Final Job Status --- 
        final_status = 'unknown'
        if failed_count > 0 and processed_count > 0: final_status = 'partial_complete'
        elif failed_count > 0 and processed_count == 0: final_status = 'failed'
        elif failed_count == 0 and processed_count >= 0: final_status = 'completed'
        final_message = f"Processed {processed_count} items, failed {failed_count} items."
        if final_status == 'failed' and processed_count == 0: final_message = f"All {failed_count} items failed."
        if final_status == 'completed' and processed_count == 0: final_message = "No new items processed (may have been processed previously or none found)."
        if final_status == 'completed' and processed_count > 0: final_message = f"Successfully processed {processed_count} items."

        # Use job.id for logging and updating
        logger.info(f"Task {task_id}: Updating job {job.id} final status to '{final_status}'. Processed: {processed_count}, Failed: {failed_count}")
        crud_ingestion_job.update_job_status(db=db, job_id=job.id, status=final_status, error_message=None if final_status == 'completed' else final_message)
        db.commit()
        
        # Use job.id for logging
        logger.info(f"Task {task_id}: Database transaction committed successfully for job {job.id}.")
        self.update_state(state='SUCCESS' if final_status in ['completed', 'partial_complete'] else 'FAILURE', meta={'details': final_message, 'processed': processed_count, 'failed': failed_count})
        return {'status': final_status, 'processed': processed_count, 'failed': failed_count}

    except Exception as e:
        task_id = self.request.id if self.request else "UNKNOWN_TASK"
        # Use job.id if available, otherwise use the input ingestion_job_id
        # Use job.user_id (UUID) if job exists, otherwise None
        user_id_for_log = str(job.user_id) if job else "UNKNOWN_USER"
        job_id_for_log = str(job.id) if job else str(ingestion_job_id)
        err_msg = f"Task {task_id}: Unhandled exception processing job {job_id_for_log} for user {user_id_for_log}: {e}"
        logger.error(err_msg, exc_info=True)
        if db: # Check if session was created before trying rollback
            try: db.rollback(); logger.warning(f"Task {task_id}: Rolled back DB transaction for job {job_id_for_log}.")
            except Exception as rb_err: logger.error(f"Task {task_id}: CRITICAL - Failed to rollback transaction for job {job_id_for_log}: {rb_err}", exc_info=True)
        # Attempt to mark job as failed even after rollback (requires new session/commit technically, but best effort)
        try:
             if job and db: # Check if job and db were fetched/created
                  # Update status using the existing session before potential close
                  crud_ingestion_job.update_job_status(db=db, job_id=job.id, status='failed', error_message=f"Unhandled task error: {str(e)[:250]}...")
                  db.commit() # Commit this specific failure update
             else:
                  logger.warning(f"Task {task_id}: Could not mark job {job_id_for_log} as failed in DB due to missing job object or DB session.")
        except Exception as final_fail_err:
            logger.error(f"Task {task_id}: Failed to mark job {job_id_for_log} as failed after unhandled exception: {final_fail_err}", exc_info=True)

        self.update_state(state='FAILURE', meta={'details': err_msg})
        # Re-raise the exception for Celery retry logic or marking as failed
        raise e 