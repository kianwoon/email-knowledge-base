import logging
import base64
import asyncio
from typing import List, Dict, Any, Tuple

from celery import Task
from celery.utils.log import get_task_logger

from ..celery_app import celery_app
from ..config import settings
from app.services.sharepoint import SharePointService # Assuming exists and can be initialized with token
from app.db.qdrant_client import get_qdrant_client
from app.crud import user_crud # To get user tokens if needed indirectly
from app.db.session import SessionLocal # For getting user tokens
from app.utils.security import decrypt_token # For user tokens

# Qdrant imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

logger = get_task_logger(__name__)

def generate_qdrant_collection_name(user_email: str) -> str:
    """Generates a sanitized, user-specific Qdrant collection name."""
    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    return f"{sanitized_email}_sharepoint_knowledge"

def generate_qdrant_point_id(sharepoint_item_id: str) -> str:
    """Generates a deterministic Qdrant point ID from the SharePoint item ID."""
    return f"sharepoint-{sharepoint_item_id}"

async def _recursively_get_files_from_folder(service: SharePointService, drive_id: str, folder_id: str, processed_ids: set) -> List[Dict[str, Any]]:
    """Helper to recursively fetch file items within a folder, avoiding cycles/duplicates."""
    files = []
    if folder_id in processed_ids: # Basic cycle detection
        logger.warning(f"Skipping already processed folder ID: {folder_id}")
        return files
    processed_ids.add(folder_id)

    try:
        items = await service.list_drive_items(drive_id=drive_id, item_id=folder_id)
        tasks = []
        for item in items:
            if item.id in processed_ids:
                continue
                
            if item.folder:
                # Recurse for sub-folders
                tasks.append(
                    _recursively_get_files_from_folder(service, drive_id, item.id, processed_ids)
                )
            elif item.file:
                # Add file details
                processed_ids.add(item.id)
                files.append({
                    "sharepoint_item_id": item.id,
                    "item_name": item.name,
                    "sharepoint_drive_id": drive_id
                })
        
        # Process sub-folder results
        if tasks:
            results = await asyncio.gather(*tasks)
            for sub_files in results:
                files.extend(sub_files)

    except Exception as e:
        logger.error(f"Error listing items in folder {folder_id} of drive {drive_id}: {e}", exc_info=True)
    return files

class SharePointProcessingTask(Task):
    _db = None
    _qdrant_client = None
    _sharepoint_service = None # Service instance per task potentially

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        # Close DB session if opened
        if self._db:
            self._db.close()
            logger.debug(f"Task {task_id}: DB session closed.")
        # Cleanup other resources if necessary

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def qdrant_client(self) -> QdrantClient:
        if self._qdrant_client is None:
            logger.debug(f"Task {self.request.id}: Getting Qdrant client instance.")
            self._qdrant_client = get_qdrant_client()
        return self._qdrant_client

    def get_sharepoint_service(self, user_email: str) -> SharePointService:
        """Gets or creates a SharePoint service instance, requires fetching user token."""
        if self._sharepoint_service is None:
            logger.debug(f"Task {self.request.id}: Initializing SharePoint service for {user_email}.")
            # Fetch user token from DB - requires DB session
            db_user = user_crud.get_user_full_instance(db=self.db, email=user_email)
            if not db_user or not db_user.ms_access_token:
                 # Note: Access token might be stale, refresh logic might be needed here or in SharePointService
                 # For simplicity now, assume a valid access token is stored.
                 # A better approach might involve storing and refreshing the refresh token.
                 logger.error(f"Task {self.request.id}: Cannot get access token for user {user_email} to init SP service.")
                 raise ValueError(f"Missing access token for user {user_email}.")
            
            # Decrypting might not be needed if access token isn't encrypted
            # access_token = decrypt_token(db_user.ms_access_token) if db_user.ms_access_token else None
            access_token = db_user.ms_access_token # Assuming it's stored directly for now
            
            if not access_token:
                raise ValueError(f"Access token unavailable for user {user_email}.")
                
            self._sharepoint_service = SharePointService(access_token)
        return self._sharepoint_service

async def _run_processing_logic(
    task_instance: Task, 
    sp_service: SharePointService,
    items_to_process: List[Dict[str, Any]],
    user_email: str
) -> Tuple[int, int, List[models.PointStruct]]:
    """Orchestrates the async fetching and processing of files."""
    task_id = task_instance.request.id
    all_files_to_process: List[Dict[str, Any]] = []
    processed_item_ids = set() # Track all processed IDs (files and folders)
    total_failed_discovery = 0

    # --- Expand Folders to Files (Async) --- 
    logger.info(f"Task {task_id}: Expanding folders...")
    folder_expansion_tasks = []
    for item in items_to_process:
        item_id = item['sharepoint_item_id']
        if item_id in processed_item_ids:
            continue
            
        if item.get('item_type') == 'folder':
            logger.info(f"Task {task_id}: Queuing expansion for folder '{item.get('item_name')}' (ID: {item_id})")
            folder_expansion_tasks.append(
                 _recursively_get_files_from_folder(sp_service, item['sharepoint_drive_id'], item_id, processed_item_ids)
            )
            processed_item_ids.add(item_id) # Mark folder as processed
        elif item.get('item_type') == 'file':
             if item_id not in processed_item_ids:
                 all_files_to_process.append(item)
                 processed_item_ids.add(item_id)
        else:
            logger.warning(f"Task {task_id}: Skipping item {item_id} with unknown type: {item.get('item_type')}")

    # Run folder expansions concurrently
    if folder_expansion_tasks:
        results = await asyncio.gather(*folder_expansion_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task {task_id}: Folder expansion failed: {result}", exc_info=result)
                total_failed_discovery += 1 # Count failure
            elif isinstance(result, list):
                # Add successfully retrieved file details
                for file_detail in result:
                     if file_detail['sharepoint_item_id'] not in processed_item_ids:
                         all_files_to_process.append(file_detail)
                         processed_item_ids.add(file_detail['sharepoint_item_id'])
            else:
                 logger.warning(f"Task {task_id}: Unexpected result type from folder expansion: {type(result)}")

    total_files = len(all_files_to_process)
    logger.info(f"Task {task_id}: Total files to process after expansion: {total_files}. Discovery failures: {total_failed_discovery}")
    if total_files == 0:
        return 0, total_failed_discovery, [] # Processed, Failed, Points

    # --- Process Each File (Async Downloads) --- 
    points_to_upsert: List[models.PointStruct] = []
    total_processed_files = 0
    total_failed_files = total_failed_discovery # Start with discovery failures
    current_file_num = 0
    
    # Process files, potentially in chunks or concurrently if desired/safe
    for file_info in all_files_to_process:
        current_file_num += 1
        file_id = file_info['sharepoint_item_id']
        file_name = file_info.get('item_name', 'Unknown Name')
        drive_id = file_info['sharepoint_drive_id']
        progress_percent = 10 + int(80 * (current_file_num / total_files))
        logger.info(f"Task {task_id}: Processing file {current_file_num}/{total_files}: '{file_name}' (ID: {file_id})")
        task_instance.update_state(state='PROGRESS', meta={'user': user_email, 'progress': progress_percent, 'status': f'Processing file {current_file_num}/{total_files}: {file_name[:30]}...'})

        try:
            # Await file download
            file_content_bytes = await sp_service.download_file(drive_id=drive_id, item_id=file_id)

            if file_content_bytes is None:
                logger.warning(f"Task {task_id}: No content for file {file_id}. Skipping.")
                total_failed_files += 1
                continue
            
            encoded_content = base64.b64encode(file_content_bytes).decode('utf-8')
            
            payload = {
                "file_name": file_name,
                "sharepoint_id": file_id,
                "drive_id": drive_id,
                "item_type": "file",
                "content_b64": encoded_content,
                "analysis_status": "pending"
            }
            
            point = models.PointStruct(
                id=generate_qdrant_point_id(file_id),
                payload=payload,
            )
            points_to_upsert.append(point)
            total_processed_files += 1

        except Exception as file_proc_err:
            logger.error(f"Task {task_id}: Failed processing file {file_id}: {file_proc_err}", exc_info=True)
            total_failed_files += 1
            task_instance.update_state(state='PROGRESS', meta={'user': user_email, 'progress': progress_percent, 'status': f'Failed file {current_file_num}/{total_files}: {file_name[:30]}...'})
            
    return total_processed_files, total_failed_files, points_to_upsert

@celery_app.task(bind=True, base=SharePointProcessingTask, name='tasks.sharepoint.process_batch')
def process_sharepoint_batch_task(self: Task, items_to_process: List[Dict[str, Any]], user_email: str):
    task_id = self.request.id
    logger.info(f"Starting SharePoint batch task {task_id} for user {user_email} ({len(items_to_process)} items).")
    self.update_state(state='STARTED', meta={'user': user_email, 'progress': 0, 'status': 'Initializing...'})

    qdrant_client = self.qdrant_client
    target_collection_name = generate_qdrant_collection_name(user_email)
    total_processed = 0
    total_failed = 0

    try:
        # --- Ensure Qdrant Collection Exists --- 
        logger.info(f"Task {task_id}: Ensuring collection '{target_collection_name}'.")
        self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 5, 'status': 'Checking collection...'})
        try:
            qdrant_client.create_collection(
                collection_name=target_collection_name,
                vectors_config=models.VectorParams(size=settings.EMBEDDING_DIMENSION, distance=models.Distance.COSINE)
            )
            logger.info(f"Task {task_id}: Collection '{target_collection_name}' created.")
        except UnexpectedResponse as e:
            if e.status_code == 400 and "already exists" in str(e.content).lower() or e.status_code == 409:
                 logger.warning(f"Task {task_id}: Collection '{target_collection_name}' already exists.")
            else: raise
        except Exception as create_err: raise create_err

        # --- Get SharePoint Service --- 
        sp_service = self.get_sharepoint_service(user_email)
        logger.info(f"Task {task_id}: SharePoint service initialized.")
        self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 10, 'status': 'Discovering files...'})

        # --- Run Async Logic --- 
        # Use asyncio.run() to execute the async helper function
        total_processed, total_failed, points_to_upsert = asyncio.run(
            _run_processing_logic(
                task_instance=self, 
                sp_service=sp_service, 
                items_to_process=items_to_process,
                user_email=user_email
            )
        )

        # --- Batch Upsert to Qdrant --- 
        logger.info(f"Task {task_id}: Upserting {len(points_to_upsert)} points.")
        self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 95, 'status': 'Saving data...'})
        if points_to_upsert:
            try:
                qdrant_client.upsert(
                    collection_name=target_collection_name, 
                    points=points_to_upsert, wait=True
                )
                logger.info(f"Task {task_id}: Qdrant upsert successful.")
            except Exception as upsert_err:
                logger.error(f"Task {task_id}: Qdrant upsert failed: {upsert_err}", exc_info=True)
                total_failed += len(points_to_upsert) # Count these as failed
                self.update_state(state='FAILURE', meta={'user': user_email, 'progress': 98, 'status': 'Failed to save data.'})
                return {'status': 'ERROR', 'message': f'Failed final save: {upsert_err}', 'processed': total_processed, 'failed': total_failed}

        # --- Final Task State --- 
        final_status_msg = f"Completed. Processed: {total_processed}, Failed: {total_failed}."
        logger.info(f"Task {task_id}: {final_status_msg}")
        final_state = 'SUCCESS' if total_failed == 0 else 'PARTIAL_FAILURE'
        self.update_state(state=final_state, meta={'user': user_email, 'progress': 100, 'status': final_status_msg, 'result': {'processed': total_processed, 'failed': total_failed}})
        return {'status': final_state, 'message': final_status_msg, 'processed': total_processed, 'failed': total_failed}

    except Exception as task_err:
        logger.critical(f"Task {task_id}: Unhandled exception: {task_err}", exc_info=True)
        self.update_state(state='FAILURE', meta={'user': user_email, 'progress': 100, 'status': f'Critical task error: {task_err}'})
        raise 