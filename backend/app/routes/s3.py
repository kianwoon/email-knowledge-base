# backend/app/routes/s3.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import boto3 # Import boto3 to use session type hint

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user_or_token_owner # Use the correct dependency
from app.models.user import UserDB # Import UserDB for type hinting
from app.schemas.s3 import (
    S3ConfigCreate, S3ConfigResponse, S3Bucket, S3Object, S3IngestRequest, S3SyncItem, S3SyncItemCreate
)
from app.crud import crud_aws_credential, crud_s3_sync_item
from app.services import s3 as s3_service # Use alias to avoid name conflict
from app.tasks.s3_tasks import process_s3_ingestion_task # <<< Import the Celery task
from app.schemas.tasks import TaskStatusResponse # <<< Import task status schema for response

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Configuration Endpoints ---

@router.post(
    "/configure", # Relative path within this router
    response_model=S3ConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Configure AWS S3 Role",
    description="Set or update the AWS IAM Role ARN for S3 access for the current user."
)
async def configure_s3(
    config_in: S3ConfigCreate,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"User {current_user.email} attempting to configure AWS Role ARN.")
    try:
        # Simple ARN format validation
        if not config_in.role_arn.startswith("arn:aws:iam::") or ":role/" not in config_in.role_arn:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid AWS Role ARN format.")

        aws_cred = crud_aws_credential.create_or_update_aws_credential(
            db=db, user_email=current_user.email, config_in=config_in
        )
        logger.info(f"Successfully configured AWS Role ARN for user {current_user.email}.")
        return S3ConfigResponse.model_validate(aws_cred)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error configuring AWS Role ARN for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save AWS configuration.")

@router.get(
    "/configure",
    response_model=Optional[S3ConfigResponse],
    summary="Get AWS S3 Configuration",
    description="Retrieve the currently configured AWS IAM Role ARN for S3 access for the current user."
)
async def get_s3_configuration(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.debug(f"Fetching AWS configuration for user {current_user.email}")
    aws_cred = crud_aws_credential.get_aws_credential_by_user_email(db, user_email=current_user.email)
    if not aws_cred:
        logger.info(f"No AWS configuration found for user {current_user.email}")
        return None # Return null/empty body for not configured
    return S3ConfigResponse.model_validate(aws_cred)

# --- Helper Dependency for Getting Assumed Role Session --- 
# This avoids repeating the logic in multiple endpoints
async def get_assumed_s3_session(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
) -> boto3.Session:
    try:
        role_arn = s3_service.get_user_aws_credentials(db=db, user_email=current_user.email)
        session = s3_service.get_aws_session_for_user(role_arn=role_arn, user_email=current_user.email)
        return session
    except HTTPException as e:
        # Re-raise HTTP exceptions from the service layer (config errors, STS errors)
        raise e
    except Exception as e:
        # Catch unexpected errors during session acquisition
        logger.error(f"Unexpected error getting AWS session for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to establish AWS session.")

# --- S3 Browsing Endpoints --- 

@router.get(
    "/buckets",
    response_model=List[S3Bucket],
    summary="List Accessible S3 Buckets",
    description="Lists S3 buckets accessible via the user's configured assumed role."
)
async def list_s3_buckets(
    assumed_session: boto3.Session = Depends(get_assumed_s3_session)
):
    logger.info(f"Requesting S3 bucket list using assumed session.")
    try:
        buckets = s3_service.list_buckets(session=assumed_session)
        return buckets
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error listing S3 buckets: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list S3 buckets.")

@router.get(
    "/objects",
    response_model=List[S3Object],
    summary="List S3 Objects (Files/Folders)",
    description="Lists objects (files and folders) within a specific S3 bucket and prefix."
)
async def list_s3_objects(
    bucket_name: str = Query(..., description="The name of the S3 bucket."),
    prefix: Optional[str] = Query("", description="The prefix (folder path) to list. Ends with '/' for folders. Empty for root."),
    assumed_session: boto3.Session = Depends(get_assumed_s3_session)
):
    clean_prefix = prefix.lstrip('/') if prefix else ""
    logger.info(f"Requesting object list for s3://{bucket_name}/{clean_prefix} using assumed session.")
    try:
        objects = s3_service.list_objects(session=assumed_session, bucket_name=bucket_name, prefix=clean_prefix)
        return objects
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error listing S3 objects in s3://{bucket_name}/{clean_prefix}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list S3 objects.")

# --- S3 Ingestion Endpoint --- 

@router.post(
    "/ingest",
    response_model=TaskStatusResponse, # Use TaskStatusResponse model
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process Pending S3 Sync Items",
    description="Initiates a background task to process all pending S3 files/folders in the user's sync list."
)
async def trigger_s3_ingestion(
    # No request body needed anymore
    # Verify config works before queueing by depending on the session
    assumed_session: boto3.Session = Depends(get_assumed_s3_session),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner),
    db: Session = Depends(get_db) # <<< Add DB dependency
):
    logger.info(f"User {current_user.email} requested processing of pending S3 sync items.")

    # Check if there are actually pending items for the user
    pending_items = crud_s3_sync_item.get_pending_items_by_user(db=db, user_id=current_user.email)
    
    # +++ ADD DETAILED LOGGING +++
    logger.info(f"Query for pending items for user {current_user.email} returned: {pending_items}")
    # Log details of each found item
    if pending_items:
        for item in pending_items:
            logger.info(f"  - Found pending item: ID={item.id}, Bucket={item.s3_bucket}, Key={item.s3_key}, Status={item.status}")
    # --- END LOGGING --- 
            
    if not pending_items:
        logger.info(f"No pending S3 sync items found for user {current_user.email}. No task submitted.")
        # Return 200 OK but indicate nothing was started
        return TaskStatusResponse(
            task_id=None, # No task ID generated
            status="NO_OP", 
            message="No pending S3 items found to process."
        )

    # We already verified config/STS works by depending on get_assumed_s3_session

    # Prepare payload for Celery task - only needs user_email
    task_payload = {
        "user_email": current_user.email,
    }

    # Submit task to Celery
    try:
        task = process_s3_ingestion_task.delay(**task_payload)
        logger.info(f"Submitted S3 ingestion task {task.id} to process pending items for user {current_user.email}")
        # Return task ID and initial status
        return TaskStatusResponse(
            task_id=task.id, 
            status="PENDING", 
            message=f"S3 ingestion task submitted to process {len(pending_items)} pending item(s)."
        )
    except Exception as e:
        logger.error(f"Failed to submit S3 ingestion task for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start S3 ingestion task.")

# --- S3 Sync List Endpoints ---

@router.post(
    "/sync-list/add",
    response_model=S3SyncItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add S3 Item to Sync List",
    description="Adds a specific S3 file or prefix to the user's list of items to be synced."
)
def add_s3_sync_item(
    item_in: S3SyncItemCreate,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"User {current_user.email} attempting to add S3 item to sync list: {item_in.s3_bucket}/{item_in.s3_key}")
    # Basic validation
    if item_in.item_type not in ['file', 'prefix']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item_type. Must be 'file' or 'prefix'.")
    if item_in.item_type == 'prefix' and not item_in.s3_key.endswith('/'):
        # Ensure prefixes end with a slash for consistency, though S3 API handles both
        item_in.s3_key += '/'
        
    db_item = crud_s3_sync_item.add_item(db=db, item_in=item_in, user_id=current_user.email)
    if db_item is None:
        # Item already exists (handled by unique constraint)
        existing_item = crud_s3_sync_item.get_item_by_user_and_key(db=db, user_id=current_user.email, s3_bucket=item_in.s3_bucket, s3_key=item_in.s3_key)
        if existing_item:
            logger.warning(f"Item {item_in.s3_bucket}/{item_in.s3_key} already in sync list for user {current_user.email}, returning existing (ID: {existing_item.id}).")
            return S3SyncItem.model_validate(existing_item)
        else:
            # This case shouldn't happen if constraint is working, but handle defensively
            logger.error(f"IntegrityError during add_item for {item_in.s3_bucket}/{item_in.s3_key} but couldn't find existing item.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error checking for existing sync item.")
            
    logger.info(f"Successfully added S3 item {db_item.s3_key} (DB ID: {db_item.id}) to sync list for user {current_user.email}")
    return S3SyncItem.model_validate(db_item) # Use model_validate for Pydantic V2

@router.get(
    "/sync-list",
    response_model=List[S3SyncItem],
    summary="Get S3 Sync List",
    description="Retrieves the current list of S3 items marked for sync by the user."
)
def get_s3_sync_list(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.debug(f"Fetching S3 sync list for user {current_user.email}")
    items = crud_s3_sync_item.get_items_by_user(db=db, user_id=current_user.email)
    return [S3SyncItem.model_validate(item) for item in items]

@router.delete(
    "/sync-list/remove/{item_id}",
    response_model=S3SyncItem, # Return the deleted item
    status_code=status.HTTP_200_OK,
    summary="Remove S3 Item from Sync List",
    description="Removes an item from the user's S3 sync list using its database ID."
)
def remove_s3_sync_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"User {current_user.email} attempting to remove S3 sync item with DB ID: {item_id}")
    # Fetch the item first to ensure it exists and belongs to the user
    db_item = db.query(crud_s3_sync_item.S3SyncItem).filter(
        crud_s3_sync_item.S3SyncItem.id == item_id,
        crud_s3_sync_item.S3SyncItem.user_id == current_user.email
    ).first()

    if not db_item:
        logger.warning(f"S3 sync item with ID {item_id} not found or does not belong to user {current_user.email}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="S3 sync item not found.")

    try:
        deleted_item_data = S3SyncItem.model_validate(db_item) # Capture data before deletion
        crud_s3_sync_item.remove_item(db=db, db_item=db_item)
        logger.info(f"Successfully removed S3 sync item {item_id} for user {current_user.email}.")
        return deleted_item_data
    except Exception as e:
        logger.error(f"Error removing S3 sync item {item_id} for user {current_user.email}: {e}", exc_info=True)
        db.rollback() # Ensure rollback on error during removal
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove S3 sync item.")

    # <<< REMOVED Placeholder response >>> 