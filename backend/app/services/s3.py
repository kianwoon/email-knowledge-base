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
import io # Add io import

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


# --- Make list_buckets async and run blocking call in threadpool ---
async def list_buckets(session: boto3.Session) -> List[S3Bucket]:
    """Lists accessible S3 buckets using the provided session (non-blocking)."""
    try:
        # Creating client is fast, no need for threadpool
        s3_client = session.client('s3')

        # --- Define the blocking call --- 
        list_buckets_call = lambda: s3_client.list_buckets()

        # --- Run in threadpool (no explicit timeout needed here unless desired) ---
        logger.info(f"Listing buckets in threadpool using assumed role session.")
        response = await run_in_threadpool(list_buckets_call)
        # --- End wrapped call ---

        buckets = [S3Bucket(name=b['Name'], creation_date=b.get('CreationDate')) for b in response.get('Buckets', [])]
        logger.info(f"Listed {len(buckets)} buckets using assumed role session.")
        return buckets
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        logger.error(f"Error listing S3 buckets with assumed role: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AWS error listing buckets: {error_code}")
    except AttributeError as ae:
        # Catch the specific error if the session object is still wrong
        logger.error(f"AttributeError listing S3 buckets: {ae}. The session object might be invalid (e.g., a coroutine).", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error processing AWS session.")
    except Exception as e:
        logger.error(f"Unexpected error listing S3 buckets with assumed role: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while listing buckets.")


# --- Make list_objects async and run blocking calls in threadpool ---
async def list_objects(session: boto3.Session, bucket_name: str, prefix: str = "") -> List[S3Object]:
    """
    Lists objects (files and common prefixes/folders) within a bucket/prefix (non-blocking).
    Handles pagination to retrieve all objects.
    """
    # Client creation is fast
    s3_client = session.client('s3')
    objects = []
    # Paginator creation is fast
    paginator = s3_client.get_paginator('list_objects_v2')

    try:
        logger.info(f"Listing objects in bucket '{bucket_name}' with prefix '{prefix}' using assumed role session (async). ")

        # --- Define the blocking paginate call --- 
        # Note: Paginators themselves aren't directly awaitable with run_in_threadpool.
        # We need to iterate through pages in the threadpool or fetch all pages at once.
        # Fetching all pages might be memory-intensive for large buckets.
        # Let's fetch page by page within the threadpool.

        # It's complex to run pagination directly in threadpool page-by-page easily.
        # Alternative: Use aioboto3 if added as a dependency for native async operations.
        # Simpler alternative for now: Run the *entire* pagination and collection logic in the threadpool.
        
        def list_all_objects_sync():
            sync_objects = []
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix, Delimiter='/')
            for page in page_iterator:
                for common_prefix in page.get('CommonPrefixes', []):
                    folder_key = common_prefix.get('Prefix')
                    if folder_key: sync_objects.append(S3Object(key=folder_key, is_folder=True))
                for obj in page.get('Contents', []):
                    obj_key = obj.get('Key')
                    if obj_key and (obj_key != prefix or not prefix):
                        sync_objects.append(S3Object(
                            key=obj_key, is_folder=False, size=obj.get('Size'), last_modified=obj.get('LastModified')
                        ))
            return sync_objects

        # --- Run the full listing logic in threadpool ---
        objects = await run_in_threadpool(list_all_objects_sync)
        # --- End wrapped call ---

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

# --- ADDED: Function specifically for R2 Upload --- 

def upload_bytes_to_r2(bucket_name: str, object_key: str, data_bytes: bytes) -> bool:
    """
    Uploads bytes data directly to a Cloudflare R2 bucket using configured credentials.
    Args:
        bucket_name (str): The target R2 bucket name.
        object_key (str): The desired R2 object key (path within the bucket).
        data_bytes (bytes): The raw bytes data to upload.
        
    Returns:
        bool: True if upload was successful, False otherwise.
    """
    try:
        # Check if R2 settings are configured
        if not all([settings.R2_ENDPOINT_URL, settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY, settings.R2_AWS_REGION]):
            logger.error("Cloudflare R2 credentials or endpoint URL are not fully configured in settings.")
            raise ValueError("R2 configuration is incomplete.")
            
        logger.info(f"Using configured R2 credentials to upload to {settings.R2_ENDPOINT_URL}/{bucket_name}/{object_key}")
        
        # Initialize S3 client pointing to R2 endpoint
        s3_client = boto3.client(
            service_name='s3',
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name=settings.R2_AWS_REGION # e.g., 'auto'
        )
        
        # Upload the bytes using put_object with BytesIO
        s3_client.put_object(
            Bucket=bucket_name, 
            Key=object_key, 
            Body=io.BytesIO(data_bytes)
            # Optionally add ContentType if needed/available: ContentType='application/octet-stream' 
        )
        logger.info(f"Successfully uploaded bytes to R2 object: {bucket_name}/{object_key}")
        return True
        
    except ClientError as e:
        logger.error(f"AWS/R2 ClientError uploading bytes to R2 object {bucket_name}/{object_key}: {e}", exc_info=True)
        return False
    except ValueError as e:
        logger.error(f"ValueError during R2 bytes upload setup for object {bucket_name}/{object_key}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error uploading bytes to R2 object {bucket_name}/{object_key}: {e}", exc_info=True)
        return False 