from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import logging

from app.models.sharepoint import (
    SharePointSite,
    SharePointDrive,
    SharePointItem,
    SharePointDownloadRequest,
    UsedInsight
)
from app.models.user import User
from app.models.tasks import TaskStatus, TaskType # Keep import for potential uncommenting
from app.dependencies.auth import get_current_active_user
from app.services.sharepoint import SharePointService
# Import TaskManager only if needed and uncommented
# from app.services.task_manager import TaskManager, get_task_manager 

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
    current_user: User = Depends(get_current_active_user)
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
    current_user: User = Depends(get_current_active_user)
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
    current_user: User = Depends(get_current_active_user)
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
    current_user: User = Depends(get_current_active_user)
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
    current_user: User = Depends(get_current_active_user)
):
    """Retrieves documents recently used by the signed-in user."""
    logger.info(f"Fetching quick access items for user {current_user.id}")
    service = _get_service_instance(current_user)
    try:
        items = await service.get_quick_access_items()
        # Pydantic automatically converts datetime etc. for the response model
        return items
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching quick access items for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve quick access items.")

# Placeholder for Shared Items route
# @router.get("/shared-with-me", ...) ... 