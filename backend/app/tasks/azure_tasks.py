# backend/app/tasks/azure_tasks.py
import logging
import uuid
from typing import List, Tuple, Dict, Optional, Any
import pathlib # Added pathlib
import asyncio
import os # Standard os import

from celery import Task
from sqlalchemy.orm import Session
# Remove Qdrant imports
# from qdrant_client import QdrantClient
# from qdrant_client import models as qdrant_models
# Import Milvus
from pymilvus import MilvusClient
from app.db.milvus_client import get_milvus_client, ensure_collection_exists
from starlette.concurrency import run_in_threadpool # Added import

from app.db.session import SessionLocal
from app.celery_app import celery_app
from app.config import settings
from app.models.azure_blob_sync_item import AzureBlobSyncItem # Reverted model import path
from app.crud import crud_azure_blob_sync_item, crud_azure_blob, user_crud # Updated CRUD import path
from app.services.azure_blob_service import AzureBlobService
from app.services import s3 as s3_service # Import s3_service for R2 upload
# Remove embedding/processing imports if no longer needed
# from app.services.embeddings import EmbeddingsClient 
# from app.services.file_processing import process_file_content 

logger = logging.getLogger(__name__)

# Remove Qdrant client helper
# def get_qdrant_client() -> QdrantClient:
#     # Helper to get Qdrant client instance based on settings
#     return QdrantClient(
#         url=settings.QDRANT_URL,
#         api_key=settings.QDRANT_API_KEY,
#         timeout=60 # Increase timeout for potentially large uploads
#     )

# Remove get_embeddings_client if not used
# def get_embeddings_client() -> EmbeddingsClient:
#    ...

# NEW: Define a namespace for generating UUIDs based on Azure Blob objects
AZURE_BLOB_NAMESPACE_UUID = uuid.UUID('b6e3f8a2-8d5e-4c1b-9f7d-4e2a8b0d5f1b') # Example random namespace for Azure

# NEW: Helper function to generate Milvus collection name for Azure
def generate_azure_blob_milvus_collection_name(user_email: str) -> str:
    """Generates a sanitized, user-specific Milvus collection name for Azure Blob."""
    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    return f"{sanitized_email}_azure_blob_knowledge"

# NEW: Helper function to generate deterministic Milvus PK for Azure Blob
def generate_azure_blob_milvus_pk(container: str, blob_path: str) -> str:
    """Generates a deterministic Milvus UUID PK from the Azure container and blob path."""
    unique_id_string = f"azure://{container}/{blob_path}"
    return str(uuid.uuid5(AZURE_BLOB_NAMESPACE_UUID, unique_id_string))

# NEW: Helper function to process items for a single connection
async def _process_items_for_connection(
    azure_service: AzureBlobService, 
    items: List[AzureBlobSyncItem], 
    db: Session, 
    task_id: str, 
    zero_vector: List[float],
    user_email: str # Added user_email
) -> Tuple[List[Dict[str, Any]], int, int]: # Updated return type hint
    """Processes a list of sync items for a single Azure connection, preparing Milvus data dicts."""
    data_for_connection: List[Dict[str, Any]] = [] # Renamed points_for_connection
    processed_count = 0
    failed_count = 0

    for item in items:
        try:
            logger.info(f"Task {task_id}: Processing item {item.id}: {item.item_type} - {item.container_name}/{item.item_path}")
            # Note: update_state is called from the main task, not here, to avoid complex state passing
            # Mark as processing only if it's currently pending
            if item.status == 'pending':
                crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='processing')

            data_dicts_to_add: List[Dict[str, Any]] = []
            item_processed_successfully = False # Track if data dicts were generated for this item
            
            blobs_to_process: List[Dict[str, str]] = [] # List of {'container': c, 'path': p, 'name': n}

            # 1. Identify Blobs to Process (handles both 'blob' and 'prefix' items)
            if item.item_type == 'blob':
                blobs_to_process.append({
                    'container': item.container_name,
                    'path': item.item_path,
                    'name': item.item_name
                })
            elif item.item_type == 'prefix':
                blobs_under_prefix = await azure_service.list_blobs(item.container_name, item.item_path)
                for blob_info in blobs_under_prefix:
                    if not blob_info.get('isDirectory'):
                        blob_path = blob_info.get('path')
                        blob_name = blob_info.get('name')
                        if blob_path and blob_name:
                            blobs_to_process.append({
                                'container': item.container_name, # Use container from the item
                                'path': blob_path,
                                'name': blob_name
                            })

            # 2. Process Each Identified Blob
            if not blobs_to_process:
                 logger.info(f"Task {task_id}: No blobs found for item {item.id} ('{item.item_path}').")
                 item_processed_successfully = True # Mark as success if prefix/blob yielded nothing
            else:
                logger.info(f"Task {task_id}: Found {len(blobs_to_process)} blob(s) to process for item {item.id}.")
                all_blobs_in_item_succeeded = True # Assume success until a blob fails
                
                for blob_meta in blobs_to_process:
                    blob_container = blob_meta['container']
                    blob_path = blob_meta['path']
                    blob_name = blob_meta['name']
                    r2_object_key_for_milvus: Optional[str] = None
                    blob_processed_successfully = False
                    
                    try:
                        # 2a. Download Blob Content
                        logger.debug(f"Task {task_id}: Downloading content for azure://{blob_container}/{blob_path}")
                        blob_content_bytes = await azure_service.download_blob_content(blob_container, blob_path)
                        if not blob_content_bytes:
                             logger.warning(f"Task {task_id}: No content downloaded for blob {blob_path}. Skipping.")
                             # This blob failed, but don't necessarily fail the whole item yet
                             all_blobs_in_item_succeeded = False
                             continue # Skip to the next blob within the item
                        logger.debug(f"Task {task_id}: Downloaded {len(blob_content_bytes)} bytes from azure://{blob_container}/{blob_path}")

                        # 2b. Upload content to R2
                        logger.debug(f"Task {task_id}: Attempting upload to R2.")
                        milvus_pk = generate_azure_blob_milvus_pk(blob_container, blob_path)
                        original_extension = "".join(pathlib.Path(blob_name).suffixes)
                        generated_r2_key = f"azure_blob/{milvus_pk}{original_extension}"
                        target_r2_bucket = settings.R2_BUCKET_NAME
                        
                        logger.info(f"Task {task_id}: Uploading copy as '{generated_r2_key}' to R2 Bucket '{target_r2_bucket}'")
                        upload_successful = await run_in_threadpool(
                            s3_service.upload_bytes_to_r2,
                            bucket_name=target_r2_bucket,
                            object_key=generated_r2_key,
                            data_bytes=blob_content_bytes
                        )
                        
                        if upload_successful:
                            r2_object_key_for_milvus = generated_r2_key
                            logger.info(f"Task {task_id}: Upload to R2 successful. Object Key: {r2_object_key_for_milvus}")
                        else:
                            logger.error(f"Task {task_id}: Failed to upload copy of azure://{blob_container}/{blob_path} to R2.")
                            raise Exception("Failed to upload file copy to R2 storage.") 

                        # 2c. Prepare Milvus Payload
                        metadata_payload = { 
                            "azure_connection_id": str(item.connection_id),
                            "container": blob_container,
                            "path": blob_path,
                            "original_filename": blob_name, # Use 'original_filename'
                            # Add other relevant Azure metadata if needed/available (e.g., last_modified, size)
                            # "last_modified": blob_info.get('lastModified')?.isoformat(), 
                            # "size": blob_info.get('contentLength'),
                        }
                        metadata_payload = {k: v for k, v in metadata_payload.items() if v is not None}

                        data_dict_for_blob = {
                            "pk": milvus_pk,
                            "vector": zero_vector,
                            "owner": user_email,
                            "source": "azure_blob",
                            "type": "azure_blob_knowledge",
                            "email_id": user_email,
                            "job_id": task_id,
                            "subject": blob_name,
                            "date": "", # Placeholder for date
                            "status": "pending", # Initial status in Milvus is pending
                            "folder": os.path.dirname(blob_path) if blob_path else "",
                            "analysis_status": "pending", # Add field
                            "r2_object_key": r2_object_key_for_milvus, # Add field
                            "metadata_json": metadata_payload
                        }
                        data_dicts_to_add.append(data_dict_for_blob)
                        blob_processed_successfully = True

                    except Exception as blob_proc_err:
                        logger.error(f"Task {task_id}: Failed processing blob azure://{blob_container}/{blob_path} within item {item.id}: {blob_proc_err}", exc_info=True)
                        all_blobs_in_item_succeeded = False # Mark item as failed if any blob fails
                        # No need to 'continue' here, loop will proceed
                
                # Determine item success based on blob processing results
                item_processed_successfully = all_blobs_in_item_succeeded

            # 3. Update Item Status & Collect Results
            if item_processed_successfully:
                # Add generated data dicts for this item to the connection's list
                if data_dicts_to_add:
                    data_for_connection.extend(data_dicts_to_add)
                    logger.info(f"Task {task_id}: Generated {len(data_dicts_to_add)} data dict(s) for item {item.id} ('{item.item_path}')")
                else:
                    # This happens if a prefix yielded no blobs, which is considered success
                    logger.info(f"Task {task_id}: Item {item.id} ('{item.item_path}') processed successfully but generated no data dicts (e.g., empty prefix).")
                
                # Update DB status to completed only if it was processing
                if item.status == 'processing':
                     crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='completed')
                processed_count += 1
                logger.info(f"Task {task_id}: Completed processing item {item.id}")
            else:
                # If any blob failed, mark the whole item as failed
                failed_count += 1
                logger.error(f"Task {task_id}: Failed processing item {item.id} ('{item.item_path}') due to errors with one or more blobs.")
                # Update DB status to failed only if it was processing
                if item.status == 'processing':
                    try:
                        crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                    except Exception as status_update_err:
                        logger.error(f"Task {task_id}: Additionally failed to mark item {item.id} as failed: {status_update_err}")
        
        except Exception as item_err: # Catch errors occurring before blob processing loop starts
            failed_count += 1
            logger.error(f"Task {task_id}: Failed processing item {item.id} ('{item.item_path}') early: {item_err}", exc_info=True)
            if item.status == 'processing': # Check status before attempting update
                 try:
                     crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                 except Exception as status_update_err:
                      logger.error(f"Task {task_id}: Additionally failed to mark item {item.id} as failed: {status_update_err}")
    
    return data_for_connection, processed_count, failed_count


# Renamed async function containing the core logic
async def _execute_azure_ingestion_logic(user_id_str: str, task_id: str):
    """Core async logic for Azure Blob ingestion."""
    logger.info(f"Task {task_id}: Starting async Azure Blob ingestion logic for user ID {user_id_str}")
    user_id = uuid.UUID(user_id_str)
    db: Session = SessionLocal()
    milvus_client = get_milvus_client() # Get Milvus client
    cumulative_processed = 0
    cumulative_failed = 0
    all_data_to_insert: List[Dict[str, Any]] = [] # Renamed
    final_status = "UNKNOWN" # Default status
    final_message = "Task did not complete fully." # Default message
    pending_items = None # Initialize pending_items

    try:
        # 1. Get User Info & Setup Milvus Collection
        user = user_crud.get_user_by_id(db, user_id=user_id)
        if not user:
            logger.error(f"Task {task_id}: User {user_id} not found.")
            # Cannot update state here, return specific error info
            return {"status": "FAILED", "message": "User not found.", "processed": 0, "failed": 0}
        
        # Ensure user has an email
        if not user.email:
             logger.error(f"Task {task_id}: User {user_id} has no email address. Cannot generate collection name.")
             return {"status": "FAILED", "message": "User email is missing.", "processed": 0, "failed": 0}

        collection_name = generate_azure_blob_milvus_collection_name(user.email)
        logger.info(f"Task {task_id}: Target Milvus collection: {collection_name}")
        
        # Use ensure_collection_exists helper for Milvus
        try: 
            ensure_collection_exists(milvus_client, collection_name, settings.DENSE_EMBEDDING_DIMENSION)
            logger.info(f"Task {task_id}: Ensured Milvus collection '{collection_name}' exists.")
        except Exception as q_err: # Keep variable name for now
            raise Exception(f'Milvus check/create failed: {q_err}') # Updated message

        # 2. Get Pending Items
        logger.info(f"Task {task_id}: Fetching pending sync items for user {user_id} (all connections)") # Updated log message
        pending_items = crud_azure_blob_sync_item.get_items_by_user_and_connection(
            db, 
            user_id=user_id, 
            connection_id=None, 
            status_filter=['pending']
        )
        total_items = len(pending_items)
        logger.info(f"Task {task_id}: Found {total_items} pending item(s).")
        if not pending_items:
             logger.info(f"Task {task_id}: No pending Azure sync items found for user {user_id}. Task complete.")
             return {"status": "COMPLETE", "message": "No pending items.", "processed": 0, "failed": 0}
        
        # Group items by connection_id
        items_by_connection: Dict[uuid.UUID, List[AzureBlobSyncItem]] = {}
        for item in pending_items:
            if item.connection_id not in items_by_connection:
                items_by_connection[item.connection_id] = []
            items_by_connection[item.connection_id].append(item)
        
        zero_vector = [0.0] * settings.DENSE_EMBEDDING_DIMENSION

        # 3. Process Items per Connection
        for conn_id, items in items_by_connection.items():
            logger.info(f"Task {task_id}: Processing connection {conn_id} with {len(items)} item(s)...")
            result = crud_azure_blob.get_connection_with_decrypted_credentials(db, connection_id=conn_id, user_id=user_id)
            
            if not result:
                logger.error(f"Task {task_id}: Connection {conn_id} not found or decryption failed. Skipping {len(items)} items.")
                cumulative_failed += len(items)
                for item in items:
                    try:
                        # Mark as failed only if pending (no need to check processing as it wasn't started)
                        if item.status == 'pending': 
                             crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                    except Exception as status_err:
                         logger.error(f"Task {task_id}: Failed marking item {item.id} as failed: {status_err}")
                continue
            
            connection_obj, decrypted_connection_string = result

            if not decrypted_connection_string:
                 logger.error(f"Task {task_id}: Decrypted connection string is empty for connection {conn_id}. Skipping items.")
                 cumulative_failed += len(items)
                 for item in items:
                     if item.status == 'pending':
                         try: crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                         except Exception as status_err: logger.error(f"Task {task_id}: Failed marking item {item.id} as failed: {status_err}")
                 continue

            try:
                async with AzureBlobService(connection_string=decrypted_connection_string) as azure_service:
                    data_dicts, processed, failed = await _process_items_for_connection(
                        azure_service, items, db, task_id, zero_vector, user.email # Pass user email
                    )
                    all_data_to_insert.extend(data_dicts)
                    cumulative_processed += processed
                    cumulative_failed += failed
            except Exception as conn_err:
                logger.error(f"Task {task_id}: Error processing connection {conn_id}: {conn_err}", exc_info=True)
                # Calculate how many items were associated with this connection attempt
                num_items_in_failed_connection = len(items)
                # Mark associated items as failed (only if they haven't reached a terminal state)
                failed_in_conn = 0
                for item in items:
                    try:
                        # Check if item was left in 'pending' or 'processing'
                        if item.status == 'pending' or item.status == 'processing': 
                            crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                            failed_in_conn += 1
                    except Exception as status_err:
                        logger.error(f"Task {task_id}: Failed marking item {item.id} as failed after connection error: {status_err}")
                # Add the count of newly failed items to the cumulative total
                cumulative_failed += failed_in_conn 
                # Don't add to cumulative_processed as these items didn't succeed
                continue # Continue to next connection

        # 4. Insert into Milvus (sync)
        if all_data_to_insert:
            logger.info(f"Task {task_id}: Inserting {len(all_data_to_insert)} data points into Milvus collection '{collection_name}'...")
            try:
                BATCH_SIZE = 100 # Or get from settings
                for i in range(0, len(all_data_to_insert), BATCH_SIZE):
                    batch = all_data_to_insert[i:i + BATCH_SIZE]
                    insert_result = milvus_client.insert(collection_name=collection_name, data=batch)
                    # logger.debug(f"Task {task_id}: Inserted batch {i//BATCH_SIZE + 1}, result PKs: {insert_result.primary_keys}")
                    # Updated log message to avoid accessing potentially missing attribute
                    logger.debug(f"Task {task_id}: Inserted batch {i//BATCH_SIZE + 1}. Result type: {type(insert_result)}") 
                logger.info(f"Task {task_id}: Milvus insert successful for {len(all_data_to_insert)} points.")
            except Exception as insert_err:
                logger.error(f"Task {task_id}: Milvus insert failed: {insert_err}", exc_info=True)
                # If insert fails, we need to mark the DB items corresponding to the *successfully processed* blobs as failed
                # This is complex because we only have the list of data dicts. 
                # A simpler approach for now: mark ALL originally pending items as failed if Milvus fails.
                logger.warning(f"Task {task_id}: Attempting to mark all originally pending items as failed due to Milvus insert error.")
                failed_after_insert_error = 0
                for item in pending_items: # Iterate over original list
                     # Refresh item to get current status
                    db.refresh(item)
                    if item.status == 'completed': # Only revert items marked completed
                        try:
                            crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                            failed_after_insert_error += 1
                        except Exception as revert_err:
                            logger.error(f"Task {task_id}: Failed reverting item {item.id} status after Milvus error: {revert_err}")
                cumulative_failed = total_items # Set failed count to total
                cumulative_processed = 0 # Reset processed count
                raise Exception(f'Milvus insert failed: {insert_err}') # Re-raise to fail the task
        else:
             logger.info(f"Task {task_id}: No data to insert into Milvus.")
        
        # 5. Determine final status and message
        if total_items > 0: # Avoid division by zero if no items initially
            if cumulative_failed == 0:
                final_status = 'COMPLETE'
            elif cumulative_processed > 0:
                final_status = 'PARTIAL_COMPLETE'
            else:
                final_status = 'FAILED'
        else:
             final_status = 'COMPLETE' # If no items, it's complete
             
        final_message = f"Azure Blob ingestion finished. Processed: {cumulative_processed}, Failed: {cumulative_failed} out of {total_items} initial items."
        logger.info(f"Task {task_id}: {final_message}")
        
        return {
            'status': final_status,
            'message': final_message,
            'processed': cumulative_processed,
            'failed': cumulative_failed
        }

    except Exception as e:
        logger.error(f"Task {task_id}: Unhandled error in async logic: {e}", exc_info=True)
        # Mark any remaining 'processing' items as failed
        remaining_failed_count = 0
        if pending_items: # Ensure we have the list
            try:
                processing_items = db.query(AzureBlobSyncItem).filter(
                    AzureBlobSyncItem.user_id == user_id,
                    AzureBlobSyncItem.status == 'processing'
                ).all()
                for item in processing_items:
                    crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                    remaining_failed_count += 1
                logger.info(f"Task {task_id}: Marked {remaining_failed_count} items as 'failed' due to task exception.")
            except Exception as cleanup_err:
                 logger.error(f"Task {task_id}: Error during failure cleanup: {cleanup_err}", exc_info=True)
                 
        # Calculate final failed count more accurately
        total_failed_on_error = cumulative_failed + remaining_failed_count
        
        return {
            "status": "FAILED", 
            "message": str(e), 
            "processed": cumulative_processed, 
            "failed": total_failed_on_error 
        }
    finally:
        db.close()


# Synchronous Celery Task Wrapper (mostly unchanged, relies on async logic's return values)
@celery_app.task(bind=True, name="tasks.azure.process_ingestion", max_retries=3, default_retry_delay=60)
def process_azure_ingestion_task(self: Task, user_id_str: str):
    """Synchronous Celery task wrapper that runs the async Azure Blob ingestion logic."""
    logger.info(f"Task {self.request.id}: Received Azure Blob ingestion request for user ID {user_id_str}. Running async logic...")
    self.update_state(state='STARTED', meta={'progress': 0, 'status': 'Initializing...'}) # Initial state update

    try:
        result = asyncio.run(_execute_azure_ingestion_logic(user_id_str=user_id_str, task_id=self.request.id))

        final_meta = {
            'progress': 100, 
            'status': str(result.get('status', 'UNKNOWN')), # Use the status returned by async logic
            'message': str(result.get('message', 'Async execution finished.')),
            'processed': int(result.get('processed', 0)),
            'failed': int(result.get('failed', 0))
        }
        # Determine Celery state based on the detailed status from async logic
        if result.get('status') == 'COMPLETE':
            final_celery_state = 'SUCCESS'
        elif result.get('status') == 'PARTIAL_COMPLETE':
            final_celery_state = 'SUCCESS' # Treat partial as success for Celery, detail is in meta
        else: # FAILED or UNKNOWN
            final_celery_state = 'FAILURE' 
        
        logger.info(f"Task {self.request.id}: Async logic completed. Final state: {final_celery_state}, Meta: {final_meta}")
        self.update_state(state=final_celery_state, meta=final_meta)
        return final_meta

    except Exception as e:
        error_message = f"Error in synchronous wrapper or during async execution: {e}"
        logger.error(f"Task {self.request.id}: {error_message}", exc_info=True)
        try:
            failure_meta = {
                'error': str(e), 
                'progress': 0, 
                'status': 'FAILURE',
                'message': error_message,
                'processed': 0, # Assume 0 processed if error in wrapper
                'failed': 'Unknown' # Can't know failed count if wrapper fails early
                }
            self.update_state(state='FAILURE', meta=failure_meta)
        except Exception as state_update_error:
            logger.error(f"Task {self.request.id}: Furthermore, failed to update task state to FAILURE: {state_update_error}")
        # Propagate the error for Celery retry logic
        # Check if the exception is a retryable one if needed
        # For now, retry on any exception from the wrapper/asyncio.run
        raise self.retry(exc=e) # Retry with the original exception 