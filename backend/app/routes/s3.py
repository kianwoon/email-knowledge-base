# backend/app/routes/s3.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Tuple
import logging
import boto3 # Import boto3 to use session type hint
from collections import defaultdict

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user_or_token_owner # Use the correct dependency
from app.models.user import UserDB # Import UserDB for type hinting
from app.schemas.s3 import (
    S3ConfigCreate, S3ConfigResponse, S3Bucket, S3Object, S3IngestRequest, S3SyncItem, S3SyncItemCreate,
    TriggerIngestResponse # <<< Import the new response schema
)
from app.crud import crud_aws_credential, crud_s3_sync_item, crud_ingestion_job
from app.schemas.ingestion_job import IngestionJobCreate # Need schema for creating jobs
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

@router.delete(
    "/configure",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear AWS S3 Configuration",
    description="Removes the AWS IAM Role ARN configuration for the current user."
)
async def clear_s3_configuration(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"User {current_user.email} attempting to clear AWS Role ARN configuration.")
    removed_cred = crud_aws_credential.remove_aws_credential(db=db, user_email=current_user.email)
    if not removed_cred:
        # If no credential existed, it's not an error, just log it.
        logger.info(f"No AWS configuration found for user {current_user.email} to clear.")
    else:
        logger.info(f"Successfully cleared AWS Role ARN for user {current_user.email}.")
    # Return No Content on success (or if it was already clear)
    return

# --- Helper Dependency for Getting Assumed Role Session --- 
# This avoids repeating the logic in multiple endpoints
async def get_assumed_s3_session(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
) -> boto3.Session:
    try:
        # Fetching role_arn here is no longer strictly necessary as get_aws_session_for_user does it,
        # but it's useful for logging or potential checks if needed.
        # role_arn = s3_service.get_user_aws_credentials(db=db, user_email=current_user.email)
        
        # Call the updated service function, passing db instead of role_arn
        session = await s3_service.get_aws_session_for_user(db=db, user_email=current_user.email)
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
        buckets = await s3_service.list_buckets(session=assumed_session)
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
        objects = await s3_service.list_objects(session=assumed_session, bucket_name=bucket_name, prefix=clean_prefix)
        return objects
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error listing S3 objects in s3://{bucket_name}/{clean_prefix}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list S3 objects.")

# --- S3 Ingestion Endpoint --- 

@router.post(
    "/ingest",
    response_model=TriggerIngestResponse, # <<< Use the new response model
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process Pending S3 Sync Items",
    description="Groups pending S3 files/folders by source and initiates background tasks for each."
)
async def trigger_s3_ingestion(
    # No request body needed
    assumed_session: boto3.Session = Depends(get_assumed_s3_session), # Verify config first
    current_user: UserDB = Depends(get_current_active_user_or_token_owner),
    db: Session = Depends(get_db)
):
    logger.info(f"User {current_user.email} requested processing of pending S3 sync items.")

    # Attempt to ensure session reads latest data
    try:
        logger.debug("Expiring session state before fetching pending items.")
        db.expire_all()
    except Exception as expire_err:
        logger.warning(f"Error calling db.expire_all(): {expire_err}")

    # 1. Fetch Pending Items
    pending_items = crud_s3_sync_item.get_pending_items_by_user(db=db, user_id=current_user.email)
    logger.info(f"Found {len(pending_items)} pending items for user {current_user.email}.")

    if not pending_items:
        logger.info(f"No pending S3 sync items found for user {current_user.email}. No tasks submitted.")
        # <<< Return the new response type for NO_OP
        return TriggerIngestResponse(
            task_id=None,
            status="NO_OP",
            message="No pending S3 sync items found."
        )

    # 2. Group by Source (bucket, key/prefix)
    # We treat each unique pending sync item as a separate job request
    # If you want to group items under the same prefix into one job, logic needs adjustment here.
    jobs_to_submit: Dict[Tuple[str, str], S3SyncItem] = {}
    for item in pending_items:
        source_tuple = (item.s3_bucket, item.s3_key)
        # Prioritize existing entries? Here we just take the first one encountered.
        if source_tuple not in jobs_to_submit:
            jobs_to_submit[source_tuple] = item
            logger.info(f"Identified potential job for s3://{item.s3_bucket}/{item.s3_key} (from item ID {item.id})")
        else:
             logger.warning(f"Multiple pending S3SyncItems found for s3://{item.s3_bucket}/{item.s3_key}. Will create job based on first encountered (item ID {jobs_to_submit[source_tuple].id}). Skipping item ID {item.id}.")

    submitted_tasks_details: List[Dict[str, Optional[str]]] = [] # Store basic task info
    failed_submissions = 0

    # 3. Loop Through Groups (Unique Sources)
    for (bucket, key_or_prefix), source_item in jobs_to_submit.items():
        job_created = False
        task_submitted = False
        new_job_id = None
        task_id = None
        error_detail = None

        try:
            # 4. Create IngestionJob
            job_details = {"bucket": bucket}
            if key_or_prefix.endswith('/'):
                job_details["prefix"] = key_or_prefix
            else:
                job_details["key"] = key_or_prefix
            
            job_schema = IngestionJobCreate(source_type='s3', job_details=job_details)
            
            logger.info(f"Attempting to create IngestionJob for user {current_user.email}, source s3://{bucket}/{key_or_prefix}")
            db_job = crud_ingestion_job.create_ingestion_job(db=db, job_in=job_schema, user_id=current_user.email)
            
            if not db_job:
                # Handle potential DB error during job creation
                logger.error(f"Failed to create IngestionJob DB record for s3://{bucket}/{key_or_prefix}")
                error_detail = f"Database error creating job for s3://{bucket}/{key_or_prefix}"
                failed_submissions += 1
                continue # Skip to next source
            
            job_created = True
            new_job_id = db_job.id
            logger.info(f"Created IngestionJob ID {new_job_id} for s3://{bucket}/{key_or_prefix}")

            # 5. Trigger Celery Task
            task = process_s3_ingestion_task.delay(job_id=new_job_id)
            task_submitted = True
            task_id = task.id
            logger.info(f"Submitted Celery task {task_id} for IngestionJob ID {new_job_id}")

            # 6. Optional: Link task ID back to job
            # Make sure db.commit() happens LATER or is handled by the background task
            crud_ingestion_job.update_job_status(db=db, job_id=new_job_id, status='pending', celery_task_id=task_id)
            # No db.commit() here!

            submitted_tasks_details.append({
                "task_id": task_id,
                "source": f"s3://{bucket}/{key_or_prefix}"
            })

        except Exception as e:
            logger.error(f"Failed processing/submitting task for s3://{bucket}/{key_or_prefix}: {e}", exc_info=True)
            error_detail = f"Error submitting task for s3://{bucket}/{key_or_prefix}: {e}"
            failed_submissions += 1
            # If job was created but task submission failed, mark job as failed
            if job_created and new_job_id is not None and not task_submitted:
                try:
                    crud_ingestion_job.update_job_status(db=db, job_id=new_job_id, status='failed', error_message=f"Celery task submission failed: {e}")
                except Exception as update_err:
                    logger.error(f"CRITICAL: Failed to mark IngestionJob {new_job_id} as failed after task submission error: {update_err}")
            # Don't append to submitted_tasks_details on failure

    # Log summary
    num_successful = len(submitted_tasks_details)
    logger.info(f"Finished triggering S3 ingestion jobs for user {current_user.email}. Submitted: {num_successful}, Failed Submissions: {failed_submissions}")

    # Handle outcomes
    if num_successful == 0:
        # This means items were found, but ALL submissions failed
        logger.error(f"Found {len(pending_items)} pending items but failed to submit any tasks for user {current_user.email}.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Found {len(pending_items)} pending S3 items, but failed to submit any processing tasks. Check server logs."
        )
    
    # <<< Return the new response type for PENDING
    first_task_id = submitted_tasks_details[0]["task_id"]
    message = f"S3 ingestion task submitted for {submitted_tasks_details[0]['source']} (Task ID: {first_task_id})"
    if num_successful > 1:
        message = f"{num_successful} S3 ingestion tasks submitted. First task ID: {first_task_id}"
        
    return TriggerIngestResponse(
        task_id=first_task_id, 
        status="PENDING",
        message=message
    )

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
    summary="Get S3 Sync List (Pending Only)",
    description="Retrieves the current list of PENDING S3 items marked for sync by the user."
)
def get_s3_sync_list(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.debug(f"Fetching PENDING S3 sync list for user {current_user.email}")
    sync_items = crud_s3_sync_item.get_pending_items_by_user(db=db, user_id=current_user.email)
    return [S3SyncItem.model_validate(item) for item in sync_items]

@router.get(
    "/sync-list/history",
    response_model=List[S3SyncItem],
    summary="Get S3 Sync History",
    description="Retrieves the most recent completed/failed S3 items for the user."
)
def get_s3_sync_history(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of history items to return."),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.debug(f"Fetching S3 sync history for user {current_user.email} (limit: {limit})")
    history_items = crud_s3_sync_item.get_completed_or_failed_items_by_user(
        db=db, user_id=current_user.email, limit=limit
    )
    return [S3SyncItem.model_validate(item) for item in history_items]

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
    # Fetch the item first to ensure it belongs to the current user
    db_item = db.get(S3SyncItem, item_id) # Use db.get for primary key lookup
    if not db_item:
        logger.warning(f"Attempt to remove non-existent S3 sync item ID: {item_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync item not found.")
    
    if db_item.user_id != current_user.email:
        logger.warning(f"User {current_user.email} attempted to remove S3 sync item ID {item_id} belonging to another user ({db_item.user_id}).")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot remove sync item belonging to another user.")

    # If checks pass, remove the item
    removed_item = crud_s3_sync_item.remove_item(db=db, db_item=db_item)
    if removed_item is None:
        # Handle potential deletion error
        logger.error(f"Failed to remove S3 sync item ID {item_id} from database.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove sync item.")

    logger.info(f"Successfully removed S3 sync item ID {item_id} for user {current_user.email}")
    return S3SyncItem.model_validate(removed_item) 