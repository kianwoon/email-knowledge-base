# backend/app/tasks/s3_tasks.py
import logging
# import base64 # No longer needed?
import asyncio
from typing import List, Dict, Any, Tuple, Optional, Set
import uuid
from datetime import datetime, timezone
import os
# import json # No longer needed?
import pathlib
import io # For handling byte streams

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session
import boto3
from botocore.exceptions import ClientError, NoCredentialsError # Added NoCredentialsError
from starlette.concurrency import run_in_threadpool # Added import

from ..celery_app import celery_app
from ..config import settings
from app.services import s3 as s3_service # For AssumeRole logic
# Import R2 service/utils (Assuming it exists or will be created)
from app.services import r2_service # Placeholder - Needs implementation # TODO: Ensure this service exists
# --- Remove Milvus/Qdrant related imports ---
# from pymilvus import MilvusClient
# from app.db.milvus_client import get_milvus_client, ensure_collection_exists
# from app.db.qdrant_client import get_qdrant_client
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.exceptions import UnexpectedResponse

# --- Import relevant models and CRUD operations ---
from app.db.session import SessionLocal # Keep SessionLocal
from app.db.models.ingestion_job import IngestionJob
from app.db.models.processed_file import ProcessedFile
from app.db.models.s3_sync_item import S3SyncItem # Keep S3SyncItem
from app.crud import crud_ingestion_job, crud_processed_file, crud_s3_sync_item # Add crud_s3_sync_item
# --- Remove old CRUD operations ---
# from app.crud import crud_aws_credential


logger = get_task_logger(__name__)

# --- Remove Milvus helper functions ---
# def generate_s3_milvus_collection_name(user_email: str) -> str: ...
# def generate_s3_milvus_pk(bucket: str, key: str) -> str: ...

# Define a namespace for generating UUIDs - potentially useful for R2 keys
S3_NAMESPACE_UUID = uuid.UUID('a5b8e4a1-7c4f-4d1a-8b0e-3f4d1a7c4f0d') # Example random namespace


# Helper function to generate R2 object key (example)
def generate_r2_object_key(user_email: str, original_key: str) -> str:
    """Generates a unique R2 object key, potentially including user and original path info."""
    # Fixed invalid character in docstring
    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    # Use a UUID based on user and original key to ensure uniqueness and prevent collisions
    unique_suffix = str(uuid.uuid5(S3_NAMESPACE_UUID, f"{user_email}:{original_key}"))
    # Extract filename from original key
    filename = pathlib.Path(original_key).name
    # Structure: user_prefix/uuid_prefix/filename
    return f"s3_imports/{sanitized_email}/{unique_suffix}/{filename}"

async def _list_all_objects_recursive(s3_client, bucket: str, prefix: str, task_instance: Task, user_email: str) -> List[Dict[str, Any]]:
    """Recursively lists all objects under a given prefix, handling pagination."""
    # Fixed invalid character in docstring
    objects = []
    continuation_token = None
    # Use task_instance.request.id for logging consistency
    task_id = task_instance.request.id if task_instance.request else "UNKNOWN_TASK"
    initial_status_msg = f'Discovering files in s3://{bucket}/{prefix}...'
    # Update Celery task state (use meta fields recognizable by frontend/API if needed)
    task_instance.update_state(state='PROGRESS', meta={'current_step': 'discovery', 'details': initial_status_msg})
    logger.info(f"Task {task_id}: {initial_status_msg}")

    while True:
        try:
            list_kwargs = {'Bucket': bucket, 'Prefix': prefix}
            if continuation_token:
                list_kwargs['ContinuationToken'] = continuation_token
            
            # Run sync boto3 call in threadpool for async context
            response = await run_in_threadpool(s3_client.list_objects_v2, **list_kwargs)

            if 'Contents' in response:
                for obj in response['Contents']:
                    # Skip zero-byte objects that often represent folders implicitly
                    if obj.get('Size') == 0 and obj['Key'].endswith('/'):
                        continue
                    objects.append({
                        'key': obj['Key'],
                        'last_modified': obj.get('LastModified'),
                        'size': obj.get('Size'),
                        'content_type': None # Will be fetched later via head_object if needed
                    })
            
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
                logger.debug(f"Task {task_id}: Paginating object list for prefix '{prefix}'")
            else:
                break # Exit loop if not truncated
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            logger.error(f"Task {task_id}: S3 ClientError listing objects in s3://{bucket}/{prefix} (Code: {error_code}): {e}", exc_info=True)
            # Specific handling for access denied during listing
            if error_code == 'AccessDenied':
                 raise PermissionError(f"Access Denied listing objects in s3://{bucket}/{prefix}. Check IAM permissions.")
            raise e # Re-raise other client errors
        except Exception as e:
            logger.error(f"Task {task_id}: Unexpected error listing objects in s3://{bucket}/{prefix}: {e}", exc_info=True)
            raise e
            
    logger.info(f"Task {task_id}: Discovered {len(objects)} potential objects under prefix '{prefix}'")
    return objects

# --- Modify Task Base Class ---
class S3ProcessingTask(Task):
    _db: Optional[Session] = None
    # --- Remove Milvus client property ---
    # _milvus_client: Optional[MilvusClient] = None
    _r2_client: Optional[Any] = None # Add R2 client property (optional, if stateful)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        # Ensure DB session is closed after task completion or failure
        if self._db:
            try:
                self._db.close()
                logger.debug(f"Task {task_id}: DB session closed.")
            except Exception as e:
                logger.error(f"Task {task_id}: Error closing DB session: {e}", exc_info=True)
        # Close R2 client if managed here (example)
        # if self._r2_client:
        #     pass # Add closing logic if needed

    @property
    def db(self) -> Session:
        # Provides a DB session scoped to the task instance
        if self._db is None:
            logger.debug(f"Task {self.request.id}: Creating new DB session.")
            self._db = SessionLocal()
        elif not self._db.is_active:
            logger.warning(f"Task {self.request.id}: DB session was inactive, creating new one.")
            try:
                self._db.close() # Attempt to close the inactive session first
            except Exception as e:
                 logger.error(f"Task {self.request.id}: Error closing inactive DB session: {e}", exc_info=True)
            self._db = SessionLocal() # Recreate if inactive or closed
        return self._db

    # --- Remove Milvus client property ---
    # @property
    # def milvus_client(self) -> MilvusClient: ...

    @property
    def r2_client(self) -> Any:
        # Provides an R2 client instance (basic example)
        # Assumes r2_service.get_r2_client() exists and handles credentials
        if self._r2_client is None:
             logger.debug(f"Task {self.request.id}: Getting R2 client instance.")
             # This assumes r2_service handles creds from settings
             # TODO: Ensure r2_service.get_r2_client() is implemented correctly
             self._r2_client = r2_service.get_r2_client()
        return self._r2_client

# --- Modify Core Logic Helper Function ---
async def _process_s3_to_r2_and_db(
    task_instance: Task,
    db_session: Session,
    job: IngestionJob, # Pass the whole job object
    sync_items_map: Dict[Tuple[str, str], S3SyncItem], # Map of (bucket, key) -> S3SyncItem
    s3_client: Any, # The boto3 S3 client with assumed role creds
    r2_client: Any  # The R2 client
) -> Tuple[int, int]: # Return counts: success, failure
    """
    Processes files listed in job_details from S3, uploads them to R2,
    creates ProcessedFile records, and updates corresponding S3SyncItem records.
    Updates IngestionJob status along the way.
    """
    # Fixed invalid character and formatting in docstring
    task_id = task_instance.request.id
    user_email = job.user_id
    job_details = job.job_details # This should contain 'bucket' and 'key' or 'prefix'

    processed_count = 0
    failed_count = 0

    s3_bucket = job_details.get('bucket')
    s3_key_or_prefix = job_details.get('key') or job_details.get('prefix') # Prefer specific key

    if not s3_bucket or not s3_key_or_prefix:
        err_msg = f"Task {task_id}: Invalid job details: Missing 'bucket' or 'key'/'prefix'."
        logger.error(err_msg)
        crud_ingestion_job.update_job_status(db=db_session, job_id=job.id, status='failed', error_message=err_msg)
        # Also fail associated sync items if possible (might be complex if job covers multiple items)
        # For simplicity, job failure implies sync item failure here.
        raise ValueError("Invalid S3 job details.")

    logger.info(f"Task {task_id}: Starting processing for job {job.id}, target: s3://{s3_bucket}/{s3_key_or_prefix}")

    # --- Discover Files ---
    try:
        task_instance.update_state(state='PROGRESS', meta={'current_step': 'discovery', 'details': f'Discovering files in s3://{s3_bucket}/{s3_key_or_prefix}...'})
        objects_to_process: List[Dict[str, Any]] = []
        is_prefix = s3_key_or_prefix.endswith('/')

        if is_prefix:
            # Use recursive listing for prefixes
            discovered_objects = await _list_all_objects_recursive(s3_client, s3_bucket, s3_key_or_prefix, task_instance, user_email)
            objects_to_process.extend(discovered_objects)
        else:
            # Handle single file
            try:
                # Use run_in_threadpool for consistency
                head = await run_in_threadpool(s3_client.head_object, Bucket=s3_bucket, Key=s3_key_or_prefix)
                objects_to_process.append({
                    'key': s3_key_or_prefix,
                    'last_modified': head.get('LastModified'),
                    'size': head.get('ContentLength'),
                    'content_type': head.get('ContentType') # Get content type from head
                })
            except ClientError as e:
                 error_code = e.response.get('Error', {}).get('Code')
                 if error_code == 'NoSuchKey' or 'NotFound' in str(e) or error_code == '404': # More robust check
                     logger.warning(f"Task {task_id}: Specified single key s3://{s3_bucket}/{s3_key_or_prefix} not found.")
                     # Job completed with 0 files if the single key doesn't exist
                 elif error_code == 'AccessDenied':
                     raise PermissionError(f"Access Denied getting metadata for s3://{s3_bucket}/{s3_key_or_prefix}. Check IAM permissions.")
                 else:
                     logger.error(f"Task {task_id}: S3 ClientError getting metadata for s3://{s3_bucket}/{s3_key_or_prefix}: {e}", exc_info=True)
                     raise e # Re-raise other client errors
            except Exception as e:
                 logger.error(f"Task {task_id}: Unexpected error getting metadata for s3://{s3_bucket}/{s3_key_or_prefix}: {e}", exc_info=True)
                 raise e # Re-raise unexpected errors

        total_files_found = len(objects_to_process)
        logger.info(f"Task {task_id}: Discovered {total_files_found} files to process for job {job.id}.")
        if total_files_found == 0:
             logger.info(f"Task {task_id}: No files found for job {job.id}. Marking job as completed.")
             crud_ingestion_job.update_job_status(db=db_session, job_id=job.id, status='completed')
             # Mark associated sync items as failed? Or completed? Depends on definition.
             # Let's mark sync items as completed if 0 files found for the specific key/prefix requested by them.
             # This assumes the sync_items_map contains the items this job is responsible for.
             for sync_item in sync_items_map.values():
                 if sync_item.status == 'processing': # Only update items marked by this task instance
                    try:
                        crud_s3_sync_item.update_item_status(db=db_session, db_item=sync_item, status='completed') # Mark as completed as no file found
                    except Exception as update_err:
                        logger.error(f"Task {task_id}: CRITICAL - Failed to update sync item {sync_item.id} to completed status after 0 files found: {update_err}", exc_info=True)
             return 0, 0 # Success, Failure

    except PermissionError as e:
        # Handle permission errors during discovery specifically
        err_msg = f"Task {task_id}: Permission Error during S3 discovery: {e}"
        logger.error(err_msg)
        crud_ingestion_job.update_job_status(db=db_session, job_id=job.id, status='failed', error_message=err_msg)
        # Fail associated sync items
        for sync_item in sync_items_map.values():
             if sync_item.status == 'processing':
                 try:
                     crud_s3_sync_item.update_item_status(db=db_session, db_item=sync_item, status='failed')
                 except Exception as update_err:
                     logger.error(f"Task {task_id}: CRITICAL - Failed to update sync item {sync_item.id} to failed status after discovery permission error: {update_err}", exc_info=True)
        raise # Re-raise to fail the Celery task
    except Exception as e:
        err_msg = f"Task {task_id}: Error during S3 discovery phase: {e}"
        logger.error(err_msg, exc_info=True)
        crud_ingestion_job.update_job_status(db=db_session, job_id=job.id, status='failed', error_message=err_msg)
        # Fail associated sync items
        for sync_item in sync_items_map.values():
            if sync_item.status == 'processing':
                 try:
                     crud_s3_sync_item.update_item_status(db=db_session, db_item=sync_item, status='failed')
                 except Exception as update_err:
                     logger.error(f"Task {task_id}: CRITICAL - Failed to update sync item {sync_item.id} to failed status after discovery error: {update_err}", exc_info=True)
        raise # Re-raise to fail the Celery task

    # --- Process Each File ---
    task_instance.update_state(state='PROGRESS', meta={'current_step': 'processing', 'total_files': total_files_found, 'processed_count': 0, 'failed_count': 0})
    file_num = 0
    processed_sync_item_ids = set() # Keep track of sync items successfully processed

    for obj_meta in objects_to_process:
        file_num += 1
        s3_object_key = obj_meta['key']
        source_identifier = f"s3://{s3_bucket}/{s3_object_key}"
        original_filename = pathlib.Path(s3_object_key).name
        logger.info(f"Task {task_id}: Processing file {file_num}/{total_files_found}: {source_identifier}")

        # Find corresponding S3SyncItem
        sync_item = sync_items_map.get((s3_bucket, s3_object_key))
        if not sync_item:
            logger.warning(f"Task {task_id}: Discovered file {source_identifier} does not have a corresponding S3SyncItem tracked by this job. Skipping.")
            # Or should we process anyway and not update sync item? Decided to skip.
            continue # Skip files not explicitly tracked by a sync item for this job instance

        # Skip if sync item already processed or failed by another task/run?
        if sync_item.status not in ['pending', 'processing']:
             logger.warning(f"Task {task_id}: Sync item for {source_identifier} (ID: {sync_item.id}) has status '{sync_item.status}'. Skipping.")
             continue

        # Define ProcessedFile data structure early
        processed_file_data = {
            "ingestion_job_id": job.id,
            "owner_email": user_email,
            "source_type": "s3",
            "source_identifier": source_identifier,
            "original_filename": original_filename,
            "r2_object_key": None, # Will be set after successful upload
            "content_type": obj_meta.get('content_type'), # Use from head_object if available
            "size_bytes": obj_meta.get('size'),
            "status": "pending_analysis", # Initial status
            "additional_data": { # Store S3 metadata (RENAMED from metadata)
                "s3_bucket": s3_bucket,
                "s3_key": s3_object_key,
                # Ensure datetime is converted to string or handle properly in CRUD
                "s3_last_modified": obj_meta.get('last_modified').isoformat() if obj_meta.get('last_modified') and hasattr(obj_meta['last_modified'], 'isoformat') else None,
                "s3_size": obj_meta.get('size'),
                # Add ETag? VersionId? from head/get object if needed
            },
            "error_message": None,
        }
        current_sync_item_status = 'failed' # Default status unless successful

        try:
            # 1. Generate R2 Key (moved earlier)
            r2_key = generate_r2_object_key(user_email, s3_object_key)
            processed_file_data["r2_object_key"] = r2_key # Store the key early

            # 2. Check if ProcessedFile already exists
            logger.debug(f"Task {task_id}: Checking for existing ProcessedFile with R2 key {r2_key}")
            existing_processed_file = crud_processed_file.get_processed_file_by_r2_key(db=db_session, r2_object_key=r2_key)

            if existing_processed_file:
                logger.warning(f"Task {task_id}: ProcessedFile record for {r2_key} already exists (ID: {existing_processed_file.id}). Skipping S3 download and R2 upload for {source_identifier}. Marking associated sync item as completed.")
                # File already processed successfully before, treat as success for this item
                processed_count += 1
                current_sync_item_status = 'completed'
                processed_sync_item_ids.add(sync_item.id)
            else:
                # File not processed before, proceed with download/upload/insert
                logger.debug(f"Task {task_id}: No existing ProcessedFile found for {r2_key}. Proceeding with ingestion.")

                # 3. Download from S3 (Streaming)
                logger.debug(f"Task {task_id}: Downloading {source_identifier}")
                task_instance.update_state(state='PROGRESS', meta={
                    'current_step': 'processing', 'current_file': source_identifier, 'file_status': 'downloading',
                    'total_files': total_files_found, 'processed_count': processed_count, 'failed_count': failed_count
                })
                # Use streaming download to handle potentially large files
                s3_object = await run_in_threadpool(s3_client.get_object, Bucket=s3_bucket, Key=s3_object_key)
                stream = s3_object['Body']
                # Update content type and size if head_object wasn't called or didn't provide them
                if not processed_file_data["content_type"]:
                     processed_file_data["content_type"] = s3_object.get('ContentType')
                if not processed_file_data["size_bytes"]: # Should usually be present from list/head
                     processed_file_data["size_bytes"] = s3_object.get('ContentLength')


                # 4. Upload to R2 (Streaming)
                logger.debug(f"Task {task_id}: Uploading {source_identifier} to R2 key {r2_key}")
                task_instance.update_state(state='PROGRESS', meta={
                    'current_step': 'processing', 'current_file': source_identifier, 'file_status': 'uploading_r2',
                    'total_files': total_files_found, 'processed_count': processed_count, 'failed_count': failed_count
                })
                # TODO: Ensure r2_service.upload_fileobj_to_r2 exists and handles credentials
                await r2_service.upload_fileobj_to_r2(
                    r2_client=r2_client,
                    file_obj=stream,
                    bucket=settings.R2_BUCKET_NAME, # Assumes setting exists # TODO: Confirm R2 bucket setting name
                    object_key=r2_key,
                    content_type=processed_file_data["content_type"] # Pass content type
                )
                # stream.close() # boto3 stream does not need explicit close usually

                # 5. Create ProcessedFile DB Record
                logger.debug(f"Task {task_id}: Creating ProcessedFile record for {r2_key}")
                task_instance.update_state(state='PROGRESS', meta={
                    'current_step': 'processing', 'current_file': source_identifier, 'file_status': 'saving_db',
                    'total_files': total_files_found, 'processed_count': processed_count, 'failed_count': failed_count
                })
                # Ensure metadata is serializable if it contains datetime objects that aren't auto-handled
                # Already handled above when defining processed_file_data

                # TODO: Ensure crud_processed_file.create_processed_file_entry exists
                processed_file_obj = ProcessedFile(**processed_file_data)
                created_entry = crud_processed_file.create_processed_file_entry(db=db_session, file_data=processed_file_obj)
                if not created_entry:
                    # Handle potential failure during add to session (though unlikely without commit)
                    raise Exception(f"Failed to add ProcessedFile record for {r2_key} to session.")

                # If all steps above succeeded
                processed_count += 1
                current_sync_item_status = 'completed'
                processed_sync_item_ids.add(sync_item.id)
                logger.info(f"Task {task_id}: Successfully processed {source_identifier} -> {r2_key}")

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            err_msg = f"S3 ClientError processing {source_identifier}: {e}"
            logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
            failed_count += 1
            processed_file_data["status"] = "ingestion_failed"
            processed_file_data["error_message"] = err_msg
            # Attempt to save failure record for ProcessedFile
            try:
                 processed_file_obj = ProcessedFile(**processed_file_data)
                 # TODO: Ensure crud_processed_file.create_processed_file_entry handles potential duplicates if retried
                 crud_processed_file.create_processed_file_entry(db=db_session, file_data=processed_file_obj)
            except Exception as db_err:
                 logger.error(f"Task {task_id}: CRITICAL - Failed to save ProcessedFile failure record for {source_identifier} after S3 error: {db_err}", exc_info=True)
        except r2_service.R2UploadError as e: # Assuming custom R2 exception # TODO: Define or import R2UploadError
            err_msg = f"R2 Upload Error for {source_identifier} to {processed_file_data.get('r2_object_key', 'N/A')}: {e}"
            logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
            failed_count += 1
            processed_file_data["status"] = "ingestion_failed"
            processed_file_data["error_message"] = err_msg
            # Attempt to save failure record for ProcessedFile
            try:
                 processed_file_obj = ProcessedFile(**processed_file_data)
                 crud_processed_file.create_processed_file_entry(db=db_session, file_data=processed_file_obj)
            except Exception as db_err:
                 logger.error(f"Task {task_id}: CRITICAL - Failed to save ProcessedFile failure record for {source_identifier} after R2 error: {db_err}", exc_info=True)
        except Exception as e:
            err_msg = f"Unexpected error processing {source_identifier}: {e}"
            logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
            failed_count += 1
            processed_file_data["status"] = "ingestion_failed"
            processed_file_data["error_message"] = err_msg
            # Attempt to save failure record for ProcessedFile
            try:
                 processed_file_obj = ProcessedFile(**processed_file_data)
                 crud_processed_file.create_processed_file_entry(db=db_session, file_data=processed_file_obj)
            except Exception as db_err:
                 logger.error(f"Task {task_id}: CRITICAL - Failed to save ProcessedFile failure record for {source_identifier} after general error: {db_err}", exc_info=True)
        finally:
            # Update S3SyncItem status based on outcome
            if sync_item: # Ensure sync_item exists before trying to update
                if current_sync_item_status == 'completed':
                    try:
                        updated_item = crud_s3_sync_item.update_item_status(db=db_session, db_item=sync_item, status='completed')
                        if updated_item:
                             logger.debug(f"Task {task_id}: Updated successfully processed S3SyncItem {sync_item.id} status to 'completed'.")
                        else:
                             logger.error(f"Task {task_id}: Failed to update successfully processed S3SyncItem {sync_item.id} status to 'completed' (update_item_status returned None).")
                    except Exception as update_err:
                         logger.error(f"Task {task_id}: CRITICAL - Failed to update successfully processed S3SyncItem {sync_item.id} status to 'completed': {update_err}", exc_info=True)
                elif current_sync_item_status == 'failed':
                    try:
                        crud_s3_sync_item.update_item_status(db=db_session, db_item=sync_item, status='failed')
                        logger.debug(f"Task {task_id}: Updated S3SyncItem {sync_item.id} status to 'failed'.")
                    except Exception as update_err:
                         logger.error(f"Task {task_id}: CRITICAL - Failed to update S3SyncItem {sync_item.id} status to 'failed': {update_err}", exc_info=True)

            # Explicitly close the S3 stream if it exists
            if 'stream' in locals() and hasattr(stream, 'close'):
                try:
                    stream.close()
                except Exception as close_err:
                    logger.warning(f"Task {task_id}: Error closing S3 stream for {source_identifier}: {close_err}")
            # Update progress
            task_instance.update_state(state='PROGRESS', meta={
                'current_step': 'processing', 'current_file': source_identifier, 'file_status': 'finished',
                'total_files': total_files_found, 'processed_count': processed_count, 'failed_count': failed_count
            })

    # --- Final check for any unprocessed sync items ---
    # Items that were marked 'processing' but didn't match a discovered file
    unprocessed_sync_items = 0
    for sync_item in sync_items_map.values():
        if sync_item.id not in processed_sync_item_ids and sync_item.status == 'processing':
            unprocessed_sync_items += 1
            logger.warning(f"Task {task_id}: S3SyncItem {sync_item.id} (s3://{sync_item.s3_bucket}/{sync_item.s3_key}) was marked 'processing' but no corresponding file was processed. Marking as 'failed'.")
            try:
                 crud_s3_sync_item.update_item_status(db=db_session, db_item=sync_item, status='failed')
                 failed_count += 1 # Count this as a failure
            except Exception as update_err:
                 logger.error(f"Task {task_id}: CRITICAL - Failed to update unprocessed S3SyncItem {sync_item.id} status to 'failed': {update_err}", exc_info=True)

    if unprocessed_sync_items > 0:
         logger.warning(f"Task {task_id}: Found {unprocessed_sync_items} sync items that were marked 'processing' but seemingly had no corresponding file discovered or processed.")


    logger.info(f"Task {task_id}: Finished processing loop for job {job.id}. Success: {processed_count}, Failed: {failed_count}")
    return processed_count, failed_count


# --- Modify Main Task Function ---
@celery_app.task(bind=True, base=S3ProcessingTask, name='tasks.s3.process_ingestion')
def process_s3_ingestion_task(self: Task, job_id: int): # Changed signature
    """
    Celery task to process an S3 ingestion job.
    Fetches files from S3 based on job details, uploads them to R2,
    creates ProcessedFile records, and updates associated S3SyncItem records.
    """
    # Fixed invalid character and formatting in docstring
    task_id = self.request.id
    logger.info(f"Task {task_id}: Received S3 ingestion job ID: {job_id}")
    self.update_state(state='PENDING', meta={'details': 'Initializing job processing...'})

    job: Optional[IngestionJob] = None # Initialize job variable
    processed_count = 0
    failed_count = 0
    db: Optional[Session] = None # Define db here to ensure it's accessible in finally

    try:
        db = self.db # Get session

        # --- Fetch IngestionJob ---
        # TODO: Ensure crud_ingestion_job.get_ingestion_job exists
        job = crud_ingestion_job.get_ingestion_job(db=db, job_id=job_id)
        if not job:
            logger.error(f"Task {task_id}: IngestionJob with ID {job_id} not found.")
            self.update_state(state='FAILURE', meta={'details': f'Job ID {job_id} not found.'})
            raise ValueError(f"IngestionJob ID {job_id} not found.")

        user_email = job.user_id
        logger.info(f"Task {task_id}: Processing job {job_id} for user {user_email}")

        # Check if job is already completed or failed
        if job.status in ['completed', 'failed', 'partial_complete']:
             logger.warning(f"Task {task_id}: Job {job_id} already in terminal state '{job.status}'. Skipping.")
             self.update_state(state='SUCCESS', meta={'details': f'Job already completed or failed ({job.status}).'})
             return {'status': 'skipped', 'reason': f'Job already in state {job.status}', 'processed': 0, 'failed': 0}

        # --- Update Job Status to Processing ---
        logger.info(f"Task {task_id}: Updating job {job_id} status to 'processing'.")
        # TODO: Ensure crud_ingestion_job.update_job_status exists
        crud_ingestion_job.update_job_status(db=db, job_id=job_id, status='processing')
        self.update_state(state='STARTED', meta={'details': 'Job status set to processing.'})

        # --- Fetch and Update Relevant S3SyncItems ---
        logger.info(f"Task {task_id}: Fetching and marking relevant S3SyncItems as processing.")
        # TODO: Implement crud_s3_sync_item.get_and_mark_pending_items_for_job
        # This function needs to find S3SyncItems matching the job's criteria (user, bucket, key/prefix)
        # with status 'pending' and update their status to 'processing'.
        # It should return the list of items it successfully marked.
        # This prevents race conditions if multiple workers/tasks pick up the same logical job.
        try:
            s3_bucket = job.job_details.get('bucket')
            s3_key_or_prefix = job.job_details.get('key') or job.job_details.get('prefix')
            if not s3_bucket or not s3_key_or_prefix:
                 raise ValueError("Missing bucket or key/prefix in job_details")

            pending_sync_items = crud_s3_sync_item.get_and_mark_pending_items_for_job(
                db=db,
                user_email=user_email,
                bucket=s3_bucket,
                key_or_prefix=s3_key_or_prefix
            )
            if not pending_sync_items:
                 logger.warning(f"Task {task_id}: No pending S3SyncItems found matching job criteria for job {job_id}. Job may be redundant or items already processed/failed.")
                 # Proceed, but _process_s3_to_r2_and_db will likely find 0 items to process based on the map.
                 # Consider setting job to completed immediately?
                 # Let's allow processing to continue; it will handle the empty set.

            # Create a map for easy lookup during processing
            sync_items_map: Dict[Tuple[str, str], S3SyncItem] = {
                (item.s3_bucket, item.s3_key): item for item in pending_sync_items
            }
            logger.info(f"Task {task_id}: Marked {len(pending_sync_items)} S3SyncItems as 'processing'.")

        except Exception as sync_item_err:
             err_msg = f"Task {task_id}: Failed to fetch or mark S3SyncItems for job {job_id}: {sync_item_err}"
             logger.error(err_msg, exc_info=True)
             crud_ingestion_job.update_job_status(db=db, job_id=job_id, status='failed', error_message="Failed to prepare sync items.")
             self.update_state(state='FAILURE', meta={'details': err_msg})
             raise

        # --- Assume Role ---
        logger.info(f"Task {task_id}: Obtaining AWS session for user {user_email}")
        self.update_state(state='PROGRESS', meta={'current_step': 'authentication', 'details': 'Authenticating with AWS...'})
        try:
            # Use the existing service function
            # TODO: Ensure s3_service.get_aws_session_for_user exists and is async or handled correctly
            aws_session = asyncio.run(s3_service.get_aws_session_for_user(db=db, user_email=user_email))
            s3_client = aws_session.client('s3')
            logger.info(f"Task {task_id}: Successfully obtained assumed role session.")
        except NoCredentialsError as e:
             err_msg = f"Task {task_id}: AWS NoCredentialsError for user {user_email}. Ensure credentials (Role ARN) are configured correctly. {e}"
             logger.error(err_msg, exc_info=True)
             crud_ingestion_job.update_job_status(db=db, job_id=job_id, status='failed', error_message="AWS credentials configuration error.")
             # Fail associated sync items
             for item in pending_sync_items: crud_s3_sync_item.update_item_status(db=db, db_item=item, status='failed')
             self.update_state(state='FAILURE', meta={'details': err_msg})
             raise # Re-raise to fail task
        except ClientError as e:
             error_code = e.response.get('Error', {}).get('Code')
             err_msg = f"Task {task_id}: AWS ClientError during authentication for user {user_email} (Code: {error_code}): {e}"
             logger.error(err_msg, exc_info=True)
             crud_ingestion_job.update_job_status(db=db, job_id=job_id, status='failed', error_message=f"AWS authentication failed: {error_code}")
             # Fail associated sync items
             for item in pending_sync_items: crud_s3_sync_item.update_item_status(db=db, db_item=item, status='failed')
             self.update_state(state='FAILURE', meta={'details': err_msg})
             raise # Re-raise to fail task
        except Exception as e:
            err_msg = f"Task {task_id}: Failed to assume role or get credentials for user {user_email}: {e}"
            logger.error(err_msg, exc_info=True)
            crud_ingestion_job.update_job_status(db=db, job_id=job_id, status='failed', error_message=f"AWS authentication failed: {e}")
            # Fail associated sync items
            for item in pending_sync_items: crud_s3_sync_item.update_item_status(db=db, db_item=item, status='failed')
            self.update_state(state='FAILURE', meta={'details': err_msg})
            raise # Re-raise to fail task

        # --- Get R2 Client ---
        logger.info(f"Task {task_id}: Obtaining R2 client.")
        # Use property or direct call
        # TODO: Ensure self.r2_client works and r2_service.get_r2_client is implemented
        r2_client = self.r2_client

        # --- Run Core Processing Logic ---
        logger.info(f"Task {task_id}: Starting core processing logic for job {job_id}.")
        # Run the async helper function using asyncio.run within the sync Celery task
        processed_count, failed_count = asyncio.run(
            _process_s3_to_r2_and_db(
                task_instance=self,
                db_session=db,
                job=job,
                sync_items_map=sync_items_map, # Pass the map
                s3_client=s3_client,
                r2_client=r2_client
            )
        )

        # --- Update Final Job Status ---
        final_status = 'unknown' # Default
        final_message = f"Processed {processed_count} files, failed {failed_count} files."
        if failed_count > 0 and processed_count > 0:
            final_status = 'partial_complete'
        elif failed_count > 0 and processed_count == 0:
            # Check if there were any sync items initially - if not, maybe 'completed' is better?
            if not pending_sync_items and failed_count == 0 : # Handles case where job started but found no pending items initially
                 final_status = 'completed'
                 final_message = "No pending sync items found for this job."
            else:
                final_status = 'failed'
                final_message = f"All {failed_count} files/items failed during processing."
        elif failed_count == 0 and processed_count >= 0: # Handles 0 found files case too
             final_status = 'completed'
             final_message = f"Successfully processed {processed_count} files."

        logger.info(f"Task {task_id}: Updating job {job_id} final status to '{final_status}'. Processed: {processed_count}, Failed: {failed_count}")
        crud_ingestion_job.update_job_status(db=db, job_id=job_id, status=final_status, error_message=None if final_status == 'completed' else final_message)

        # --- COMMIT TRANSACTION ---
        logger.info(f"Task {task_id}: Committing database transaction for job {job_id}.")
        db.commit() # Commit all changes made in the session

        self.update_state(state='SUCCESS' if final_status in ['completed', 'partial_complete'] else 'FAILURE', meta={'details': final_message, 'processed': processed_count, 'failed': failed_count})
        logger.info(f"Task {task_id}: Database transaction committed successfully for job {job_id}.")
        return {'status': final_status, 'processed': processed_count, 'failed': failed_count}

    except Exception as e:
        task_id = self.request.id if self.request else "UNKNOWN_TASK"
        job_id_str = str(job_id) if 'job_id' in locals() else "UNKNOWN_JOB"
        err_msg = f"Task {task_id}: Unhandled exception processing job {job_id_str}: {e}"
        logger.error(err_msg, exc_info=True)

        # --- ROLLBACK TRANSACTION ---
        if db: # Check if session was created
            try:
                logger.warning(f"Task {task_id}: Rolling back database transaction for job {job_id_str} due to error.")
                db.rollback()
            except Exception as rb_err:
                logger.error(f"Task {task_id}: CRITICAL - Failed to rollback transaction for job {job_id_str}: {rb_err}", exc_info=True)

        # Attempt to update job status to failed (this might fail if rollback occurred, but worth trying for visibility)
        # This update happens *after* rollback, so it requires a separate commit if we want it persisted.
        # For simplicity, we'll just log the failure state here. The main rollback handles data consistency.
        # (Original logic to update status after rollback removed for clarity, as it won't persist without a new commit)

        self.update_state(state='FAILURE', meta={'details': err_msg})
        raise e # Re-raise the exception so Celery knows the task failed

    # Note: The db.close() in after_return will still run, which is fine.

# TODO: Ensure all referenced CRUD functions exist and have the correct signatures:
# - crud_ingestion_job.get_ingestion_job(db, job_id)
# - crud_ingestion_job.update_job_status(db, job_id, status, error_message=None)
# - crud_s3_sync_item.get_and_mark_pending_items_for_job(db, user_email, bucket, key_or_prefix) -> List[S3SyncItem]
# - crud_s3_sync_item.update_item_status(db, db_item, status)
# - crud_processed_file.create_processed_file_entry(db, file_data: ProcessedFile)
# TODO: Ensure R2 service functions exist:
# - r2_service.get_r2_client() -> R2 Client instance
# - r2_service.upload_fileobj_to_r2(r2_client, file_obj, bucket, object_key, content_type)
# - Define or import r2_service.R2UploadError
# TODO: Confirm settings.R2_BUCKET_NAME is correct.

# TODO: Ensure all referenced CRUD functions exist and have the correct signatures:
# - crud_ingestion_job.get_ingestion_job(db, job_id)
# - crud_ingestion_job.update_job_status(db, job_id, status, error_message=None)
# - crud_s3_sync_item.get_and_mark_pending_items_for_job(db, user_email, bucket, key_or_prefix) -> List[S3SyncItem]
# - crud_s3_sync_item.update_item_status(db, db_item, status)
# - crud_processed_file.create_processed_file_entry(db, file_data: ProcessedFile)
# TODO: Ensure R2 service functions exist:
# - r2_service.get_r2_client() -> R2 Client instance
# - r2_service.upload_fileobj_to_r2(r2_client, file_obj, bucket, object_key, content_type)
# - Define or import r2_service.R2UploadError
# TODO: Confirm settings.R2_BUCKET_NAME is correct. 