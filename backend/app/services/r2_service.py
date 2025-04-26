# backend/app/services/r2_service.py
import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Any, BinaryIO
import asyncio
from fastapi.concurrency import run_in_threadpool

from app.config import settings

logger = logging.getLogger(__name__)

class R2UploadError(Exception):
    """Custom exception for R2 upload failures."""
    pass

# TODO: Implement get_r2_client
# TODO: Implement upload_fileobj_to_r2
# TODO: Implement upload_bytes_to_r2

def get_r2_client() -> Any:
    """Initializes and returns a boto3 client configured for R2."""
    try:
        # Ensure all required settings are present
        if not all([
            settings.R2_ENDPOINT_URL,
            settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY,
            settings.R2_REGION # Although region might not be strictly used by R2 endpoint, S3 client expects it
        ]):
            raise ValueError("Missing required R2 configuration settings (ENDPOINT_URL, ACCESS_KEY_ID, SECRET_ACCESS_KEY, REGION).")

        s3_client = boto3.client(
            service_name='s3',
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name=settings.R2_REGION  # e.g., 'auto' or a specific region if needed
        )
        logger.info("Successfully created R2 client.")
        return s3_client
    except NoCredentialsError as e:
        logger.error(f"AWS NoCredentialsError while creating R2 client: {e}. Check environment variables or configuration.")
        raise R2UploadError(f"Credentials not found for R2: {e}") from e
    except ValueError as e:
        logger.error(f"Configuration error creating R2 client: {e}")
        raise R2UploadError(f"Configuration error for R2: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error creating R2 client: {e}", exc_info=True)
        raise R2UploadError(f"Failed to initialize R2 client: {e}") from e


async def upload_fileobj_to_r2(
    r2_client: Any,
    file_obj: BinaryIO,
    bucket: str,
    object_key: str,
    content_type: str | None = None
) -> None:
    """Uploads a file-like object to R2 using the provided client."""
    try:
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        logger.debug(f"Uploading file object to R2: s3://{bucket}/{object_key}, ContentType: {content_type}")
        # Boto3's upload_fileobj is synchronous, wrap in run_in_threadpool for async context
        await run_in_threadpool(
            r2_client.upload_fileobj,
            Fileobj=file_obj,
            Bucket=bucket,
            Key=object_key,
            ExtraArgs=extra_args
        )
        logger.info(f"Successfully uploaded file object to R2: s3://{bucket}/{object_key}")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        logger.error(f"R2 ClientError uploading file object to s3://{bucket}/{object_key} (Code: {error_code}): {e}", exc_info=True)
        raise R2UploadError(f"R2 upload failed (ClientError: {error_code}): {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error uploading file object to s3://{bucket}/{object_key}: {e}", exc_info=True)
        raise R2UploadError(f"R2 upload failed (Unexpected): {e}") from e

# Example self-test (optional)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Attempting to initialize R2 client (ensure .env is configured)...")
    try:
        client = get_r2_client()
        # You could add a test upload here if desired, requires a configured bucket and credentials
        # import io
        # test_bucket = settings.R2_BUCKET_NAME
        # test_key = "r2_service_test.txt"
        # test_data = io.BytesIO(b"This is a test file from r2_service.")
        # print(f"Attempting test upload to {test_bucket}/{test_key}...")
        # asyncio.run(upload_fileobj_to_r2(client, test_data, test_bucket, test_key, "text/plain"))
        # print("Test upload successful (check your R2 bucket).")
    except Exception as e:
        logger.error(f"R2 service self-test failed: {e}", exc_info=True) 

# TODO: Implement upload_bytes_to_r2
async def upload_bytes_to_r2(
    r2_client: Any,
    bucket_name: str,
    object_key: str,
    data_bytes: bytes,
    content_type: str | None = None
) -> bool:
    """Uploads bytes data directly to R2 using put_object."""
    try:
        put_kwargs = {
            'Bucket': bucket_name,
            'Key': object_key,
            'Body': data_bytes
        }
        if content_type:
            put_kwargs['ContentType'] = content_type
            
        logger.debug(f"Uploading bytes to R2: s3://{bucket_name}/{object_key}, Size: {len(data_bytes)}, ContentType: {content_type}")
        # put_object is synchronous, wrap in threadpool
        await run_in_threadpool(r2_client.put_object, **put_kwargs)
        logger.info(f"Successfully uploaded bytes to R2: s3://{bucket_name}/{object_key}")
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        logger.error(f"R2 ClientError uploading bytes to s3://{bucket_name}/{object_key} (Code: {error_code}): {e}", exc_info=True)
        # raise R2UploadError(f"R2 upload failed (ClientError: {error_code}): {e}") from e
        return False # Return False on failure for the knowledge service
    except Exception as e:
        logger.error(f"Unexpected error uploading bytes to s3://{bucket_name}/{object_key}: {e}", exc_info=True)
        # raise R2UploadError(f"R2 upload failed (Unexpected): {e}") from e
        return False # Return False on failure 