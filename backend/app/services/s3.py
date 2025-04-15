# backend/app/services/s3.py
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import logging
from typing import List, Optional
import asyncio # Import asyncio
from asyncio import TimeoutError # Import TimeoutError
from fastapi.concurrency import run_in_threadpool # Import run_in_threadpool

from app.config import settings # Assuming settings has APP_AWS_ACCESS_KEY_ID etc.
from app.crud import crud_aws_credential
from app.schemas.s3 import S3Bucket, S3Object # Import schemas

logger = logging.getLogger(__name__)

# Define a reusable function to get user credentials
def get_user_aws_credentials(db: Session, user_email: str) -> str:
    """Fetches the configured Role ARN for the user."""
    user_cred = crud_aws_credential.get_aws_credential_by_user_email(db, user_email=user_email)
    if not user_cred or not user_cred.role_arn:
        logger.warning(f"No AWS Role ARN configured for user {user_email}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AWS Role ARN not configured for this user.")
    return user_cred.role_arn

# --- Make the function async --- 
async def get_aws_session_for_user(db: Session, user_email: str) -> boto3.Session:
    """
    Fetches the user's configured Role ARN from the DB, assumes the role using the
    application's credentials (with timeout), and returns a boto3 Session with temporary credentials.
    Now an async function.
    """
    role_session_name = f"user_s3_session_{user_email.replace('@', '_').replace('.', '_')}" # Sanitize session name

    try:
        # --- Fetch Role ARN from DB (remains synchronous) ---
        role_arn = get_user_aws_credentials(db, user_email)
        logger.info(f"Retrieved Role ARN '{role_arn}' for user {user_email} from database.")
        # --- End Fetch Role ARN ---

        # Check if application credentials are configured in settings
        if not all([settings.APP_AWS_ACCESS_KEY_ID, settings.APP_AWS_SECRET_ACCESS_KEY, settings.AWS_REGION]):
             logger.error("Application AWS credentials (ID, Key, Region) are not configured in settings.")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server configuration error: Missing AWS credentials.")

        # Create the STS client (synchronous operation, relatively quick)
        sts_client = boto3.client(
            'sts',
            aws_access_key_id=settings.APP_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.APP_AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
            # endpoint_url=settings.AWS_STS_ENDPOINT_URL # Optional: if using custom endpoint
        )

        # --- Define the blocking AssumeRole call ---
        assume_role_call = lambda: sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=role_session_name
        )

        logger.info(f"Attempting to assume role: {role_arn} for user: {user_email} (with timeout)")
        
        # --- Run the call in threadpool with timeout ---
        timeout_seconds = getattr(settings, 'AWS_ASSUME_ROLE_TIMEOUT_SECONDS', 30) # Default 30s
        assumed_role_object = await asyncio.wait_for(
            run_in_threadpool(assume_role_call),
            timeout=timeout_seconds
        )
        # --- End wrapped call ---

        # Create a new session using the temporary credentials (synchronous)
        credentials = assumed_role_object['Credentials']
        assumed_session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
            region_name=settings.AWS_REGION # Use the same region
        )
        logger.info(f"Successfully assumed role {role_arn} for user {user_email}")
        return assumed_session

    except TimeoutError:
        timeout_seconds = getattr(settings, 'AWS_ASSUME_ROLE_TIMEOUT_SECONDS', 30)
        logger.error(f"Timeout ({timeout_seconds}s) occurred while assuming role {role_arn} for user {user_email}.")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"AWS authentication timed out while assuming role.")
    except (NoCredentialsError, PartialCredentialsError):
        logger.exception("Application AWS credentials not found or incomplete.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server configuration error: Missing AWS credentials.")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code == 'AccessDenied':
            logger.error(f"Access denied when trying to assume role {role_arn} for user {user_email}. Check IAM permissions.", exc_info=False)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission error: Could not assume AWS role. Ensure the application has 'sts:AssumeRole' permission for '{role_arn}' and the role's trust policy allows the application.")
        else:
            logger.error(f"AWS ClientError assuming role {role_arn} for user {user_email}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AWS error assuming role: {error_code}")
    except Exception as e:
        logger.error(f"Unexpected error assuming role {role_arn} for user {user_email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during AWS authentication.")


def list_buckets(session: boto3.Session) -> List[S3Bucket]:
    """Lists accessible S3 buckets using the provided session."""
    try:
        s3_client = session.client('s3')
        response = s3_client.list_buckets()
        buckets = [S3Bucket(name=b['Name'], creation_date=b.get('CreationDate')) for b in response.get('Buckets', [])]
        logger.info(f"Listed {len(buckets)} buckets using assumed role session.")
        return buckets
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        logger.error(f"Error listing S3 buckets with assumed role: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AWS error listing buckets: {error_code}")
    except Exception as e:
        logger.error(f"Unexpected error listing S3 buckets with assumed role: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while listing buckets.")


def list_objects(session: boto3.Session, bucket_name: str, prefix: str = "") -> List[S3Object]:
    """
    Lists objects (files and common prefixes/folders) within a bucket/prefix.
    Handles pagination to retrieve all objects.
    """
    s3_client = session.client('s3')
    objects = []
    paginator = s3_client.get_paginator('list_objects_v2')

    try:
        logger.info(f"Listing objects in bucket '{bucket_name}' with prefix '{prefix}' using assumed role session.")
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix, Delimiter='/')

        for page in page_iterator:
            # Add folders (CommonPrefixes)
            for common_prefix in page.get('CommonPrefixes', []):
                folder_key = common_prefix.get('Prefix')
                if folder_key:
                     objects.append(S3Object(key=folder_key, is_folder=True))

            # Add files (Contents)
            for obj in page.get('Contents', []):
                 obj_key = obj.get('Key')
                 # Skip the prefix itself if it's listed as an object (placeholder for folder)
                 if obj_key and (obj_key != prefix or not prefix):
                     objects.append(S3Object(
                         key=obj_key,
                         is_folder=False,
                         size=obj.get('Size'),
                         last_modified=obj.get('LastModified')
                     ))

        logger.info(f"Found {len(objects)} objects/folders in '{bucket_name}/{prefix}' using assumed role.")
        objects.sort(key=lambda x: (not x.is_folder, x.key))
        return objects

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code == 'NoSuchBucket':
             logger.warning(f"Attempted to list objects in non-existent bucket: {bucket_name} (assumed role session)")
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bucket '{bucket_name}' not found or access denied.")
        elif error_code == 'AccessDenied':
             logger.warning(f"Access denied listing objects in bucket '{bucket_name}' prefix '{prefix}' (assumed role session)")
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied to list objects in '{bucket_name}/{prefix}'. Check role permissions (s3:ListBucket).")
        else:
            logger.error(f"Error listing objects in bucket '{bucket_name}' prefix '{prefix}' (assumed role session): {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AWS error listing objects: {error_code}")
    except Exception as e:
        logger.error(f"Unexpected error listing objects in bucket '{bucket_name}' prefix '{prefix}' (assumed role session): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while listing objects.")


def download_s3_object(session: boto3.Session, bucket_name: str, key: str) -> bytes:
    """Downloads an S3 object's content as bytes using the provided session."""
    s3_client = session.client('s3')
    try:
        logger.info(f"Attempting to download s3://{bucket_name}/{key} using assumed role session.")
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response['Body'].read()
        logger.info(f"Successfully downloaded s3://{bucket_name}/{key} ({len(content)} bytes) using assumed role session.")
        return content
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code == 'NoSuchKey':
             logger.warning(f"Attempted to download non-existent key: s3://{bucket_name}/{key} (assumed role session)")
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Object '{key}' not found in bucket '{bucket_name}'.")
        elif error_code == 'NoSuchBucket':
             logger.warning(f"Attempted to download from non-existent bucket: {bucket_name} (assumed role session)")
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bucket '{bucket_name}' not found or access denied.")
        elif error_code == 'AccessDenied':
             logger.warning(f"Access denied downloading s3://{bucket_name}/{key} (assumed role session)")
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied to download object '{key}' from bucket '{bucket_name}'. Check role permissions (s3:GetObject).")
        else:
            logger.error(f"Error downloading object s3://{bucket_name}/{key} (assumed role session): {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AWS error downloading object: {error_code}")
    except Exception as e:
        logger.error(f"Unexpected error downloading object s3://{bucket_name}/{key} (assumed role session): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while downloading the object.") 