import logging
import base64
import asyncio
from typing import List, Dict, Any, Tuple, Optional
import uuid
from datetime import datetime, timedelta, timezone

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from ..celery_app import celery_app
from ..config import settings
from app.services.sharepoint import SharePointService # Assuming exists and can be initialized with token
from app.db.qdrant_client import get_qdrant_client
from app.crud import user_crud # To get user tokens if needed indirectly
from app.db.session import SessionLocal # For getting user tokens
from app.utils.security import decrypt_token # For user tokens
from app.crud import crud_sharepoint_sync_item # Import sync item CRUD and model
from app.db.models.sharepoint_sync_item import SharePointSyncItem as SharePointSyncItemDBModel # Import SharePointSyncItem model
from .email_tasks import get_msal_app # CORRECTED Import from the sibling email_tasks module

# Qdrant imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

logger = get_task_logger(__name__)

def generate_qdrant_collection_name(user_email: str) -> str:
    """Generates a sanitized, user-specific Qdrant collection name."""
    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    return f"{sanitized_email}_sharepoint_knowledge"

# Define a namespace for generating UUIDs
SHAREPOINT_NAMESPACE_UUID = uuid.UUID('c7e9aab9-17e4-4f75-8559-40ac7d046c1c') # Example random namespace

def generate_qdrant_point_id(sharepoint_item_id: str) -> str:
    """Generates a deterministic Qdrant UUID point ID from the SharePoint item ID."""
    return str(uuid.uuid5(SHAREPOINT_NAMESPACE_UUID, sharepoint_item_id))

async def _recursively_get_files_from_folder(service: SharePointService, drive_id: str, folder_id: str, processed_ids: set) -> List[Dict[str, Any]]:
    """Helper to recursively fetch file items within a folder, avoiding cycles/duplicates."""
    files = []
    # REMOVED entry guard check as the top-level list is already de-duplicated,
    # and internal checks should handle cycles/duplicates within the expansion.
    
    # Add the current folder ID BEFORE listing children to prevent cycles
    processed_ids.add(folder_id)

    try:
        items = await service.list_drive_items(drive_id=drive_id, item_id=folder_id)
        tasks = []
        for item in items:
            if item.id in processed_ids:
                continue
                
            if item.is_folder:
                # Recurse for sub-folders
                tasks.append(
                    _recursively_get_files_from_folder(service, drive_id, item.id, processed_ids)
                )
            elif item.is_file:
                # Add file details
                processed_ids.add(item.id)
                files.append({
                    "sharepoint_item_id": item.id,
                    "item_name": item.name,
                    "sharepoint_drive_id": drive_id,
                    "webUrl": item.web_url,
                    "createdDateTime": item.created_datetime.isoformat() if item.created_datetime else None,
                    "lastModifiedDateTime": item.last_modified_datetime.isoformat() if item.last_modified_datetime else None,
                    "size": item.size,
                    "item_type": "file"
                })
        
        # Process sub-folder results
        if tasks:
            results = await asyncio.gather(*tasks)
            for sub_files in results:
                files.extend(sub_files)

    except Exception as e:
        # +++ LOG THE SPECIFIC ERROR before re-raising +++
        logger.error(f"_recursively_get_files: Caught exception processing folder {folder_id}: {e}", exc_info=True)
        # Re-raise the exception so the caller knows the expansion failed for this branch
        raise 
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
        """Gets or creates a SharePoint service instance, handling token refresh."""
        if self._sharepoint_service is None:
            logger.debug(f"Task {self.request.id}: Initializing SharePoint service for {user_email}.")
            
            # --- Fetch user with refresh token ---
            db_user = user_crud.get_user_with_refresh_token(db=self.db, email=user_email)
            if not db_user:
                logger.error(f"Task {self.request.id}: User {user_email} not found in DB.")
                raise ValueError(f"User {user_email} not found.")

            access_token = db_user.ms_access_token
            refresh_token = db_user.ms_refresh_token # Assuming stored directly for now
            expiry_time = db_user.ms_token_expiry
            
            # --- Decrypt refresh token if needed ---
            # if refresh_token:
            #     decrypted_refresh_token = decrypt_token(refresh_token)
            # else:
            #     decrypted_refresh_token = None
            decrypted_refresh_token = refresh_token # Assuming not encrypted for now

            if not decrypted_refresh_token:
                logger.error(f"Task {self.request.id}: Missing refresh token for user {user_email}.")
                raise ValueError(f"Missing refresh token for user {user_email}. Cannot proceed.")

            # --- Check token expiry (allowing a buffer) ---
            # Make expiry_time timezone-aware if it isn't already (assuming UTC)
            tz_aware_expiry = None
            if expiry_time:
                if expiry_time.tzinfo is None:
                     tz_aware_expiry = expiry_time.replace(tzinfo=timezone.utc)
                else:
                    tz_aware_expiry = expiry_time # Already timezone-aware
            
            current_time_utc = datetime.now(timezone.utc)
            check_time = current_time_utc + timedelta(minutes=5)
            
            # +++ Add Detailed Logging +++
            logger.info(f"Task {self.request.id}: Expiry Check - DB expiry_time: {expiry_time}")
            logger.info(f"Task {self.request.id}: Expiry Check - Timezone-aware expiry: {tz_aware_expiry}")
            logger.info(f"Task {self.request.id}: Expiry Check - Current UTC time: {current_time_utc}")
            logger.info(f"Task {self.request.id}: Expiry Check - Comparison time (now + 5min): {check_time}")
            # +++ End Detailed Logging +++
            
            # Check if token is missing, expired, or expires within the next 5 minutes
            needs_refresh = False
            if not access_token or not tz_aware_expiry:
                needs_refresh = True
                logger.info(f"Task {self.request.id}: Access token or expiry missing/invalid for {user_email}. Refresh required.")
            elif tz_aware_expiry <= check_time:
                needs_refresh = True
                logger.info(f"Task {self.request.id}: Access token for {user_email} expired or expiring soon (Expiry: {tz_aware_expiry} <= Check Time: {check_time}). Refresh required.")
            else:
                 # +++ Add explicit log for valid token case +++
                 logger.info(f"Task {self.request.id}: Expiry Check PASSED for {user_email} (Expiry: {tz_aware_expiry} > Check Time: {check_time}). Using existing token.")

            # --- Attempt Refresh if Needed ---
            if needs_refresh:
                logger.info(f"Task {self.request.id}: Attempting token refresh for {user_email}.")
                try:
                    msal_instance = get_msal_app()
                    # Ensure scopes match what's needed for SharePointService
                    token_result = msal_instance.acquire_token_by_refresh_token(
                        refresh_token=decrypted_refresh_token,
                        scopes=settings.MS_SCOPES.split() 
                    )

                    if "access_token" in token_result and "expires_in" in token_result:
                        new_access_token = token_result['access_token']
                        new_expiry = datetime.now(timezone.utc) + timedelta(seconds=token_result['expires_in'])
                        new_refresh_token = token_result.get('refresh_token') # Check if MS sent a new one
                        
                        # --- Encrypt new refresh token if needed ---
                        # encrypted_new_refresh = encrypt_token(new_refresh_token) if new_refresh_token else None
                        encrypted_new_refresh = new_refresh_token # Assuming not encrypted
                        
                        # --- Update DB ---
                        logger.info(f"Task {self.request.id}: Token refresh successful for {user_email}. Updating DB.")
                        # Use the new update function
                        update_success = user_crud.update_user_ms_tokens(
                            db=self.db, 
                            user_email=user_email, 
                            access_token=new_access_token, 
                            expiry=new_expiry, 
                            refresh_token=encrypted_new_refresh # Pass the potentially new refresh token
                        )
                        if not update_success:
                             logger.error(f"Task {self.request.id}: Failed to update new tokens in DB for {user_email}.")
                             # Decide how to handle: raise error or try using old token?
                             # Raising error is safer to prevent using stale data
                             raise ValueError("Failed to update refreshed tokens in database.")
                             
                        access_token = new_access_token # Use the new token for the service
                        logger.info(f"Task {self.request.id}: Using newly refreshed access token for {user_email}.")

                    elif "error_description" in token_result:
                         logger.error(f"Task {self.request.id}: MSAL refresh error for {user_email}: {token_result.get('error')} - {token_result.get('error_description')}")
                         raise ValueError(f"Token refresh failed: {token_result.get('error_description')}")
                    else:
                         logger.error(f"Task {self.request.id}: Unexpected MSAL refresh result for {user_email}: {token_result}")
                         raise ValueError("Token refresh failed with unexpected result.")

                except Exception as refresh_err:
                    logger.error(f"Task {self.request.id}: Exception during token refresh for {user_email}: {refresh_err}", exc_info=True)
                    # Re-raise or handle appropriately (e.g., mark task as failed)
                    raise ValueError(f"Exception during token refresh: {refresh_err}")
            else:
                 logger.debug(f"Task {self.request.id}: Existing access token for {user_email} is still valid.")

            # --- Initialize Service with Valid Token ---
            if not access_token:
                 # This should ideally not be reached if refresh logic is correct
                 logger.error(f"Task {self.request.id}: Access token still unavailable for {user_email} after refresh attempt.")
                 raise ValueError(f"Could not obtain valid access token for {user_email}.")
                 
            self._sharepoint_service = SharePointService(access_token)
            
        return self._sharepoint_service

async def _run_processing_logic(
    task_instance: Task,
    db_session: Session,
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
                # Add successfully retrieved file details from the recursive call
                # The recursive call already handles its internal duplicates.
                # The final dict-based deduplication will handle any duplicates across top-level calls.
                for file_detail in result:
                     all_files_to_process.append(file_detail)
            else:
                 logger.warning(f"Task {task_id}: Unexpected result type from folder expansion: {type(result)}")

    total_files = len(all_files_to_process)
    logger.info(f"Task {task_id}: Total files to process after expansion: {total_files}. Discovery failures: {total_failed_discovery}")
    if total_files == 0:
        return 0, total_failed_discovery, [] # Processed, Failed, Points

    # --- De-duplicate the FINAL list of files before processing ---
    # +++ Add Logging: Inspect list before de-duplication +++
    logger.debug(f"Task {task_id}: Content of all_files_to_process before de-duplication (first 2 items): {all_files_to_process[:2]}")
    
    unique_files_dict: Dict[str, Dict[str, Any]] = {}
    for file_item in all_files_to_process:
        file_id = file_item.get('sharepoint_item_id')
        if file_id and file_id not in unique_files_dict:
            unique_files_dict[file_id] = file_item
        elif not file_id:
            logger.warning(f"Task {task_id}: Found file item without 'sharepoint_item_id' after expansion: {file_item}")

    final_files_to_process = list(unique_files_dict.values())

    # --- Process Each File (Async Downloads) --- 
    points_to_upsert: List[models.PointStruct] = []
    total_processed_files = 0
    total_failed_files = total_failed_discovery # Start with discovery failures
    current_file_num = 0

    for item_data_from_api in final_files_to_process: # Renamed for clarity
        current_file_num += 1
        # Get SharePoint IDs from the data passed to the task
        file_id = item_data_from_api['sharepoint_item_id']
        drive_id = item_data_from_api['sharepoint_drive_id']
        # Get the Database ID for status updates
        item_db_id = item_data_from_api.get('item_db_id') # Use .get() for safety

        # item_status = 'processing' # Default status before processing <-- REMOVE, set below
        db_sync_item: Optional[SharePointSyncItemDBModel] = None # Define type hint

        # --- Attempt to fetch DB item and update status ONLY if item_db_id exists --- 
        if item_db_id:
            try:
                db_sync_item = db_session.get(SharePointSyncItemDBModel, item_db_id)
                if db_sync_item:
                    db_sync_item.status = 'processing'
                    db_session.add(db_sync_item)
                    db_session.commit()
                    logger.debug(f"Task {task_id}: Set status to 'processing' for DB item ID {item_db_id} (SP ID: {file_id})")
                else:
                    logger.warning(f"Task {task_id}: Could not find DB sync item with DB ID {item_db_id} (SP ID: {file_id}) to update status. Status update skipped.")
                    # Don't skip the whole file, just the status update
            except Exception as db_err:
                logger.error(f"Task {task_id}: DB error updating status to 'processing' for DB ID {item_db_id}: {db_err}", exc_info=True)
                db_session.rollback()
                # Don't skip the whole file, try processing anyway but log DB error
        else:
            logger.debug(f"Task {task_id}: No item_db_id for discovered file SP ID {file_id}. Skipping DB status updates.")
        # --- End status update attempt ---

        # --- Fetch full item details (Always attempt this) ---
        logger.debug(f"Task {task_id}: Fetching full details for item {file_id}")
        file_details = None
        try:
            file_details = await sp_service.get_item_details(drive_id=drive_id, item_id=file_id)
        except Exception as detail_err:
             logger.error(f"Task {task_id}: Error fetching details for file '{item_data_from_api.get('item_name', 'Unknown')}' (ID: {file_id}): {detail_err}", exc_info=True)
             # No details, cannot proceed with this file

        if not file_details:
            logger.warning(f"Task {task_id}: Could not fetch details for file '{item_data_from_api.get('item_name', 'Unknown')}' (ID: {file_id}). Skipping file processing.")
            total_failed_files += 1
            # Update status to 'failed' only if we had a DB item
            if db_sync_item:
                try:
                    db_sync_item.status = 'failed'
                    db_session.add(db_sync_item)
                    db_session.commit()
                    logger.info(f"Task {task_id}: Set status to 'failed' for DB item ID {item_db_id} (SP ID: {file_id}) due to detail fetch error.")
                except Exception as db_err_fail:
                    logger.error(f"Task {task_id}: DB error updating status to 'failed' for DB ID {item_db_id}: {db_err_fail}", exc_info=True)
                    db_session.rollback()
            continue # Go to next file if details failed
        
        file_info = file_details.model_dump()
        file_name = file_info.get('name', item_data_from_api.get('item_name', 'Unknown')) # Prefer fetched name
        logger.debug(f"Task {task_id}: file_info dict before payload creation: {file_info}")

        # --- Update task progress ---
        progress_percent = 10 + int(80 * (current_file_num / total_files))
        logger.info(f"Task {task_id}: Processing file {current_file_num}/{total_files}: '{file_name}' (ID: {file_id}) - Size: {file_info.get('size')}")
        task_instance.update_state(state='PROGRESS', meta={'user': user_email, 'progress': progress_percent, 'status': f'Processing file {current_file_num}/{total_files}: {file_name[:30]}...'})

        try:
            # 1. Download file
            file_content_bytes = await sp_service.download_file_content(drive_id=drive_id, item_id=file_id)
            if file_content_bytes is None:
                 logger.warning(f"Task {task_id}: No content for file {file_id}. Skipping point creation, marking as failed.")
                 raise ValueError("File content was None") 

            # 2. Process content (Placeholder for embedding)
            # vector = await embed_content(file_content_bytes, file_name) 
            vector_size = settings.EMBEDDING_DIMENSION # Use setting
            vector = [0.1] * vector_size # Placeholder vector
            logger.debug(f"Task {task_id}: Placeholder processing complete for {file_name}.")

            # 3. Construct Qdrant payload
            payload = {
                "source": "sharepoint",
                "document_type": "file",
                "sharepoint_item_id": file_id,
                "sharepoint_drive_id": drive_id,
                "name": file_info.get("name"),
                "webUrl": file_info.get("webUrl"),
                "createdDateTime": file_info.get("createdDateTime"),
                "lastModifiedDateTime": file_info.get("lastModifiedDateTime"),
                "size": file_info.get("size"),
                "mimeType": file_info.get("file", {}).get("mimeType"),
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            # 4. Create Qdrant point
            qdrant_point_id = generate_qdrant_point_id(file_id)
            point = models.PointStruct(
                id=qdrant_point_id,
                vector=vector,
                payload=payload
            )
            points_to_upsert.append(point)
            total_processed_files += 1

            # 5. Update status to 'completed' in DB (only if db_sync_item exists)
            if db_sync_item:
                try:
                    db_sync_item.status = 'completed'
                    db_session.add(db_sync_item)
                    db_session.commit()
                    logger.info(f"Task {task_id}: Set status to 'completed' for DB item ID {item_db_id} (SP ID: {file_id})")
                except Exception as db_err_complete:
                    logger.error(f"Task {task_id}: DB error updating status to 'completed' for DB ID {item_db_id}: {db_err_complete}", exc_info=True)
                    db_session.rollback()
                    # If DB update fails, count as failure even if point was created
                    total_failed_files += 1
                    if total_processed_files > 0: 
                      total_processed_files -= 1

        except Exception as e: 
            logger.error(f"Task {task_id}: Failed to process file '{file_name}' (ID: {file_id}): {e}", exc_info=True)
            total_failed_files += 1
            # 6. Update status to 'failed' in DB (only if db_sync_item exists)
            if db_sync_item:
                try:
                    if db_sync_item.status != 'failed': # Avoid re-updating if already failed
                        db_sync_item.status = 'failed'
                        db_session.add(db_sync_item)
                        db_session.commit()
                        logger.info(f"Task {task_id}: Set status to 'failed' for DB item ID {item_db_id} (SP ID: {file_id}) due to processing error.")
                except Exception as db_err_fail:
                    logger.error(f"Task {task_id}: DB error updating status to 'failed' for DB ID {item_db_id}: {db_err_fail}", exc_info=True)
                    db_session.rollback()

    return total_processed_files, total_failed_files, points_to_upsert

@celery_app.task(bind=True, base=SharePointProcessingTask, name='tasks.sharepoint.process_batch')
def process_sharepoint_batch_task(self: Task, items_for_task: List[Dict[str, Any]], user_email: str): # Renamed parameter
    task_id = self.request.id
    logger.info(f"Starting SharePoint batch task {task_id} for user {user_email} ({len(items_for_task)} items).")
    self.update_state(state='STARTED', meta={'user': user_email, 'progress': 0, 'status': 'Initializing...'})

    qdrant_client = self.qdrant_client
    db_session = self.db # Get DB session from Task base class
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
        total_processed, total_failed, points_to_upsert = asyncio.run(
            _run_processing_logic(
                task_instance=self, 
                db_session=db_session, 
                sp_service=sp_service, 
                items_to_process=items_for_task, # Pass the correctly named list
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