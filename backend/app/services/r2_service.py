# backend/app/services/r2_service.py
import logging
from typing import Any, IO
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings

logger = logging.getLogger(__name__)

# Define a custom exception for R2 specific errors
class R2UploadError(Exception):
    """Custom exception for R2 upload failures."""
    pass

def get_r2_client() -> Any:
    """
    Initializes and returns a boto3 client configured for Cloudflare R2.
    Uses credentials and endpoint from the application settings.
    """
    try:
        # Ensure required settings are present
        if not all([settings.R2_ENDPOINT_URL, settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY, settings.R2_AWS_REGION]):
            raise ValueError("Missing required R2 configuration settings (Endpoint, Access Key, Secret Key, Region).")

        session = boto3.session.Session()
        client = session.client(
            service_name='s3',
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name=settings.R2_AWS_REGION, # R2 requires a region, 'auto' often works
        )
        logger.info("Successfully initialized R2 client.")
        return client
    except NoCredentialsError:
        logger.error("R2 credentials not found. Ensure R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY are set.", exc_info=True)
        raise ValueError("R2 credentials not found.")
    except Exception as e:
        logger.error(f"Failed to initialize R2 client: {e}", exc_info=True)
        raise ValueError(f"Failed to initialize R2 client: {e}")


async def upload_fileobj_to_r2(
    r2_client: Any,
    file_obj: IO[bytes],
    bucket: str,
    object_key: str,
    content_type: str | None = None
) -> None:
    """
    Uploads a file-like object to the specified R2 bucket using the provided client.

    Args:
        r2_client: The initialized boto3 R2 client.
        file_obj: The file-like object to upload (must be in binary mode).
        bucket: The target R2 bucket name.
        object_key: The desired key (path) for the object in R2.
        content_type: Optional content type for the uploaded object.

    Raises:
        R2UploadError: If the upload fails due to ClientError or other issues.
        ValueError: If required arguments are missing.
    """
    if not all([r2_client, file_obj, bucket, object_key]):
        raise ValueError("Missing required arguments for R2 upload (client, file_obj, bucket, object_key).")

    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type
    # Can add other args like ACL if needed, but R2 defaults are usually fine

    try:
        logger.debug(f"Attempting to upload to R2: s3://{bucket}/{object_key}")
        r2_client.upload_fileobj(
            Fileobj=file_obj,
            Bucket=bucket,
            Key=object_key,
            ExtraArgs=extra_args
        )
        logger.info(f"Successfully uploaded file to R2: s3://{bucket}/{object_key}")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        error_message = e.response.get('Error', {}).get('Message')
        logger.error(f"R2 ClientError uploading s3://{bucket}/{object_key} (Code: {error_code}): {error_message}", exc_info=True)
        raise R2UploadError(f"Failed to upload to R2 (Code: {error_code}): {error_message}") from e
    except Exception as e:
        logger.error(f"Unexpected error uploading to R2 s3://{bucket}/{object_key}: {e}", exc_info=True)
        raise R2UploadError(f"Unexpected error during R2 upload: {e}") from e

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