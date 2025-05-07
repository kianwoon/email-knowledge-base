from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import uuid
import json

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.services.outlook import OutlookService
from app.models.user import UserDB
from app.crud import user_crud
from app.tasks.outlook_sync import cancel_user_sync_tasks

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email/sync", tags=["outlook-sync"])


class SyncConfig(BaseModel):
    enabled: bool
    frequency: str  # 'hourly', 'daily', or 'weekly'
    folders: List[str]
    startDate: Optional[str] = None
    # Add fields for domain configuration
    primaryDomain: Optional[str] = None
    allianceDomains: Optional[List[str]] = None


class SyncStatus(BaseModel):
    folder: str
    folderId: str
    status: str  # 'idle', 'syncing', 'completed', 'error'
    lastSync: Optional[str] = None
    progress: float = 0
    itemsProcessed: int = 0
    totalItems: int = 0
    error: Optional[str] = None


class SyncFolderRequest(BaseModel):
    folders: List[str]
    startDate: Optional[str] = None


class LastSyncInfo(BaseModel):
    last_sync: Optional[datetime] = None
    items_processed: Optional[int] = None
    folder: Optional[str] = None


# Global storage for active sync tasks (in-memory)
# In a production environment, this should be in a database or Redis
active_sync_tasks: Dict[str, Dict[str, Any]] = {}


@router.get("/config", response_model=Optional[SyncConfig])
async def get_sync_config(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the current user's Outlook sync configuration."""
    try:
        # Get the user record from the database
        user_db = db.query(UserDB).filter(UserDB.email == current_user.email).first()
        
        if not user_db or not user_db.outlook_sync_config:
            logger.warning(f"User {current_user.email} not found or has no outlook_sync_config.")
            return None
            
        # Log the raw config string from DB
        raw_config_str = user_db.outlook_sync_config
        logger.info(f"Raw outlook_sync_config from DB for {current_user.email}: {raw_config_str}")
            
        # Parse the stored JSON string
        try:
            config_dict = json.loads(raw_config_str)
            logger.info(f"Parsed config_dict: {config_dict}")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse outlook_sync_config JSON for user {current_user.email}")
            return None 
            
        # Extract values with logging, checking both camelCase and snake_case as a fallback
        enabled = config_dict.get('enabled', False)
        frequency = config_dict.get('frequency', 'daily')
        folders = config_dict.get('folders', [])
        startDate = config_dict.get('startDate')
        
        # Prioritize camelCase, fallback to snake_case
        primaryDomain = config_dict.get('primaryDomain')
        if primaryDomain is None:
            primaryDomain = config_dict.get('primary_domain') # Check snake_case
            
        allianceDomains = config_dict.get('allianceDomains')
        if allianceDomains is None:
            allianceDomains = config_dict.get('alliance_domains') # Check snake_case
        
        logger.info(f"Extracted primaryDomain (after checking variations): {primaryDomain}")
        logger.info(f"Extracted allianceDomains (after checking variations): {allianceDomains}")
            
        # Create a SyncConfig instance from the parsed dictionary,
        # including the new domain fields. Pydantic handles missing keys gracefully.
        response_obj = SyncConfig(
            enabled=enabled,
            frequency=frequency,
            folders=folders,
            startDate=startDate,
            primaryDomain=primaryDomain,
            allianceDomains=allianceDomains
        )
        
        logger.info(f"Returning SyncConfig object: {response_obj.dict()}")
        return response_obj
    except Exception as e:
        logger.error(f"Error getting sync config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sync configuration"
        )


@router.post("/config", response_model=SyncConfig)
async def save_sync_config(
    sync_config: SyncConfig,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Save the user's Outlook sync configuration."""
    try:
        # Get the user record from the database
        user_db = db.query(UserDB).filter(UserDB.email == current_user.email).first()
        
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Explicitly create the dictionary to be saved
        config_to_save = {
            "enabled": sync_config.enabled,
            "frequency": sync_config.frequency,
            "folders": sync_config.folders,
            "startDate": sync_config.startDate,
            "primaryDomain": sync_config.primaryDomain, 
            "allianceDomains": sync_config.allianceDomains
        }
        logger.info(f"Dictionary constructed for saving: {config_to_save}")
        
        # Serialize using json.dumps
        try:
            config_json_to_save = json.dumps(config_to_save)
            logger.info(f"JSON string generated for saving: {config_json_to_save}")
        except Exception as json_err:
            logger.error(f"Error serializing config dictionary to JSON: {json_err}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to prepare sync configuration for saving."
            )

        # Save the generated JSON string
        user_db.outlook_sync_config = config_json_to_save
        
        # Commit with specific error handling
        try:
            logger.info(f"Attempting to commit sync config for user {current_user.email}")
            db.commit()
            logger.info(f"Successfully committed sync config for user {current_user.email}")
        except Exception as commit_err:
            db.rollback()
            logger.error(f"Database commit failed when saving sync config: {commit_err}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save sync configuration to database."
            )
            
        # Return the original Pydantic model as the response
        return sync_config
    except HTTPException:
        raise


async def process_folder_sync(user_email: str, folder_id: str, task_id: str, start_date: Optional[str] = None):
    """Background task to process folder synchronization."""
    try:
        # Update status to 'syncing'
        active_sync_tasks[task_id]['statuses'][folder_id]['status'] = 'syncing'
        active_sync_tasks[task_id]['statuses'][folder_id]['progress'] = 0
        
        # Initialize the Outlook service with user email
        outlook_service = await OutlookService.create(user_email)
        
        # Get folder details
        folder_info = await outlook_service.get_folder_details(folder_id)
        total_items = folder_info.get('totalItemCount', 0)
        
        # Update total items count
        active_sync_tasks[task_id]['statuses'][folder_id]['totalItems'] = total_items
        
        if total_items == 0:
            # No items to process
            active_sync_tasks[task_id]['statuses'][folder_id]['status'] = 'completed'
            active_sync_tasks[task_id]['statuses'][folder_id]['progress'] = 100
            active_sync_tasks[task_id]['statuses'][folder_id]['lastSync'] = datetime.now(timezone.utc).isoformat()
            return
        
        # Get messages from folder (implement pagination for large folders)
        processed_count = 0
        page_size = 50
        
        # If no start date specified, default to one month ago
        if not start_date:
            one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
            start_date = one_month_ago.strftime("%Y-%m-%d")
            logger.info(f"No start date specified for folder {folder_id}. Defaulting to one month ago: {start_date}")
        
        # Construct filter params for start date
        params = {"top": page_size}
        if start_date:
            # Convert date string to ISO format for filtering
            try:
                filter_date = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                # Format date exactly as required by Microsoft Graph API
                formatted_date = filter_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                params["filter"] = f"receivedDateTime ge {formatted_date}"
                logger.info(f"Filtering messages from folder {folder_id} with start date: {start_date}")
            except ValueError:
                logger.error(f"Invalid start date format: {start_date}. Using no date filter.")
        
        # Fetch the first page of messages with optional date filter
        messages = await outlook_service.list_messages(folder_id, **params)
        
        while messages:
            # Process each message
            for msg in messages:
                # Here you would implement the delta sync logic
                # For now, we'll just update the progress
                processed_count += 1
                progress = min(100, (processed_count / total_items) * 100)
                
                # Update task status
                active_sync_tasks[task_id]['statuses'][folder_id]['progress'] = progress
                active_sync_tasks[task_id]['statuses'][folder_id]['itemsProcessed'] = processed_count
            
            # Check if there are more messages to process
            if len(messages) < page_size:
                break
                
            # Fetch the next page
            next_params = params.copy()
            next_params["skip"] = processed_count
            next_messages = await outlook_service.list_messages(
                folder_id, 
                **next_params
            )
            
            if not next_messages:
                break
                
            messages = next_messages
        
        # Mark as completed
        active_sync_tasks[task_id]['statuses'][folder_id]['status'] = 'completed'
        active_sync_tasks[task_id]['statuses'][folder_id]['progress'] = 100
        active_sync_tasks[task_id]['statuses'][folder_id]['lastSync'] = datetime.now(timezone.utc).isoformat()
        
    except Exception as e:
        logger.error(f"Error processing folder sync: {e}")
        # Update status to 'error'
        if task_id in active_sync_tasks and folder_id in active_sync_tasks[task_id]['statuses']:
            active_sync_tasks[task_id]['statuses'][folder_id]['status'] = 'error'
            active_sync_tasks[task_id]['statuses'][folder_id]['error'] = str(e)


@router.post("/start", response_model=Dict[str, Any])
async def start_sync(
    sync_request: SyncFolderRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Start synchronizing selected Outlook folders."""
    try:
        # Create a new task ID
        task_id = str(uuid.uuid4())
        
        # Initialize Outlook service to get folder information
        outlook_service = await OutlookService.create(current_user.email)
        
        # Get information about each folder
        statuses = {}
        for folder_id in sync_request.folders:
            try:
                folder_info = await outlook_service.get_folder_details(folder_id)
                folder_name = folder_info.get('displayName', folder_id)
                
                statuses[folder_id] = {
                    'folder': folder_name,
                    'folderId': folder_id,
                    'status': 'idle',
                    'progress': 0,
                    'itemsProcessed': 0,
                    'totalItems': folder_info.get('totalItemCount', 0)
                }
            except Exception as e:
                logger.error(f"Error getting folder details for {folder_id}: {e}")
                statuses[folder_id] = {
                    'folder': folder_id,
                    'folderId': folder_id,
                    'status': 'error',
                    'progress': 0,
                    'itemsProcessed': 0,
                    'totalItems': 0,
                    'error': f"Failed to get folder details: {str(e)}"
                }
        
        # Store the task information
        active_sync_tasks[task_id] = {
            'user_email': current_user.email,
            'folders': sync_request.folders,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'statuses': statuses,
            'start_date': sync_request.startDate
        }
        
        # Start background tasks for each folder
        for folder_id in sync_request.folders:
            if statuses[folder_id]['status'] != 'error':
                background_tasks.add_task(
                    process_folder_sync,
                    current_user.email,
                    folder_id,
                    task_id,
                    sync_request.startDate
                )
        
        return {
            'task_id': task_id,
            'message': 'Sync started for selected folders',
            'statuses': list(statuses.values())
        }
    except Exception as e:
        logger.error(f"Error starting sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start folder synchronization: {str(e)}"
        )


@router.get("/status", response_model=List[SyncStatus])
async def get_sync_status(
    current_user: User = Depends(get_current_active_user)
):
    """Get the status of active sync tasks for the current user."""
    try:
        # Find tasks for the current user
        user_statuses = []
        for task_id, task_info in active_sync_tasks.items():
            if task_info['user_email'] == current_user.email:
                # Convert the dictionary of statuses to a list
                for folder_id, status in task_info['statuses'].items():
                    user_statuses.append(SyncStatus(**status))
        
        return user_statuses
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sync status"
        )


@router.post("/stop", response_model=Dict[str, Any])
async def stop_sync(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Stop any ongoing or scheduled Outlook sync for the current user."""
    try:
        # Get the user record from the database
        user_db = db.query(UserDB).filter(UserDB.email == current_user.email).first()
        
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Call the function to cancel any pending sync tasks
        success = cancel_user_sync_tasks(str(user_db.id))
        
        if success:
            return {"message": "Sync stopped successfully", "status": "success"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to stop sync"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop sync: {str(e)}"
        )


@router.get("/last-sync", response_model=LastSyncInfo)
async def get_last_sync_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the timestamp of the last Outlook sync from the database."""
    try:
        # Get the user record from the database
        user_db = db.query(UserDB).filter(UserDB.email == current_user.email).first()
        
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get active folder info if available
        folder_id = None  # Changed variable name to folder_id to be more explicit
        items_processed = None
        for task_id, task_info in active_sync_tasks.items():
            if task_info['user_email'] == current_user.email:
                # Find the most recently completed folder sync
                for current_folder_id, status in task_info['statuses'].items():
                    if status['status'] == 'completed' and status['lastSync']:
                        # Use folder ID instead of folder name 
                        folder_id = current_folder_id  # Return the folder ID, not the name
                        items_processed = status['itemsProcessed']
                        # Log for debugging
                        logger.info(f"Last sync info found: folder_id={folder_id}, items={items_processed}")
                        break
        
        # Log the data being returned
        logger.info(f"Returning last sync info: last_sync={user_db.last_outlook_sync}, folder={folder_id}")
        
        return LastSyncInfo(
            last_sync=user_db.last_outlook_sync,
            items_processed=items_processed,
            folder=folder_id  # This was incorrectly returning the folder name instead of ID
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving last sync info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve last sync information"
        ) 