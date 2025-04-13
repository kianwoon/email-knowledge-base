# backend/app/tasks/s3_tasks.py
import logging
import base64
import asyncio
from typing import List, Dict, Any, Tuple, Optional, Set
import uuid
from datetime import datetime, timezone
import os

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session
import boto3
from botocore.exceptions import ClientError

from ..celery_app import celery_app
from ..config import settings
from app.services import s3 as s3_service # For AssumeRole logic
from app.db.qdrant_client import get_qdrant_client
from app.crud import crud_aws_credential, crud_s3_sync_item # To get Role ARN and CRUD operations
from app.db.session import SessionLocal, get_db
from app.db.models.s3_sync_item import S3SyncItem # Model import

# Qdrant imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

logger = get_task_logger(__name__)

def generate_s3_qdrant_collection_name(user_email: str) -> str:
    """Generates a sanitized, user-specific Qdrant collection name for S3."""
    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    return f"{sanitized_email}_aws_s3_knowledge"

# Define a namespace for generating UUIDs based on S3 objects
S3_NAMESPACE_UUID = uuid.UUID('a5b8e4a1-7c4f-4d1a-8b0e-3f4d1a7c4f0d') # Example random namespace

def generate_s3_qdrant_point_id(bucket: str, key: str) -> str:
    """Generates a deterministic Qdrant UUID point ID from the S3 bucket and key."""
    unique_id_string = f"s3://{bucket}/{key}"
    return str(uuid.uuid5(S3_NAMESPACE_UUID, unique_id_string))

async def _list_all_objects_recursive(s3_client, bucket: str, prefix: str, task_instance: Task, user_email: str) -> List[Dict[str, Any]]:
    """Recursively lists all objects under a given prefix, handling pagination."""
    objects = []
    continuation_token = None
    initial_status_msg = f'Discovering files in s3://{bucket}/{prefix}...'
    task_instance.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 15, 'status': initial_status_msg})
    logger.info(f"Task {task_instance.request.id}: {initial_status_msg}")

    while True:
        try:
            list_kwargs = {'Bucket': bucket, 'Prefix': prefix}
            if continuation_token:
                list_kwargs['ContinuationToken'] = continuation_token
            
            # Use async equivalent if available, otherwise run sync in thread?
            # For now, assuming sync call is acceptable within Celery task context
            # or that the s3_client is already configured for async via aioboto3 if used.
            # Let's proceed with standard boto3 sync for now.
            response = s3_client.list_objects_v2(**list_kwargs)

            if 'Contents' in response:
                for obj in response['Contents']:
                    # Skip zero-byte objects that often represent folders implicitly
                    if obj.get('Size') == 0 and obj['Key'].endswith('/'):
                        continue
                    objects.append({
                        'key': obj['Key'],
                        'last_modified': obj.get('LastModified'),
                        'size': obj.get('Size')
                    })
            
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
                logger.debug(f"Task {task_instance.request.id}: Paginating object list for prefix '{prefix}'")
            else:
                break # Exit loop if not truncated
        except ClientError as e:
            logger.error(f"Task {task_instance.request.id}: Error listing objects in s3://{bucket}/{prefix}: {e}", exc_info=True)
            # Decide how to handle partial failure - return what we have?
            raise e # Re-raise for now to fail the specific branch
        except Exception as e:
            logger.error(f"Task {task_instance.request.id}: Unexpected error listing objects in s3://{bucket}/{prefix}: {e}", exc_info=True)
            raise e
            
    logger.info(f"Task {task_instance.request.id}: Discovered {len(objects)} potential objects under prefix '{prefix}'")
    return objects

class S3ProcessingTask(Task):
    _db: Optional[Session] = None
    _qdrant_client: Optional[QdrantClient] = None
    # No persistent service needed as session is per-task via AssumeRole

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self._db:
            self._db.close()
            logger.debug(f"Task {task_id}: DB session closed.")

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def qdrant_client(self) -> QdrantClient:
        if self._qdrant_client is None:
            logger.debug(f"Task {self.request.id}: Getting Qdrant client instance.")
            self._qdrant_client = get_qdrant_client()
        return self._qdrant_client

async def _run_s3_processing_logic(
    task_instance: Task,
    db_session: Session,
    user_email: str,
    pending_sync_items: List[S3SyncItem]
) -> Tuple[int, int, List[models.PointStruct]]:
    """Orchestrates fetching, processing, and preparing S3 data for Qdrant based on pending sync items."""
    task_id = task_instance.request.id
    points_to_upsert: List[models.PointStruct] = []
    total_processed_count = 0
    total_failed_count = 0
    # Map S3 key to its corresponding sync item DB ID for easy status updates
    sync_item_map: Dict[Tuple[str, str], S3SyncItem] = {(item.s3_bucket, item.s3_key): item for item in pending_sync_items}

    if not pending_sync_items:
        logger.info(f"Task {task_id}: No pending S3 sync items found for user {user_email}. Nothing to process.")
        return 0, 0, []

    # --- Group keys by bucket for efficient AssumeRole and S3 client usage ---
    keys_by_bucket: Dict[str, List[str]] = {}
    for item in pending_sync_items:
        if item.s3_bucket not in keys_by_bucket:
            keys_by_bucket[item.s3_bucket] = []
        keys_by_bucket[item.s3_bucket].append(item.s3_key)
    
    logger.info(f"Task {task_id}: Found {len(pending_sync_items)} pending sync items across {len(keys_by_bucket)} bucket(s) for user {user_email}.")

    # --- Assume Role (once per task is sufficient) ---
    logger.info(f"Task {task_id}: Getting AWS credentials for user {user_email}")
    task_instance.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 5, 'status': 'Authenticating with AWS...'})
    try:
        role_arn = s3_service.get_user_aws_credentials(db=db_session, user_email=user_email)
        aws_session = s3_service.get_aws_session_for_user(role_arn=role_arn, user_email=user_email)
        s3_client = aws_session.client('s3')
        logger.info(f"Task {task_id}: Successfully assumed role {role_arn}")
    except Exception as e:
        logger.error(f"Task {task_id}: Failed to assume role or get credentials: {e}", exc_info=True)
        # Fail all pending items if auth fails
        for item in pending_sync_items:
            try:
                crud_s3_sync_item.update_item_status(db=db_session, db_item=item, status='failed')
            except Exception as update_err:
                logger.error(f"Task {task_id}: CRITICAL - Failed to update sync item {item.id} to failed status after auth error: {update_err}", exc_info=True)
        raise ValueError(f"AWS authentication failed: {e}") # Fail task

    # --- Expand Prefixes and Collect Final File Keys/Metadata --- 
    task_instance.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 10, 'status': 'Discovering files...'})
    all_object_metadata: List[Dict[str, Any]] = []
    initial_failed_keys: Set[Tuple[str, str]] = set() # Track (bucket, key) pairs that failed initial metadata fetch

    for bucket, keys_or_prefixes in keys_by_bucket.items():
        logger.info(f"Task {task_id}: Discovering objects in bucket '{bucket}' for {len(keys_or_prefixes)} initial keys/prefixes...")
        discovery_tasks = []
        for key_or_prefix in keys_or_prefixes:
            if key_or_prefix.endswith('/'): # Prefix
                discovery_tasks.append(
                    _list_all_objects_recursive(s3_client, bucket, key_or_prefix, task_instance, user_email)
                )
            else: # Specific file key
                try:
                    head = s3_client.head_object(Bucket=bucket, Key=key_or_prefix)
                    all_object_metadata.append({
                        'bucket': bucket, # Store bucket with metadata
                        'key': key_or_prefix,
                        'last_modified': head.get('LastModified'),
                        'size': head.get('ContentLength'),
                        'content_type': head.get('ContentType')
                    })
                except ClientError as e:
                    logger.error(f"Task {task_id}: Failed to get metadata for specific key s3://{bucket}/{key_or_prefix}: {e}", exc_info=True)
                    initial_failed_keys.add((bucket, key_or_prefix))
                except Exception as e:
                    logger.error(f"Task {task_id}: Unexpected error getting metadata for key s3://{bucket}/{key_or_prefix}: {e}", exc_info=True)
                    initial_failed_keys.add((bucket, key_or_prefix))
                    
        # Process prefix discovery tasks for the current bucket
        if discovery_tasks:
            results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task {task_id}: Prefix discovery failed in bucket {bucket}: {result}", exc_info=result)
                    # Cannot easily map this back to a specific sync item ID, mark general failure?
                    # For now, log and continue, individual file processing will handle failures.
                elif isinstance(result, list):
                    # Add bucket info to metadata from recursive calls
                    all_object_metadata.extend([{**meta, 'bucket': bucket} for meta in result])
                else:
                    logger.warning(f"Task {task_id}: Unexpected result type from prefix discovery: {type(result)}")

    # --- Deduplicate final list using a dictionary keyed by (bucket, key) --- 
    unique_objects_dict: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for obj_meta in all_object_metadata:
        bucket = obj_meta.get('bucket')
        key = obj_meta.get('key')
        if bucket and key:
            unique_objects_dict[(bucket, key)] = obj_meta # Overwrite duplicates
        else:
            logger.warning(f"Task {task_id}: Found object metadata without bucket or key: {obj_meta}")
            
    final_objects_to_process = list(unique_objects_dict.values())
    total_files_to_process = len(final_objects_to_process)
    
    # Update status for items that failed initial metadata fetch
    for bucket, key in initial_failed_keys:
        sync_item = sync_item_map.get((bucket, key))
        if sync_item:
            try:
                crud_s3_sync_item.update_item_status(db=db_session, db_item=sync_item, status='failed')
                total_failed_count += 1
            except Exception as update_err:
                 logger.error(f"Task {task_id}: CRITICAL - Failed to update sync item {sync_item.id} to failed status after metadata error: {update_err}", exc_info=True)
        else:
            logger.warning(f"Task {task_id}: Sync item not found in map for initially failed key s3://{bucket}/{key}")

    logger.info(f"Task {task_id}: Total unique files to process: {total_files_to_process}. Initial failures recorded: {len(initial_failed_keys)}")
    if total_files_to_process == 0:
        # Ensure any remaining 'processing' items (e.g., prefixes that yielded no files) are marked failed?
        # Or maybe completed if no files found is expected?
        # For now, just return the counts. The task caller handles overall status.
        return total_processed_count, total_failed_count, points_to_upsert

    # --- Process Each Unique File --- 
    current_file_num = 0
    for obj_meta in final_objects_to_process:
        current_file_num += 1
        obj_bucket = obj_meta['bucket']
        obj_key = obj_meta['key']
        obj_filename = os.path.basename(obj_key)
        progress_percent = 15 + int(80 * (current_file_num / total_files_to_process))
        logger.info(f"Task {task_id}: Processing file {current_file_num}/{total_files_to_process}: s3://{obj_bucket}/{obj_key}")
        task_instance.update_state(state='PROGRESS', meta={'user': user_email, 'progress': progress_percent, 'status': f'Processing {current_file_num}/{total_files_to_process}: {obj_filename[:30]}...'})

        # Find the original sync item(s) that led to this object key
        # A file might result from a specific file sync item OR a prefix sync item
        # We only need to update ONE sync item if multiple prefixes covered the same file.
        # Let's find the most specific one (file > prefix) or just the first found.
        target_sync_item = sync_item_map.get((obj_bucket, obj_key)) # Check direct file match first
        if not target_sync_item:
            # Find if it falls under any 'prefix' type sync items
            for (item_bucket, item_key), sync_item in sync_item_map.items():
                if item_bucket == obj_bucket and sync_item.item_type == 'prefix' and obj_key.startswith(item_key):
                    # Found a matching prefix. If the prefix item is still 'processing', use it.
                    # We assume the status update logic below handles marking it complete/failed.
                    target_sync_item = sync_item # Use the prefix item for status update
                    break # Take the first matching prefix

        if not target_sync_item:
             logger.warning(f"Task {task_id}: Could not find corresponding SyncItem in map for processed file s3://{obj_bucket}/{obj_key}. Skipping status update for this file.")
             # Continue processing the file for Qdrant, but we can't update the DB status

        file_processed_successfully = False
        try:
            # 1. Ensure full metadata (if not already fetched)
            if 'content_type' not in obj_meta:
                try:
                    head = s3_client.head_object(Bucket=obj_bucket, Key=obj_key)
                    obj_meta['last_modified'] = head.get('LastModified')
                    obj_meta['size'] = head.get('ContentLength')
                    obj_meta['content_type'] = head.get('ContentType')
                except ClientError as e:
                    logger.error(f"Task {task_id}: Failed getting metadata for s3://{obj_bucket}/{obj_key} during processing: {e}", exc_info=True)
                    raise # Re-raise to mark file as failed

            # 2. Download content
            logger.debug(f"Task {task_id}: Downloading s3://{obj_bucket}/{obj_key}")
            get_object_response = s3_client.get_object(Bucket=obj_bucket, Key=obj_key)
            file_content_bytes = get_object_response['Body'].read()
            logger.debug(f"Task {task_id}: Downloaded {len(file_content_bytes)} bytes for {obj_key}")
            
            # 3. Base64 encode
            content_b64 = base64.b64encode(file_content_bytes).decode('utf-8')

            # 4. Prepare Qdrant payload
            payload = {
                "source": "s3",
                "s3_bucket": obj_bucket,
                "s3_key": obj_key,
                "original_filename": obj_filename,
                "user_email": user_email,
                "last_modified": obj_meta.get('last_modified').isoformat() if obj_meta.get('last_modified') else None,
                "content_type": obj_meta.get('content_type'),
                "size": obj_meta.get('size'),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "analysis_status": "pending",
                "content_b64": content_b64
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            # 5. Prepare Qdrant point
            point_id = generate_s3_qdrant_point_id(obj_bucket, obj_key)
            vector_size = settings.EMBEDDING_DIMENSION
            placeholder_vector = [0.0] * vector_size # Use 0.0 for S3 placeholder

            point = models.PointStruct(
                id=point_id,
                vector=placeholder_vector,
                payload=payload
            )
            points_to_upsert.append(point)
            total_processed_count += 1
            file_processed_successfully = True

        except Exception as file_err:
            logger.error(f"Task {task_id}: Failed processing file s3://{obj_bucket}/{obj_key}: {file_err}", exc_info=True)
            total_failed_count += 1
            file_processed_successfully = False

        # Update DB status for the corresponding sync item
        if target_sync_item:
            try:
                new_status = 'completed' if file_processed_successfully else 'failed'
                # Avoid redundant updates if status is already terminal
                if target_sync_item.status not in ['completed', 'failed']:
                    crud_s3_sync_item.update_item_status(db=db_session, db_item=target_sync_item, status=new_status)
                    logger.info(f"Task {task_id}: Updated status for SyncItem {target_sync_item.id} (s3://{obj_bucket}/{obj_key}) to {new_status}")
                else:
                    logger.debug(f"Task {task_id}: SyncItem {target_sync_item.id} already in terminal state '{target_sync_item.status}'. Skipping update for file s3://{obj_bucket}/{obj_key}.")
            except Exception as update_err:
                logger.error(f"Task {task_id}: CRITICAL - Failed to update sync item {target_sync_item.id} status for file s3://{obj_bucket}/{obj_key}: {update_err}", exc_info=True)
                # Continue processing other files

    # Final check: Mark any original 'prefix' items that are still 'processing' as 'completed'
    # This handles cases where a prefix was added but contained no processable files.
    for item in pending_sync_items:
        # Refresh item from DB to get the latest status after file processing loops
        db_session.refresh(item)
        if item.item_type == 'prefix' and item.status == 'processing':
            try:
                crud_s3_sync_item.update_item_status(db=db_session, db_item=item, status='completed')
                logger.info(f"Task {task_id}: Marked empty/fully-processed prefix SyncItem {item.id} (s3://{item.s3_bucket}/{item.s3_key}) as completed.")
            except Exception as final_update_err:
                 logger.error(f"Task {task_id}: Failed final status update for prefix SyncItem {item.id}: {final_update_err}", exc_info=True)

    return total_processed_count, total_failed_count, points_to_upsert

@celery_app.task(bind=True, base=S3ProcessingTask, name='tasks.s3.process_ingestion')
def process_s3_ingestion_task(self: Task, user_email: str):
    """Processes pending S3 sync items for a user."""
    task_id = self.request.id
    logger.info(f"Starting S3 ingestion task {task_id} for user {user_email}")
    self.update_state(state='STARTED', meta={'user': user_email, 'progress': 0, 'status': 'Initializing...'})

    qdrant_client: QdrantClient = self.qdrant_client # Get from Task base class property
    db: Session = self.db # Get from Task base class property
    collection_name = generate_s3_qdrant_collection_name(user_email)
    total_processed = 0
    total_failed = 0
    pending_sync_items: List[S3SyncItem] = []

    try:
        # 1. Fetch pending items from DB
        logger.info(f"Task {task_id}: Fetching pending S3 sync items for user {user_email}...")
        pending_sync_items = crud_s3_sync_item.get_pending_items_by_user(db=db, user_id=user_email)
        if not pending_sync_items:
             logger.info(f"Task {task_id}: No pending S3 sync items found for user {user_email}. Task finished.")
             self.update_state(state='SUCCESS', meta={'user': user_email, 'progress': 100, 'status': 'No items to process.', 'processed': 0, 'failed': 0})
             return {'status': 'SUCCESS', 'message': 'No pending items found.', 'processed': 0, 'failed': 0}

        # 2. Mark items as 'processing'
        logger.info(f"Task {task_id}: Marking {len(pending_sync_items)} items as 'processing'...")
        self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 1, 'status': f'Preparing {len(pending_sync_items)} items...'})
        processed_ids_for_status_update = []
        try:
            for item in pending_sync_items:
                crud_s3_sync_item.update_item_status(db=db, db_item=item, status='processing')
                processed_ids_for_status_update.append(item.id)
        except Exception as status_update_err:
            logger.error(f"Task {task_id}: Failed to update initial status to 'processing': {status_update_err}", exc_info=True)
            # Attempt to revert status for successfully updated items? Complex.
            # For now, fail the whole task if we can't even mark as processing.
            raise Exception(f"Failed to mark items as processing: {status_update_err}")

        # 3. Ensure Qdrant collection exists (create/recreate)
        logger.info(f"Task {task_id}: Ensuring collection '{collection_name}'.")
        self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 3, 'status': 'Preparing knowledge base...'})
        try:
            qdrant_client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=settings.EMBEDDING_DIMENSION, distance=models.Distance.COSINE)
            )
            logger.info(f"Task {task_id}: Collection '{collection_name}' created/recreated.")
        except (UnexpectedResponse, Exception) as e:
            logger.error(f"Task {task_id}: Failed to create/recreate Qdrant collection '{collection_name}': {e}", exc_info=True)
            # Mark items back to failed?
            for item_id in processed_ids_for_status_update:
                item = db.query(S3SyncItem).get(item_id)
                if item: crud_s3_sync_item.update_item_status(db=db, db_item=item, status='failed')
            raise Exception(f"Qdrant collection setup failed: {e}")

        # 4. Run the main processing logic (async part)
        # Use asyncio.run() to execute the async helper from the sync task function
        total_processed, total_failed, points_to_upsert = asyncio.run(
             _run_s3_processing_logic(
                task_instance=self,
                db_session=db, # Pass the session
                user_email=user_email,
                pending_sync_items=pending_sync_items # Pass the DB items
            )
        )
        
        # 5. Upsert points to Qdrant (if any)
        if points_to_upsert:
            logger.info(f"Task {task_id}: Upserting {len(points_to_upsert)} points to '{collection_name}'.")
            self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 95, 'status': f'Saving {len(points_to_upsert)} items to knowledge base...'})
            try:
                qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points_to_upsert,
                    wait=True # Wait for operation to complete
                )
                logger.info(f"Task {task_id}: Successfully upserted points.")
            except Exception as e:
                logger.error(f"Task {task_id}: Failed to upsert points to Qdrant collection '{collection_name}': {e}", exc_info=True)
                # Mark all successfully processed items as failed because upsert failed?
                # This is tricky. For now, log error, but report counts as processed.
                # The status in the DB reflects file processing success/failure.
                # Mark task as failed overall?
                raise Exception(f"Qdrant upsert failed: {e}") # Fail task
        else:
            logger.info(f"Task {task_id}: No points to upsert.")

        # 6. Final status update
        final_message = f"Ingestion complete. Processed: {total_processed}, Failed: {total_failed}."
        logger.info(f"Task {task_id}: {final_message}")
        self.update_state(state='SUCCESS', meta={'user': user_email, 'progress': 100, 'status': final_message, 'processed': total_processed, 'failed': total_failed})
        return {'status': 'COMPLETED', 'message': final_message, 'processed': total_processed, 'failed': total_failed}

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        # Attempt to mark any items still 'processing' as 'failed'
        try:
            if pending_sync_items: # Only if we fetched some initially
                 processing_items = db.query(S3SyncItem).filter(
                    S3SyncItem.user_id == user_email,
                    S3SyncItem.status == 'processing'
                 ).all()
                 for item in processing_items:
                    crud_s3_sync_item.update_item_status(db=db, db_item=item, status='failed')
                 logger.info(f"Task {task_id}: Marked {len(processing_items)} items as 'failed' due to task exception.")
        except Exception as cleanup_err:
            logger.error(f"Task {task_id}: Error during failure cleanup: {cleanup_err}", exc_info=True)
            
        # Use self.update_state for Celery failure state
        self.update_state(
            state='FAILURE', 
            meta={'user': user_email, 'progress': 0, 'status': f'Task failed: {e}', 'exc_type': type(e).__name__, 'exc_message': str(e)}
        )
        # Return error info for result backend
        return {'status': 'FAILED', 'message': str(e), 'processed': total_processed, 'failed': total_failed} 