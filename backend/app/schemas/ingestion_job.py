# backend/app/schemas/ingestion_job.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import datetime

# Pydantic model for creating an IngestionJob
# Used typically in API endpoints when initiating a job
class IngestionJobCreate(BaseModel):
    source_type: str = Field(..., max_length=50, description="Type of the data source (e.g., 's3', 'azure_blob')")
    job_details: Dict[str, Any] = Field(..., description="Source-specific parameters (e.g., bucket/key for S3)")

    class Config:
        json_schema_extra = {
            "example": {
                "source_type": "s3",
                "job_details": {"bucket": "my-data-bucket", "prefix": "incoming/"}
            }
        }

# Pydantic model for updating an IngestionJob (Optional, define if needed)
class IngestionJobUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=50, description="Updated status of the job")
    error_message: Optional[str] = Field(None, description="Error message if the job failed")
    # Add other fields that might be updatable if necessary

# Pydantic model for representing an IngestionJob read from the DB (e.g., in API responses)
class IngestionJobRead(BaseModel):
    id: int
    user_id: str
    source_type: str
    status: str
    job_details: Dict[str, Any]
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True # Enable ORM mode 