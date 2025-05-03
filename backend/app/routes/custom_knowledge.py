import base64
import io
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user_or_token_owner
from app.models.user import UserDB
from app.config import settings
from app.services import r2_service
from app.db.models.processed_file import ProcessedFile
from app.crud import crud_processed_file

# Get logger
logger = logging.getLogger(__name__)

router = APIRouter()

class CustomKnowledgeUpload(BaseModel):
    filename: str
    content_type: str
    file_size: int
    content_base64: str

class ProcessedFileOut(BaseModel):
    id: int
    owner_email: str
    source_type: str
    source_identifier: str
    original_filename: str
    r2_object_key: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    status: str
    created_at: datetime = Field(..., alias="created_at")
    updated_at: datetime = Field(..., alias="updated_at")
    error_message: Optional[str] = None

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

def generate_r2_object_key(user_email: str, original_key: str) -> str:
    """Generates a unique R2 object key for custom uploads."""
    CUSTOM_UPLOAD_NAMESPACE_UUID = uuid.UUID('c1a2b3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d') # Example namespace
    sanitized_email = user_email.replace('@', '_').replace('.', '_')
    unique_suffix = str(uuid.uuid5(CUSTOM_UPLOAD_NAMESPACE_UUID, f"{user_email}:{original_key}:{datetime.now(timezone.utc).isoformat()}")) # Add timestamp for uniqueness
    filename = original_key # Keep original filename for clarity
    return f"custom_uploads/{sanitized_email}/{unique_suffix}/{filename}"

@router.post("/upload-base64")
async def upload_custom_knowledge_base64(
    payload: CustomKnowledgeUpload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user_or_token_owner)
):
    try:
        # --- R2 Upload Logic ---
        user_email = current_user.email
        original_filename = payload.filename
        logger.info(f"Received custom knowledge upload request from {user_email} for file {original_filename}")

        # 1. Decode Base64 content
        try:
            file_content_bytes = base64.b64decode(payload.content_base64)
            if len(file_content_bytes) != payload.file_size:
                logger.warning(f"Decoded size {len(file_content_bytes)} does not match reported size {payload.file_size} for {original_filename}")
                # Decide if this is critical - allowing it for now
            file_obj = io.BytesIO(file_content_bytes)
        except (base64.binascii.Error, TypeError) as decode_err:
            logger.error(f"Failed to decode base64 content for {original_filename}: {decode_err}")
            raise HTTPException(status_code=400, detail="Invalid base64 content.")

        # 2. Generate R2 Key
        r2_key = generate_r2_object_key(user_email, original_filename)
        logger.debug(f"Generated R2 key: {r2_key} for {original_filename}")

        # 3. Check if ProcessedFile with this R2 key already exists
        existing_file = crud_processed_file.get_processed_file_by_r2_key(db=db, r2_object_key=r2_key)
        if existing_file:
            logger.warning(f"ProcessedFile record for R2 key {r2_key} already exists (ID: {existing_file.id}). Skipping upload for {original_filename}.")
            # Return success but indicate duplication? Or raise specific error?
            # Raising conflict error for now
            raise HTTPException(status_code=409, detail=f"A file derived from '{original_filename}' resulting in the same storage key seems to already exist.")

        # 4. Get R2 Client
        try:
            r2_client = r2_service.get_r2_client()
        except Exception as r2_client_err:
            logger.error(f"Failed to get R2 client: {r2_client_err}", exc_info=True)
            raise HTTPException(status_code=503, detail="Could not connect to file storage service.")

        # 5. Upload to R2
        try:
            logger.info(f"Uploading {original_filename} to R2 bucket '{settings.R2_BUCKET_NAME}' with key '{r2_key}'")
            await r2_service.upload_fileobj_to_r2(
                r2_client=r2_client,
                file_obj=file_obj, # Pass the BytesIO object
                bucket=settings.R2_BUCKET_NAME,
                object_key=r2_key,
                content_type=payload.content_type # Pass content type from payload
            )
            logger.info(f"Successfully uploaded {original_filename} to R2 as {r2_key}")
        except Exception as upload_err: # Catch generic Exception, refine if r2_service throws specific errors
            logger.error(f"Failed to upload {original_filename} to R2: {upload_err}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {upload_err}")

        # 6. Create ProcessedFile DB Record
        try:
            logger.info(f"Creating ProcessedFile record for {r2_key}")
            processed_file_data = ProcessedFile(
                owner_email=user_email,
                source_type="custom_upload", # Indicate the source
                source_identifier=f"custom_upload:{original_filename}", # A unique identifier for this source
                original_filename=original_filename,
                r2_object_key=r2_key,
                content_type=payload.content_type,
                size_bytes=payload.file_size, # Use size from payload
                status="pending_analysis", # Set status as requested
                # ingestion_job_id=None, # No specific job ID for direct uploads
                additional_data=None, # No extra data needed for now
                error_message=None, # No error
                # uploaded_at and updated_at are handled by the model defaults
            )
            created_entry = crud_processed_file.create_processed_file_entry(db=db, file_data=processed_file_data)
            if not created_entry:
                # This case might indicate an issue within the CRUD function or session state
                logger.error(f"CRUD function failed to return created entry for {r2_key}, but no exception was raised.")
                raise HTTPException(status_code=500, detail="Failed to save file record after upload.")

            db.commit() # Commit the transaction to save the ProcessedFile record
            db.refresh(created_entry) # Refresh to get the ID and default values
            logger.info(f"Successfully created ProcessedFile record (ID: {created_entry.id}) for {r2_key}")

        except Exception as db_err:
            logger.error(f"Failed to create ProcessedFile record for {r2_key} after successful R2 upload: {db_err}", exc_info=True)
            # Attempt to clean up the R2 file? Or leave it and report error?
            # Leaving it for now, but this indicates inconsistency.
            db.rollback() # Rollback the failed DB transaction
            raise HTTPException(status_code=500, detail="Failed to save file metadata after upload.")

        return {"status": "success", "message": f"File '{original_filename}' uploaded successfully and pending analysis.", "r2_key": r2_key, "processed_file_id": created_entry.id}

    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error during custom knowledge upload for {payload.filename}: {e}", exc_info=True)
        # Rollback if a db session issue occurred before commit attempt
        try:
            db.rollback()
        except Exception as rb_err:
            logger.error(f"Error during rollback attempt on unexpected error: {rb_err}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@router.get("/history", response_model=List[ProcessedFileOut])
def get_custom_knowledge_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user_or_token_owner)
):
    """
    Return recently processed custom knowledge files (source_type='custom_upload')
    for the current user.
    """
    try:
        logger.info(f"Fetching custom knowledge upload history for user {current_user.email}")
        records = db.query(ProcessedFile).filter(
            ProcessedFile.owner_email == current_user.email,
            ProcessedFile.source_type == 'custom_upload' # Filter specifically for custom uploads
        ).order_by(
            ProcessedFile.created_at.desc() # Sort by creation time (most recent first)
        ).limit(100).all() # Limit the results to avoid excessive data transfer

        logger.info(f"Found {len(records)} custom knowledge history records for user {current_user.email}")
        # Pydantic's orm_mode will handle the conversion to ProcessedFileOut
        return records
    except Exception as e:
        logger.error(f"Error fetching custom knowledge history for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve upload history.")
