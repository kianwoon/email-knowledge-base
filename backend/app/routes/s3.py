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
    S3ConfigCreate, S3ConfigResponse, S3Bucket, S3Object, S3IngestRequest
)
from app.crud import crud_aws_credential
from app.services import s3 as s3_service # Use alias to avoid name conflict
# from app.tasks.s3_tasks import process_s3_ingestion_task # Placeholder for Celery task
# from app.schemas.tasks import TaskStatusResponse # Placeholder for task status response

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
    # response_model=TaskStatusResponse, # Placeholder for task status
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest S3 Objects",
    description="Initiates a background task to ingest selected S3 files/folders into the knowledge base."
)
async def ingest_s3_objects(
    ingest_request: S3IngestRequest,
    # Verify config works before queueing by depending on the session
    assumed_session: boto3.Session = Depends(get_assumed_s3_session),
    current_user: UserDB = Depends(get_current_active_user_or_token_owner)
):
    logger.info(f"User {current_user.email} requested ingestion for {len(ingest_request.keys)} keys/prefixes in bucket {ingest_request.bucket}")

    if not ingest_request.keys:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No S3 keys provided for ingestion.")

    # We already verified config/STS works by depending on get_assumed_s3_session

    # Prepare payload for Celery task
    task_payload = {
        "user_email": current_user.email,
        "bucket": ingest_request.bucket,
        "keys_to_ingest": ingest_request.keys,
    }

    # Submit task to Celery (TODO - Implement the actual task first)
    # try:
    #     task = process_s3_ingestion_task.delay(**task_payload)
    #     logger.info(f"Submitted S3 ingestion task {task.id} for user {current_user.email}, bucket {ingest_request.bucket}")
    #     return TaskStatusResponse(task_id=task.id, status="PENDING", message="S3 ingestion task submitted.")
    # except Exception as e:
    #     logger.error(f"Failed to submit S3 ingestion task for user {current_user.email}: {e}", exc_info=True)
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start S3 ingestion task.")

    # Placeholder response until Celery task is implemented
    logger.warning(f"S3 ingestion task queuing not implemented yet for user {current_user.email}.")
    return {"message": "S3 ingestion request received (task queuing not implemented yet).", "status": "ACCEPTED"} 