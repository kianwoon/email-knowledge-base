import logging
import base64
import asyncio
from asyncio import TimeoutError # Import TimeoutError
from typing import List, Dict, Any, Tuple, Optional
import uuid
from datetime import datetime, timedelta, timezone
import json # Import json for metadata serialization

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session
from fastapi.concurrency import run_in_threadpool # Import run_in_threadpool
import httpx # Import httpx for potential timeout configuration

from ..celery_app import celery_app
from ..config import settings
from app.services.sharepoint import SharePointService # Assuming exists and can be initialized with token
# Remove Qdrant imports
# from app.db.qdrant_client import get_qdrant_client
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.exceptions import UnexpectedResponse
# Import Milvus
from pymilvus import MilvusClient
from app.db.milvus_client import get_milvus_client, ensure_collection_exists # Import Milvus helpers

from app.crud import user_crud # To get user tokens if needed indirectly
from app.db.session import SessionLocal # For getting user tokens
from app.utils.security import decrypt_token # For user tokens
from app.crud import crud_sharepoint_sync_item # Import sync item CRUD and model
from app.db.models.sharepoint_sync_item import SharePointSyncItem as SharePointSyncItemDBModel # Import SharePointSyncItem model
from .email_tasks import get_msal_app # CORRECTED Import from the sibling email_tasks module

# Ensure SQLAlchemy update is imported if not already
from sqlalchemy import update # Add this near other SQLAlchemy imports if missing

logger = get_task_logger(__name__)

def generate_milvus_collection_name(user_email: str) -> str: # Renamed function
    """Generates a sanitized, user-specific Milvus collection name."""
    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    return f"{sanitized_email}_sharepoint_knowledge"

# Define a namespace for generating UUIDs
SHAREPOINT_NAMESPACE_UUID = uuid.UUID('c7e9aab9-17e4-4f75-8559-40ac7d046c1c') # Example random namespace

def generate_milvus_pk(sharepoint_item_id: str) -> str: # Renamed function
    """Generates a deterministic Milvus UUID PK from the SharePoint item ID."""
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

# --- Define a timeout for the blocking refresh call ---
MS_REFRESH_TIMEOUT_SECONDS = getattr(settings, 'MS_REFRESH_TIMEOUT_SECONDS', 30)

class SharePointProcessingTask(Task):
    _db = None
    # _qdrant_client = None # Remove Qdrant client instance variable
    _milvus_client = None # Add Milvus client instance variable
    _sharepoint_service = None # Service instance per task potentially

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        # Close DB session if opened
        if self._db:
            self._db.close()
            logger.debug(f"Task {task_id}: DB session closed.")
        # Cleanup other resources if necessary
        # Milvus client cleanup might not be needed here if managed globally

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def milvus_client(self) -> MilvusClient: # Renamed property and updated type hint
        if self._milvus_client is None:
            logger.debug(f"Task {self.request.id}: Getting Milvus client instance.")
            self._milvus_client = get_milvus_client() # Use Milvus getter
        return self._milvus_client

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
            refresh_token = db_user.ms_refresh_token # Assuming stored directly
            expiry_time = db_user.ms_token_expiry
            decrypted_refresh_token = refresh_token # Assuming not encrypted

            if not decrypted_refresh_token:
                logger.error(f"Task {self.request.id}: Missing refresh token for user {user_email}.")
                raise ValueError(f"Missing refresh token for user {user_email}. Cannot proceed.")

            # --- Check token expiry (allowing a buffer) ---
            tz_aware_expiry = None
            if expiry_time:
                if expiry_time.tzinfo is None:
                     tz_aware_expiry = expiry_time.replace(tzinfo=timezone.utc)
                else:
                    tz_aware_expiry = expiry_time
            
            current_time_utc = datetime.now(timezone.utc)
            check_time = current_time_utc + timedelta(minutes=5)
            
            logger.info(f"Task {self.request.id}: Expiry Check - Timezone-aware expiry: {tz_aware_expiry}")
            logger.info(f"Task {self.request.id}: Expiry Check - Comparison time (now + 5min): {check_time}")

            needs_refresh = False
            if not access_token or not tz_aware_expiry:
                needs_refresh = True
                logger.info(f"Task {self.request.id}: Access token or expiry missing/invalid for {user_email}. Refresh required.")
            elif tz_aware_expiry <= check_time:
                needs_refresh = True
                logger.info(f"Task {self.request.id}: Access token for {user_email} expired or expiring soon. Refresh required.")
            else:
                 logger.info(f"Task {self.request.id}: Expiry Check PASSED for {user_email}. Using existing token.")

            # --- Attempt Refresh if Needed ---
            if needs_refresh:
                logger.info(f"Task {self.request.id}: Attempting **direct blocking** token refresh for {user_email}.")
                try:
                    msal_instance = get_msal_app()
                    required_scopes = settings.MS_SCOPE

                    # Filter out reserved scopes before requesting token refresh
                    reserved_scopes = {'openid', 'profile', 'offline_access', 'email'} # Added 'email'
                    filtered_scopes = [s for s in required_scopes if s.lower() not in reserved_scopes]
                    logger.debug(f"Filtered MS Scopes for refresh: {filtered_scopes}")

                    token_result = msal_instance.acquire_token_by_refresh_token(
                        refresh_token=decrypted_refresh_token,
                        scopes=filtered_scopes
                        # If msal allows passing timeout, add it here e.g. timeout=MS_REFRESH_TIMEOUT_SECONDS
                    )
                    # --- End direct call ---

                    if not token_result or "error" in token_result:
                        error_desc = token_result.get('error_description', 'Unknown token acquisition error') if token_result else "No result from refresh call"
                        logger.error(f"Task {self.request.id}: MSAL refresh error for {user_email}: {token_result.get('error') if token_result else 'N/A'} - {error_desc}")
                        # Fail explicitly if refresh fails
                        raise ValueError(f"Token refresh failed (MSAL): {error_desc}")

                    if "access_token" in token_result and "expires_in" in token_result:
                        new_access_token = token_result['access_token']
                        new_expiry = datetime.now(timezone.utc) + timedelta(seconds=token_result['expires_in'])
                        new_refresh_token = token_result.get('refresh_token')
                        encrypted_new_refresh = new_refresh_token # Assuming not encrypted

                        logger.info(f"Task {self.request.id}: Token refresh successful for {user_email}. Updating DB.")
                        update_success = user_crud.update_user_ms_tokens(
                            db=self.db,
                            user_email=user_email,
                            access_token=new_access_token,
                            expiry=new_expiry,
                            refresh_token=encrypted_new_refresh
                        )
                        if not update_success:
                             logger.error(f"Task {self.request.id}: Failed to update new tokens in DB for {user_email}.")
                             raise ValueError("Failed to update refreshed tokens in database.")

                        access_token = new_access_token # Use the new token
                        logger.info(f"Task {self.request.id}: DB update successful. Using newly refreshed access token for {user_email}.")
                    else:
                         logger.error(f"Task {self.request.id}: Unexpected MSAL refresh result structure for {user_email}: {token_result}")
                         raise ValueError("Token refresh failed with unexpected result structure.")

                # Catch specific exceptions if needed (e.g., httpx.TimeoutException if underlying client uses it)
                except Exception as refresh_err:
                    logger.error(f"Task {self.request.id}: Exception during token refresh process for {user_email}: {refresh_err}", exc_info=True)
                    # IMPORTANT: Re-raise the exception to ensure the task fails if refresh fails
                    raise ValueError(f"Exception during token refresh prevented service initialization: {refresh_err}")

            # --- Initialize Service with Valid Token ---
            if not access_token:
                 # This should only be reached if refresh wasn't needed but token was initially None
                 logger.error(f"Task {self.request.id}: Access token is unexpectedly None before service initialization for {user_email}.")
                 raise ValueError(f"Could not obtain valid access token for {user_email}.")

            # +++ Add final confirmation log +++
            logger.info(f"Task {self.request.id}: Initializing SharePointService for {user_email} with token expiring at {expiry_time} (or refreshed expiry if applicable). Token starts with: {access_token[:10]}...")
            self._sharepoint_service = SharePointService(access_token)

        return self._sharepoint_service

async def _run_processing_logic(
    task_instance: Task,
    db_session: Session,
    sp_service: SharePointService,
    items_to_process: List[Dict[str, Any]], # This is the original list including folders
    user_email: str,
    task_id: str # Added task_id parameter
) -> Tuple[int, int, List[Dict[str, Any]]]: # Updated return type hint
    """Orchestrates the async fetching and processing of files, preparing Milvus data dicts."""
    # task_id = task_instance.request.id # Get task_id from parameter instead
    all_files_to_process: List[Dict[str, Any]] = []
    processed_item_ids = set() # Track all processed IDs (files and folders)
    total_failed_discovery = 0
    # +++ Keep track of original folder DB IDs and their expansion outcome +++
    folder_outcomes: Dict[int, str] = {} # {item_db_id: "success" | "failed"}

    # --- Expand Folders to Files (Async) ---
    logger.info(f"Task {task_id}: Expanding folders...")
    folder_expansion_tasks = []
    original_folder_items_map: Dict[str, int] = {} # {folder_sp_id: item_db_id}

    for item in items_to_process:
        item_sp_id = item['sharepoint_item_id']
        item_db_id = item.get('item_db_id') # Get the DB ID of the original item
        item_type = item.get('item_type')

        if item_sp_id in processed_item_ids: # Skip if already handled (e.g., duplicate entry)
            continue

        if item_type == 'folder' and item_db_id:
            logger.info(f"Task {task_id}: Queuing expansion for folder '{item.get('item_name')}' (SP_ID: {item_sp_id}, DB_ID: {item_db_id}) ")
            original_folder_items_map[item_sp_id] = item_db_id # Store mapping
            # Add task to list for concurrent execution
            folder_expansion_tasks.append(
                 _recursively_get_files_from_folder(sp_service, item['sharepoint_drive_id'], item_sp_id, processed_item_ids)
            )
            # Mark folder SP ID as processed (to avoid re-processing if listed again)
            processed_item_ids.add(item_sp_id) 
            # Assume success initially, will be updated on error
            folder_outcomes[item_db_id] = "success"

        elif item_type == 'file':
             # Add file directly if not already processed (e.g., added individually)
             if item_sp_id not in processed_item_ids:
                 all_files_to_process.append(item)
                 processed_item_ids.add(item_sp_id)
        else:
            logger.warning(f"Task {task_id}: Skipping item {item_sp_id} with unknown type: {item_type}")
            if item_db_id: # Mark unknown type with DB ID as failed
                 folder_outcomes[item_db_id] = "failed"

    # Run folder expansions concurrently
    if folder_expansion_tasks:
        # Use the list of futures directly, assume order matches original append order implicitly
        expansion_results = await asyncio.gather(*folder_expansion_tasks, return_exceptions=True)
        
        # Correlate results back to original folders
        original_folder_sp_ids = list(original_folder_items_map.keys())
        for i, result in enumerate(expansion_results):
            folder_sp_id = original_folder_sp_ids[i]
            folder_db_id = original_folder_items_map[folder_sp_id]
            
            if isinstance(result, Exception):
                logger.error(f"Task {task_id}: Folder expansion failed for SP_ID {folder_sp_id} (DB_ID: {folder_db_id}): {result}", exc_info=result)
                total_failed_discovery += 1 # Count failure
                folder_outcomes[folder_db_id] = "failed" # Mark this specific folder as failed
            elif isinstance(result, list):
                # Add successfully retrieved file details
                all_files_to_process.extend(result)
                # Keep folder_outcomes[folder_db_id] as "success"
            else:
                 logger.warning(f"Task {task_id}: Unexpected result type from folder expansion for SP_ID {folder_sp_id} (DB_ID: {folder_db_id}): {type(result)}")
                 folder_outcomes[folder_db_id] = "failed" # Mark as failed on unexpected result

    # --- De-duplicate the FINAL list of files before processing ---
    logger.debug(f"Task {task_id}: Content of all_files_to_process before de-duplication (first 2 items): {all_files_to_process[:2]}")
    unique_files_dict: Dict[str, Dict[str, Any]] = {}
    for file_item in all_files_to_process:
        file_id = file_item.get('sharepoint_item_id')
        if file_id and file_id not in unique_files_dict:
            unique_files_dict[file_id] = file_item
        elif not file_id:
            logger.warning(f"Task {task_id}: Found file item without 'sharepoint_item_id' after expansion: {file_item}")
    final_files_to_process = list(unique_files_dict.values())
    total_files = len(final_files_to_process)
    logger.info(f"Task {task_id}: Total unique files to process: {total_files}. Discovery failures: {total_failed_discovery}")
    if total_files == 0 and total_failed_discovery == 0:
         # If no files and no discovery errors, potentially update original items that were empty folders
         pass # Handled later
    elif total_files == 0 and total_failed_discovery > 0:
         # If only discovery errors, the folders are already marked failed
         pass # Handled later

    # --- Process Each File --- 
    data_to_insert: List[Dict[str, Any]] = [] # Changed from points_to_upsert
    total_processed_files = 0
    # Start file failures count with discovery failures
    total_failed_files_or_folders = total_failed_discovery 
    current_file_num = 0

    for item_data_from_api in final_files_to_process: 
        current_file_num += 1
        file_id = item_data_from_api['sharepoint_item_id']
        drive_id = item_data_from_api['sharepoint_drive_id']
        item_db_id = item_data_from_api.get('item_db_id') # DB ID of the *file itself*, if added directly
        file_name = item_data_from_api.get('item_name', 'Unknown')
        
        # Assume success for this file initially
        file_processed_successfully = False
        db_sync_item: Optional[SharePointSyncItemDBModel] = None 
        
        # --- Update DB Status for the file item (if it has a direct DB entry) ---
        if item_db_id:
            try:
                db_sync_item = db_session.get(SharePointSyncItemDBModel, item_db_id)
                if db_sync_item:
                    db_sync_item.status = 'processing'
                    db_session.add(db_sync_item)
                    db_session.commit()
                else: logger.warning(f"Task {task_id}: Could not find DB sync item with DB ID {item_db_id} (SP ID: {file_id}) to update status.")
            except Exception as db_err: logger.error(f"Task {task_id}: DB error updating status to 'processing' for DB ID {item_db_id}: {db_err}", exc_info=True); db_session.rollback()
        
        # --- Process the file --- 
        try:
            # Fetch details (moved inside try-except)
            logger.debug(f"Task {task_id}: Fetching full details for item {file_id}")
            file_details = await sp_service.get_item_details(drive_id=drive_id, item_id=file_id)
            if not file_details: raise ValueError("Could not fetch file details")
            file_info = file_details.model_dump()
            file_name = file_info.get('name', file_name) # Prefer fetched name
            logger.info(f"Task {task_id}: Processing file {current_file_num}/{total_files}: '{file_name}' (ID: {file_id}) - Size: {file_info.get('size')}")
            task_instance.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 10 + int(80 * (current_file_num / total_files)), 'status': f'Processing file {current_file_num}/{total_files}: {file_name[:30]}...'})

            # Process content (Embedding placeholder)
            # Use DENSE_EMBEDDING_DIMENSION from settings
            vector_size = settings.DENSE_EMBEDDING_DIMENSION 
            vector = [0.0] * vector_size # Use float 0.0 for placeholder

            # --- Prepare Milvus data dictionary --- 
            milvus_pk = generate_milvus_pk(file_id) # Renamed function call

            # Construct metadata dict (excluding b64 content)
            metadata_payload = {
                "sharepoint_item_id": file_id,
                "sharepoint_drive_id": drive_id,
                "filename": file_info.get("name"),
                "webUrl": file_info.get("webUrl"),
                "createdDateTime": file_info.get("createdDateTime"),
                "lastModifiedDateTime": file_info.get("lastModifiedDateTime"),
                "size": file_info.get("size"),
                "mimeType": file_info.get("file", {}).get("mimeType"),
                "analysis_status": "pending"
            }
            metadata_payload = {k: v for k, v in metadata_payload.items() if v is not None}

            data_dict = {
                "pk": milvus_pk,
                "vector": vector, # Placeholder vector
                "owner": user_email,
                "source": "sharepoint", 
                "type": "sharepoint_knowledge", # Type indicating raw sharepoint data
                "email_id": user_email, # ADDED: Match schema requirement
                "job_id": task_id, # Use task_id from parameter
                "subject": file_info.get("name"), # Use filename as subject
                "date": file_info.get("lastModifiedDateTime") or "", # Use last modified OR empty string
                "status": "processed", # Simplified status
                "folder": "", # Leave blank for now
                # Store the rest in the JSON field, ensuring it's serializable
                "metadata_json": metadata_payload # Store prepared dict directly
            }
            
            data_to_insert.append(data_dict) # Add the dictionary
            
            # Mark as successful for status update
            file_processed_successfully = True
            total_processed_files += 1

        except Exception as e:
            logger.error(f"Task {task_id}: Failed to process file '{file_name}' (ID: {file_id}): {e}", exc_info=True)
            total_failed_files_or_folders += 1 # Increment overall failure count
            # file_processed_successfully remains False

        # --- Update DB status for the file (if direct entry exists) ---
        if db_sync_item:
            final_file_status = 'completed' if file_processed_successfully else 'failed'
            if db_sync_item.status != final_file_status: # Avoid redundant updates
                 try:
                     db_sync_item.status = final_file_status
                     db_session.add(db_sync_item)
                     db_session.commit()
                     logger.info(f"Task {task_id}: Set file status to '{final_file_status}' for DB item ID {item_db_id} (SP ID: {file_id})")
                 except Exception as db_err_final:
                     logger.error(f"Task {task_id}: DB error updating final status to '{final_file_status}' for DB ID {item_db_id}: {db_err_final}", exc_info=True)
                     db_session.rollback()
                     # If DB update fails, revert success count and increment failure count
                     if file_processed_successfully:
                         total_processed_files -= 1
                         total_failed_files_or_folders += 1

    # --- Update Original Folder Item Statuses --- 
    logger.info(f"Task {task_id}: === Starting Final Folder Status Update Section ===")
    logger.info(f"Task {task_id}: Original items passed to task: {items_to_process}") # Log the original list
    logger.info(f"Task {task_id}: Folder expansion outcomes: {folder_outcomes}") # Log the outcomes dict
    
    processed_folder_db_ids = set()

    for loop_idx, original_item in enumerate(items_to_process): # Iterate through the initial list again
        item_db_id = original_item.get('item_db_id')
        item_type = original_item.get('item_type')
        logger.debug(f"Task {task_id}: Final loop check item {loop_idx}: DB_ID={item_db_id}, Type={item_type}") # Log each item check

        if item_type == 'folder' and item_db_id and item_db_id not in processed_folder_db_ids:
            processed_folder_db_ids.add(item_db_id) # Prevent processing same folder DB ID twice
            logger.info(f"Task {task_id}: Processing FOLDER item: DB_ID={item_db_id}") # Log when folder is processed
            
            folder_final_status = "unknown"
            expansion_outcome = folder_outcomes.get(item_db_id)
            logger.debug(f"Task {task_id}: Folder DB_ID {item_db_id} - Expansion outcome: {expansion_outcome}")

            if expansion_outcome == "success":
                folder_final_status = 'completed'
            elif expansion_outcome == "failed":
                folder_final_status = 'failed'
            else:
                logger.warning(f"Task {task_id}: Unknown expansion outcome for folder DB ID {item_db_id}. Cannot determine final status.")
                continue
                
            logger.info(f"Task {task_id}: Determined final status for folder DB_ID {item_db_id} as: '{folder_final_status}'")

            try:
                logger.debug(f"Task {task_id}: Attempting direct update for folder DB_ID {item_db_id}...")
                # Use a direct query and update approach within this block for isolation
                stmt = (
                    update(SharePointSyncItemDBModel)
                    .where(SharePointSyncItemDBModel.id == item_db_id)
                    .values(status=folder_final_status)
                    .execution_options(synchronize_session="fetch") # Or False, depending on need
                )
                result = db_session.execute(stmt)
                logger.debug(f"Task {task_id}: Update execution result for folder DB_ID {item_db_id}: rowcount={result.rowcount}")
                if result.rowcount > 0:
                    logger.info(f"Task {task_id}: Directly updated status for original folder (DB_ID: {item_db_id}) to '{folder_final_status}'. ({result.rowcount} row affected). Attempting commit.")
                    try:
                        db_session.commit() 
                        logger.info(f"Task {task_id}: Successfully committed status update for folder DB_ID: {item_db_id}.")
                    except Exception as commit_err:
                        logger.error(f"Task {task_id}: Failed to commit status update for folder DB_ID {item_db_id}: {commit_err}", exc_info=True)
                        db_session.rollback() 
                else:
                    # This might happen if the status was already correct, or the item was deleted
                    logger.warning(f"Task {task_id}: Update statement affected 0 rows for folder DB ID {item_db_id}. Item might not exist or status already set.")
            except Exception as db_folder_err:
                 logger.error(f"Task {task_id}: DB error during final status update attempt for folder DB ID {item_db_id}: {db_folder_err}", exc_info=True)
                 db_session.rollback() # Rollback on error during update execution
        elif item_type != 'folder':
             logger.debug(f"Task {task_id}: Final loop - Skipping non-folder item {loop_idx}: DB_ID={item_db_id}")
        elif not item_db_id:
             logger.debug(f"Task {task_id}: Final loop - Skipping folder item {loop_idx} without DB ID.")
        elif item_db_id in processed_folder_db_ids:
             logger.debug(f"Task {task_id}: Final loop - Skipping already processed folder DB_ID {item_db_id}.")
             
    logger.info(f"Task {task_id}: === Finished Final Folder Status Update Section ===")

    # Return counts and data dicts
    logger.info(f"Task {task_id}: Returning final counts. Processed Files: {total_processed_files}, Failed Items (Files+Folders): {total_failed_files_or_folders}")
    return total_processed_files, total_failed_files_or_folders, data_to_insert # Return list of dicts

@celery_app.task(bind=True, base=SharePointProcessingTask, name='tasks.sharepoint.process_batch')
def process_sharepoint_batch_task(self: Task, items_for_task: List[Dict[str, Any]], user_email: str):
    task_id = self.request.id
    logger.info(f"Starting SharePoint batch task {task_id} for user {user_email} ({len(items_for_task)} items).")
    self.update_state(state='STARTED', meta={'user': user_email, 'progress': 0, 'status': 'Initializing...'})

    milvus_client = self.milvus_client # Use Milvus client property
    db_session = self.db # Get DB session from Task base class
    target_collection_name = generate_milvus_collection_name(user_email) # Use renamed function
    total_processed = 0
    total_failed = 0

    try:
        # --- Ensure Milvus Collection Exists --- 
        logger.info(f"Task {task_id}: Ensuring Milvus collection '{target_collection_name}' with dim {settings.DENSE_EMBEDDING_DIMENSION}.") # Updated log
        self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 5, 'status': 'Checking collection...'})
        try:
            # Use Milvus helper ensure_collection_exists
            ensure_collection_exists(milvus_client, target_collection_name, settings.DENSE_EMBEDDING_DIMENSION) # Use setting dimension
            logger.info(f"Task {task_id}: Milvus collection '{target_collection_name}' is ready.")
        except Exception as create_err: 
            # Catch potential errors from ensure_collection_exists (e.g., connection, schema mismatch)
            logger.error(f"Task {task_id}: Failed to ensure Milvus collection '{target_collection_name}': {create_err}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user': user_email, 'status': f'Failed to prepare vector collection: {create_err}'})
            raise Exception(f"Failed to prepare target collection: {create_err}") # Reraise

        # --- Get SharePoint Service --- 
        sp_service = self.get_sharepoint_service(user_email)
        logger.info(f"Task {task_id}: SharePoint service initialized.")
        self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 10, 'status': 'Discovering files...'})

        # --- Run Async Logic --- 
        # Note: total_failed now includes folder discovery failures AND file processing failures
        total_processed, total_failed, data_to_insert = asyncio.run( # Renamed points_to_upsert
            _run_processing_logic(
                task_instance=self, 
                db_session=db_session, 
                sp_service=sp_service, 
                items_to_process=items_for_task, # Pass the original list
                user_email=user_email,
                task_id=task_id # Pass task_id
            )
        )

        # --- Batch Insert into Milvus --- 
        logger.info(f"Task {task_id}: Inserting {len(data_to_insert)} data points into Milvus.") # Updated log
        self.update_state(state='PROGRESS', meta={'user': user_email, 'progress': 95, 'status': 'Saving data...'})
        if data_to_insert:
            try:
                # Use Milvus insert
                insert_result = milvus_client.insert(
                    collection_name=target_collection_name, 
                    data=data_to_insert
                )
                logger.info(f"Task {task_id}: Milvus insert call successful for {len(data_to_insert)} points.") # Simplified log
            except Exception as upsert_err:
                logger.error(f"Task {task_id}: Milvus insert failed: {upsert_err}", exc_info=True) # Updated log
                total_failed += len(data_to_insert) # Count these as failed
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