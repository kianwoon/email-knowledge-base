# backend/app/tasks/azure_tasks.py
import logging
import uuid
from typing import List, Tuple, Dict, Optional, Any
import base64 # Import base64
import asyncio
import json # Import json
import os # ADDED: Import os module

from celery import Task
from sqlalchemy.orm import Session
# Remove Qdrant imports
# from qdrant_client import QdrantClient
# from qdrant_client import models as qdrant_models
# Import Milvus
from pymilvus import MilvusClient
from app.db.milvus_client import get_milvus_client, ensure_collection_exists

from app.db.session import SessionLocal
from app.celery_app import celery_app
from app.config import settings
from app.models.azure_blob_sync_item import AzureBlobSyncItem
from app.crud import crud_azure_blob_sync_item, crud_azure_blob, user_crud
from app.services.azure_blob_service import AzureBlobService
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
            crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='processing')

            data_dict_to_add: Optional[Dict[str, Any]] = None # Renamed point_to_add
            data_dicts_for_prefix: List[Dict[str, Any]] = [] # Renamed points_for_prefix
            item_processed_successfully = False # Track if data dicts were generated for this item

            if item.item_type == 'blob':
                # No need to download content for raw storage
                # blob_content_bytes = await azure_service.download_blob_content(item.container_name, item.item_path)
                # if blob_content_bytes:
                #     content_b64 = base64.b64encode(blob_content_bytes).decode('utf-8')
                point_id = str(uuid.uuid4()) # Generate PK
                metadata = { 
                    "azure_connection_id": str(item.connection_id),
                    "container": item.container_name,
                    "path": item.item_path,
                    "filename": item.item_name,
                    "analysis_status": "pending"
                }
                metadata = {k: v for k, v in metadata.items() if v is not None}

                data_dict_to_add = {
                    "pk": point_id,
                    "vector": zero_vector,
                    "owner": user_email,
                    "source": "azure_blob",
                    "type": "azure_blob_knowledge",
                    "email_id": user_email,
                    "job_id": task_id,
                    "subject": item.item_name, # Use filename as subject
                    "date": "", # Azure service doesn't easily provide this, use empty string
                    "status": "processed",
                    "folder": os.path.dirname(item.item_path) if item.item_path else "",
                    "metadata_json": metadata # Store the dict
                }
                item_processed_successfully = True
                # else:
                #     logger.warning(f"Task {task_id}: No content downloaded for blob {item.item_path}. Skipping.")
            
            elif item.item_type == 'prefix':
                blobs_under_prefix = await azure_service.list_blobs(item.container_name, item.item_path)
                for blob_info in blobs_under_prefix:
                    if not blob_info.get('isDirectory'):
                        blob_path = blob_info.get('path'); blob_name = blob_info.get('name')
                        if not blob_path or not blob_name: continue
                        # No download needed
                        # blob_content_bytes = await azure_service.download_blob_content(item.container_name, blob_path)
                        # if blob_content_bytes:
                        #    content_b64 = base64.b64encode(blob_content_bytes).decode('utf-8')
                        point_id = str(uuid.uuid4())
                        metadata = { 
                            "azure_connection_id": str(item.connection_id),
                            "container": item.container_name,
                            "path": blob_path,
                            "filename": blob_name,
                            "analysis_status": "pending"
                        }
                        metadata = {k: v for k, v in metadata.items() if v is not None}
                        
                        data_dict_for_blob = {
                            "pk": point_id,
                            "vector": zero_vector,
                            "owner": user_email,
                            "source": "azure_blob",
                            "type": "azure_blob_knowledge",
                            "email_id": user_email,
                            "job_id": task_id,
                            "subject": blob_name,
                            "date": "", # Use empty string
                            "status": "processed",
                            "folder": os.path.dirname(blob_path) if blob_path else "",
                            "metadata_json": metadata
                        }
                        data_dicts_for_prefix.append(data_dict_for_blob)
                        # else:
                        #     logger.warning(f"Task {task_id}: No content downloaded for blob {blob_path} under prefix. Skipping.")
                if data_dicts_for_prefix:
                     data_for_connection.extend(data_dicts_for_prefix)
                     logger.info(f"Task {task_id}: Generated {len(data_dicts_for_prefix)} data dicts for prefix item {item.id} ('{item.item_path}')")
                     item_processed_successfully = True # Mark prefix as processed if it yielded points
                else:
                     logger.info(f"Task {task_id}: No processable blobs found under prefix item {item.id} ('{item.item_path}').")

            if data_dict_to_add:
                data_for_connection.append(data_dict_to_add)
                logger.info(f"Task {task_id}: Generated 1 data dict for blob item {item.id} ('{item.item_path}')")
                item_processed_successfully = True
            
            crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='completed')
            processed_count += 1
            logger.info(f"Task {task_id}: Completed processing item {item.id}")
        
        except Exception as item_err:
            failed_count += 1
            logger.error(f"Task {task_id}: Failed processing item {item.id} ('{item.item_path}'): {item_err}", exc_info=True)
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
        # Generate collection name prefix from email, replacing special chars
        if user.email:
            safe_email_prefix = user.email.replace('@', '_').replace('.', '_')
        else:
            # Fallback if email is somehow missing (shouldn't happen for Azure/MS users)
            safe_email_prefix = str(user.id) 
        collection_name = f"{safe_email_prefix}_azure_blob_knowledge"
        logger.info(f"Task {task_id}: Target Milvus collection: {collection_name}")
        
        # Use ensure_collection_exists helper for Milvus
        try: 
            ensure_collection_exists(milvus_client, collection_name, settings.DENSE_EMBEDDING_DIMENSION)
            logger.info(f"Task {task_id}: Ensured Milvus collection '{collection_name}' exists.")
        except Exception as q_err: # Keep variable name for now
            raise Exception(f'Milvus check/create failed: {q_err}') # Updated message

        # 2. Get Pending Items
        # Fetch pending items for *all* connections for this user
        logger.info(f"Task {task_id}: Fetching pending sync items for user {user_id} (all connections)") # Updated log message
        pending_items = crud_azure_blob_sync_item.get_items_by_user_and_connection(
            db, 
            user_id=user_id, 
            connection_id=None, # Explicitly pass None to fetch for all connections
            status_filter=['pending'] # Use correct function name and list for status
        )
        total_items = len(pending_items)
        logger.info(f"Task {task_id}: Found {total_items} pending item(s).")
        if not pending_items:
             logger.info(f"Task {task_id}: No pending Azure sync items found for user {user_id}. Task complete.")
             return {"status": "COMPLETE", "message": "No pending items.", "processed": 0, "failed": 0}
        logger.info(f"Task {task_id}: Found {len(pending_items)} pending items.")

        # Group items by connection_id (Corrected initialization)
        items_by_connection: Dict[uuid.UUID, List[AzureBlobSyncItem]] = {}
        for item in pending_items:
            if item.connection_id not in items_by_connection:
                items_by_connection[item.connection_id] = []
            items_by_connection[item.connection_id].append(item)
        
        # Use DENSE_EMBEDDING_DIMENSION from settings for placeholder
        zero_vector = [0.0] * settings.DENSE_EMBEDDING_DIMENSION

        # 3. Process Items per Connection
        for conn_id, items in items_by_connection.items():
            logger.info(f"Task {task_id}: Processing connection {conn_id}...")
            # Fetch connection object and decrypted credential separately
            # connection = crud_azure_blob.get_connection_with_decrypted_credentials(db, connection_id=conn_id, user_id=user_id)
            result = crud_azure_blob.get_connection_with_decrypted_credentials(db, connection_id=conn_id, user_id=user_id)
            
            if not result:
                logger.error(f"Task {task_id}: Connection {conn_id} not found or decryption failed. Skipping {len(items)} items.")
                cumulative_failed += len(items)
                # Mark items as failed (ensure db_item is passed correctly)
                for item in items:
                    try:
                        crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                    except Exception as status_err:
                         logger.error(f"Task {task_id}: Failed marking item {item.id} as failed: {status_err}")
                continue
            
            # Unpack the result
            connection_obj, decrypted_connection_string = result

            if not decrypted_connection_string:
                 # Should be caught by CRUD func, but safety check
                 logger.error(f"Task {task_id}: Decrypted connection string is empty for connection {conn_id}. Skipping items.")
                 cumulative_failed += len(items)
                 # Mark items as failed
                 for item in items:
                     try: crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                     except Exception as status_err: logger.error(f"Task {task_id}: Failed marking item {item.id} as failed: {status_err}")
                 continue

            try:
                # Initialize service with the decrypted string
                async with AzureBlobService(connection_string=decrypted_connection_string) as azure_service:
                    # Await the helper
                    data_dicts, processed, failed = await _process_items_for_connection(
                        azure_service, items, db, task_id, zero_vector, user.email # Pass user email
                    )
                    all_data_to_insert.extend(data_dicts)
                    cumulative_processed += processed
                    cumulative_failed += failed
            except Exception as conn_err:
                logger.error(f"Task {task_id}: Error processing connection {conn_id}: {conn_err}", exc_info=True)
                cumulative_failed += len(items) # Assume all failed
                # Mark failed (sync) - Corrected try/except format
                for item in items:
                    try:
                        # Ensure we only try to mark items not already completed/failed
                        if item.status == 'pending' or item.status == 'processing': 
                            crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                    except Exception as status_err:
                        logger.error(f"Task {task_id}: Failed marking item {item.id} as failed: {status_err}")
                continue # Continue to next connection

        # 4. Insert into Milvus (sync)
        if all_data_to_insert:
            logger.info(f"Task {task_id}: Inserting {len(all_data_to_insert)} data points into Milvus...")
            # Insert logic (remains sync)
            try:
                BATCH_SIZE = 100
                for i in range(0, len(all_data_to_insert), BATCH_SIZE):
                    batch = all_data_to_insert[i:i + BATCH_SIZE]
                    milvus_client.insert(collection_name=collection_name, data=batch)
                logger.info(f"Task {task_id}: Milvus insert successful.")
            except Exception as insert_err:
                raise Exception(f'Milvus insert failed: {insert_err}') # Re-raise for sync wrapper
        else:
             logger.info(f"Task {task_id}: No data to insert into Milvus.")
        
        # 5. Determine final status and message
        final_status = 'COMPLETE' if cumulative_failed == 0 else 'PARTIAL_COMPLETE'
        final_message = f"Azure Blob ingestion finished. Processed: {cumulative_processed}, Failed: {cumulative_failed}."
        logger.info(f"Task {task_id}: {final_message}")
        
        return {
            'status': final_status,
            'message': final_message,
            'processed': cumulative_processed,
            'failed': cumulative_failed
        }

    # Catch all exceptions within the async logic to return error info
    except Exception as e:
        logger.error(f"Task {task_id}: Unhandled error in async logic: {e}", exc_info=True)
        # Calculate failed count correctly in case of error before processing starts
        num_pending = len(pending_items) if pending_items else 0
        failed_in_exception = num_pending - cumulative_processed
        # Return error details for the sync wrapper to handle
        return {
            "status": "FAILED", 
            "message": str(e), 
            "processed": cumulative_processed, 
            "failed": cumulative_failed + failed_in_exception
        }
    finally:
        # Close DB session opened within this async function
        db.close()


# NEW Synchronous Celery Task Wrapper
@celery_app.task(bind=True, name="tasks.azure.process_ingestion", max_retries=3, default_retry_delay=60)
def process_azure_ingestion_task(self: Task, user_id_str: str):
    """Synchronous Celery task wrapper that runs the async Azure Blob ingestion logic."""
    logger.info(f"Task {self.request.id}: Received Azure Blob ingestion request for user ID {user_id_str}. Running async logic...")
    self.update_state(state='STARTED', meta={'progress': 0, 'status': 'Initializing...'}) # Initial state update

    try:
        # Run the async function using asyncio.run()
        # Pass the task ID for logging within the async function
        result = asyncio.run(_execute_azure_ingestion_logic(user_id_str=user_id_str, task_id=self.request.id))

        # Update final state based on the result from the async function
        final_meta = {
            'progress': 100, 
            'status': str(result.get('status', 'UNKNOWN')),
            'message': str(result.get('message', 'Async execution finished.')),
            'processed': int(result.get('processed', 0)),
            'failed': int(result.get('failed', 0))
        }
        final_celery_state = 'SUCCESS' if result.get('status') in ['COMPLETE', 'PARTIAL_COMPLETE'] else 'FAILURE'
        
        logger.info(f"Task {self.request.id}: Async logic completed. Final state: {final_celery_state}, Meta: {final_meta}")
        self.update_state(state=final_celery_state, meta=final_meta)
        return final_meta # Return the result dictionary

    except Exception as e:
        # Catch exceptions raised *during* asyncio.run or potentially by the async logic itself if not caught internally
        error_message = f"Error in synchronous wrapper or during async execution: {e}"
        logger.error(f"Task {self.request.id}: {error_message}", exc_info=True)
        try:
            # Attempt to update state to FAILURE
            failure_meta = {'error': str(e), 'progress': 0}
            self.update_state(state='FAILURE', meta=failure_meta)
        except Exception as state_update_error:
            logger.error(f"Task {self.request.id}: Furthermore, failed to update task state to FAILURE: {state_update_error}")
        # Propagate the error for Celery retry logic
        raise self.retry(exc=e) # Retry with the original exception 