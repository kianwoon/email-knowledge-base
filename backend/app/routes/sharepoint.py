from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Path
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone

# --- Correct DB Session Dependency Import ---
from sqlalchemy.orm import Session
from app.db.session import get_db # Corrected path
# --- End Correction ---

from app.models.sharepoint import (
    SharePointSite,
    SharePointDrive,
    SharePointItem,
    SharePointDownloadRequest,
    UsedInsight,
    RecentDriveItem
)
# +++ Add SyncList Models +++
from app.models.sharepoint_sync import SharePointSyncItem, SharePointSyncItemCreate 

from app.models.user import User
from app.models.tasks import TaskStatus, TaskType # Keep import for potential uncommenting
# +++ Add CRUD imports +++
from app.crud import crud_sharepoint_sync_item
# from app.services.task_manager import TaskManager, get_task_manager # REMOVE TaskManager import
from app.tasks.sharepoint_tasks import process_sharepoint_batch_task # Import the Celery task
# +++ Add TaskStatusEnum +++
from app.models.tasks import TaskStatusEnum

from app.dependencies.auth import get_current_active_user_or_token_owner
from app.services.sharepoint import SharePointService
# Import TaskManager only if needed and uncommented
# from app.services.task_manager import TaskManager, get_task_manager 

# --- Import ProcessSyncResponse from tasks schema --- 
# from app.schemas.sharepoint import (
#    ProcessSyncResponse
# )
from app.schemas.tasks import ProcessSyncResponse # <-- Corrected import location
# --- End Import Correction --- 

# +++ Add IngestionJob imports +++
from app.crud import crud_ingestion_job
from app.schemas.ingestion_job import IngestionJobCreate

router = APIRouter()
logger = logging.getLogger(__name__)

# Helper function to check token and instantiate service (Internal to this module)
def _get_service_instance(current_user: User) -> SharePointService:
    if not current_user.ms_access_token:
        logger.warning(f"User {current_user.id} / {current_user.email} attempted SharePoint access without MS token.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"}, 
        )
    try:
        return SharePointService(current_user.ms_access_token)
    except ValueError as ve:
        logger.error(f"Failed to initialize SharePointService for user {current_user.id}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize SharePoint service."
        )

@router.get(
    "/sites", 
    response_model=List[SharePointSite],
    summary="List SharePoint Sites",
    description="Get a list of SharePoint sites the user can access."
)
async def list_sites(
    # Removed search query for simplicity, can be added back if needed
    # search: Optional[str] = Query(None, description="Optional search query to filter sites."),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"Fetching SharePoint sites for user {current_user.id}")
    try:
        service = _get_service_instance(current_user)
        sites_data = await service.search_accessible_sites()

        # Convert SharePointSite objects to dictionaries for JSON response
        sites_list = [site.dict() for site in sites_data]
        return sites_list
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error fetching SharePoint sites for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve SharePoint sites.")

@router.get(
    "/sites/{site_id}/drives", 
    response_model=List[SharePointDrive],
    summary="List Site Document Libraries (Drives)",
    description="Get a list of document libraries (drives) within a site."
)
async def list_drives(
    site_id: str,
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    service = _get_service_instance(current_user)
    try:
        drives_data = await service.list_drives_for_site(site_id)
        return drives_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching drives for site {site_id} for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve document libraries.")

@router.get(
    "/drives/{drive_id}/items", 
    response_model=List[SharePointItem],
    summary="List Drive Items (Files/Folders)",
    description="Get items within a drive's root or a specific folder path."
)
async def list_drive_items(
    drive_id: str,
    item_id: Optional[str] = Query(None, description="The ID of the parent folder. If omitted, lists root items."),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    service = _get_service_instance(current_user)
    try:
        items_data = await service.list_drive_items(drive_id, item_id=item_id)
        return items_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching items for drive {drive_id} item_id '{item_id}' for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve drive items.")

@router.get(
    "/drives/{drive_id}/search", 
    response_model=List[SharePointItem],
    summary="Search Drive",
    description="Search for items within a drive."
)
async def search_drive(
    drive_id: str,
    query: str = Query(..., min_length=1, description="Search query string."),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    service = _get_service_instance(current_user)
    try:
        results = await service.search_drive(drive_id, query.strip())
        return results
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error searching drive {drive_id} query '{query}' for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to perform search.")

# --- Download/Process Endpoint (Commented out until TaskManager is ready) ---
# Requires uncommenting imports for TaskManager, TaskStatus, TaskType
# @router.post(
#     "/drives/download", 
#     response_model=TaskStatus,
#     status_code=status.HTTP_202_ACCEPTED,
#     summary="Download and Process SharePoint File",
#     description="Initiates a background task to download and process a SharePoint file."
# )
# async def download_and_process_file(
#     request_body: SharePointDownloadRequest,
#     current_user: User = Depends(get_current_active_user),
#     task_manager: TaskManager = Depends(get_task_manager), 
# ):
#     service = _get_service_instance(current_user) # Still check token here
#     logger.info(f"Download request for drive={request_body.drive_id}, item={request_body.item_id} by user {current_user.id}")
#     
#     task_payload = {
#         "drive_id": request_body.drive_id,
#         "item_id": request_body.item_id,
#         "user_id": str(current_user.id), 
#         "access_token": current_user.ms_access_token # Pass token for the task
#     }
# 
#     try:
#         task = await task_manager.submit_task(
#             task_type=TaskType.PROCESS_SHAREPOINT_FILE,
#             payload=task_payload,
#             user_id=str(current_user.id)
#         )
#         logger.info(f"Submitted SharePoint download task {task.task_id} for user {current_user.id}")
#         # Return the initial status provided by submit_task
#         return task 
#     except Exception as e:
#         logger.error(f"Failed to submit SharePoint download task for user {current_user.id}: {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to initiate SharePoint file processing."
#         ) 

# --- Insight Routes (New) ---

@router.get("/quick-access", response_model=List[UsedInsight], summary="Get Quick Access Items")
async def get_quick_access(
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    """Retrieves documents recently used by the signed-in user."""
    logger.info(f"Fetching quick access items for user {current_user.email}")
    service = _get_service_instance(current_user)
    try:
        items = await service.get_quick_access_items()
        # Pydantic automatically converts datetime etc. for the response model
        return items
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching quick access items for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve quick access items.")

# Placeholder for Shared Items route
# @router.get("/shared-with-me", ...) ... 

# +++ Add Route for Recent Drive Items +++
@router.get("/drive/recent", response_model=List[RecentDriveItem])
async def get_my_recent_files(
    top: int = Query(25, ge=1, le=100, description="Number of items to return."), # Optional parameter
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    """Gets the user's most recently used/modified drive items."""
    service = _get_service_instance(current_user) # Helper likely checks token
    try:
        # Changed from get_my_recent_drive_items to get_recent_drive_items
        recent_items = await service.get_recent_drive_items(token=current_user.ms_access_token, top=top)
        return recent_items
    except HTTPException as e:
        # Log detailed error before re-raising
        logger.error(f"sharepoint.errors.fetchRecentTitleFailed to retrieve recent items for user {current_user.email}: {e.detail}", exc_info=True)
        raise HTTPException(status_code=e.status_code, detail="Failed to retrieve recent items.")
    except Exception as e:
        logger.error(f"sharepoint.errors.fetchRecentUnexpected unexpected error retrieving recent items for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching recent items.")
# --- End New Route --- 

# +++ Sync List Routes +++

@router.post(
    "/sync-list/add",
    response_model=SharePointSyncItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add Item to Sync List",
    description="Adds a SharePoint file or folder to the user's sync list."
)
async def add_sync_list_item(
    item_data: SharePointSyncItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"User {current_user.email} adding item {item_data.sharepoint_item_id} ('{item_data.item_name}') to sync list.")
    
    try:
        # Call CRUD function with user_email
        created_item = crud_sharepoint_sync_item.add_item(db=db, item_in=item_data, user_email=current_user.email)
        
        if created_item is None:
             logger.warning(f"Item {item_data.sharepoint_item_id} already in sync list for user {current_user.email}. Add request ignored.")
             raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail=f"Item '{item_data.item_name}' already exists in the sync list."
             )
        
        logger.info(f"Successfully added item {created_item.id} to sync list for user {current_user.email}.")
        return created_item
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Failed to add item {item_data.sharepoint_item_id} to sync list for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add item '{item_data.item_name}' to sync list due to an internal error."
        )

@router.delete(
    "/sync-list/remove/{sharepoint_item_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove Item from Sync List",
    description="Removes a specific item from the user's sync list using its SharePoint ID."
)
async def remove_sync_list_item(
    sharepoint_item_id: str = Path(..., description="The SharePoint ID of the item to remove."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"User {current_user.email} requesting removal of item {sharepoint_item_id} from sync list.")
    deleted_item = crud_sharepoint_sync_item.remove_item(
        db=db, user_email=current_user.email, sharepoint_item_id=sharepoint_item_id
    )
    if deleted_item is None:
        logger.warning(f"Item {sharepoint_item_id} not found in sync list for user {current_user.email} or removal failed.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found in sync list."
        )
    logger.info(f"Successfully removed item {sharepoint_item_id} from sync list for user {current_user.email}.")
    return {"message": "Item removed successfully"}

@router.get(
    "/sync-list",
    response_model=List[SharePointSyncItem],
    summary="Get User Sync List",
    description="Retrieves ALL items from the user's sync list, regardless of status."
)
async def get_sync_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"Fetching ALL sync list items for user {current_user.email}")
    # Call the CRUD function to get ALL items for the user
    items = crud_sharepoint_sync_item.get_sync_list_for_user(db=db, user_email=current_user.email)
    return items

@router.get(
    "/sync-history",
    response_model=List[SharePointSyncItem],
    summary="Get Completed Sync History",
    description="Retrieves items that have been successfully processed (status='completed')."
)
async def get_sync_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"Fetching completed sync history for user {current_user.email}")
    try:
        completed_items = crud_sharepoint_sync_item.get_completed_sync_items_for_user(
            db=db,
            user_email=current_user.email
        )
        return completed_items
    except Exception as e:
        logger.error(f"Error fetching sync history for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sync history."
        )

@router.post(
    "/sync-list/process",
    response_model=ProcessSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process User Sync List",
    description="Creates an ingestion job and initiates a background task to process pending items."
)
async def process_sync_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    user_email_str = current_user.email

    if not user_email_str:
        logger.error(f"User object for ID {current_user.id} is missing email address.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User email not available.")

    logger.info(f"User {user_email_str} initiating processing of sync list.")

    # 1. Fetch Pending Items (to check if there's anything to do)
    pending_sync_items_db = crud_sharepoint_sync_item.get_active_sync_list_for_user(db=db, user_email=user_email_str)
    if not pending_sync_items_db:
        logger.info(f"No active (pending/processing) items in sync list for user {user_email_str}. Nothing to process.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending items found in the sync list to process."
        )
    
    # Extract item details for job logging/metadata if desired (optional)
    job_details = {
        "item_count": len(pending_sync_items_db),
        "trigger_time": datetime.now(timezone.utc).isoformat()
    }

    # 2. Create IngestionJob Record
    new_job_id = None
    try:
        job_schema = IngestionJobCreate(
            user_email=user_email_str,
            source_type='sharepoint',
            status='pending', # Start as pending, task updates to processing
            job_details=job_details
        )
        db_job = crud_ingestion_job.create_ingestion_job(db=db, job_in=job_schema, user_id=user_email_str)
        if not db_job:
             raise Exception("Failed to create IngestionJob record in database.")
        new_job_id = db_job.id
        logger.info(f"Created IngestionJob ID {new_job_id} for user {user_email_str} SharePoint sync.")
        # Commit the job creation here
        db.commit()
    except Exception as job_create_err:
        db.rollback() # Rollback if job creation fails
        logger.error(f"Failed to create IngestionJob for user {user_email_str}: {job_create_err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create processing job record."
        )

    # 3. Submit Celery Task with IngestionJob ID
    task_id = None
    try:
        # Pass only the job ID to the task
        task = process_sharepoint_batch_task.delay(ingestion_job_id=new_job_id)
        task_id = task.id
        logger.info(f"Submitted SharePoint batch processing task {task_id} for IngestionJob ID {new_job_id}.")

        # 4. Link Celery Task ID back to IngestionJob
        try:
            crud_ingestion_job.update_job_status(db=db, job_id=new_job_id, celery_task_id=task_id)
            db.commit() # Commit the task ID update
            logger.info(f"Linked Celery task {task_id} to IngestionJob {new_job_id}.")
        except Exception as link_err:
            db.rollback()
            logger.error(f"Failed to link Celery task {task_id} to IngestionJob {new_job_id}: {link_err}", exc_info=True)

        # 5. Return Response (Celery Task ID)
        return ProcessSyncResponse(task_id=task_id)

    except Exception as e:
        logger.error(f"Failed to submit SharePoint sync list processing task for user {user_email_str} / Job {new_job_id}: {e}", exc_info=True)
        if new_job_id is not None:
            try:
                crud_ingestion_job.update_job_status(db=db, job_id=new_job_id, status='failed', error_message=f"Celery task submission failed: {e}")
                db.commit()
            except Exception as update_err:
                 logger.error(f"CRITICAL: Failed to mark IngestionJob {new_job_id} as failed after task submission error: {update_err}", exc_info=True)
                 db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate sync list processing task."
        )

# +++ End Sync List Routes +++ 