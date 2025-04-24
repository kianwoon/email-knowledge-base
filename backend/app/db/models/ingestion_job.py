# backend/app/db/models/ingestion_job.py
import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID # Import UUID if needed based on UserDB PK
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
# Import ProcessedFile for relationship typing if needed, using TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .processed_file import ProcessedFile

class IngestionJob(Base):
    __tablename__ = 'ingestion_jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Link to the user who initiated the job
    # Assuming UserDB PK is email (String) based on previous check
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True) 

    # Type of the data source
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) 
    # e.g., 's3', 'azure_blob', 'email', 'sharepoint'

    # Overall status of the ingestion request
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending', index=True)
    # e.g., 'pending', 'processing', 'completed', 'partial_complete', 'failed'

    # JSONB column to store source-specific parameters
    job_details: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Examples:
    # S3: {"bucket": "my-bucket", "prefix": "data/"} 
    # Azure: {"connection_id": "uuid-...", "container": "container-name", "path": "folder/or/file.txt"}
    # Email: {"filter_criteria": {"sender": "x@y.com", "folder_id": "id...", ...}}
    # SharePoint: {"site_id": "site-id", "drive_id": "drive-id", "item_id": "item-id", "item_type": "folder"}

    # Link to the Celery task processing this job (optional but useful)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Store error message if the job failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Define the relationship to ProcessedFile
    processed_files: Mapped[List["ProcessedFile"]] = relationship(
        back_populates="ingestion_job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_ingestion_jobs_user_status', 'user_id', 'status'), # Index for user job status lookup
    )

    def __repr__(self) -> str:
        return f"<IngestionJob(id={self.id}, user_id='{self.user_id}', type='{self.source_type}', status='{self.status}')>" 