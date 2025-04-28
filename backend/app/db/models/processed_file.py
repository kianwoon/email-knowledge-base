# backend/app/db/models/processed_file.py
import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Index, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
# Import IngestionJob for relationship typing if needed, using TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .ingestion_job import IngestionJob
    from app.models.user import UserDB # If relating to UserDB

class ProcessedFile(Base):
    __tablename__ = 'processed_files'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Foreign Key to the parent job
    ingestion_job_id: Mapped[int] = mapped_column(ForeignKey('ingestion_jobs.id'), nullable=False, index=True)
    # Define relationship if needed for querying job details from file object
    ingestion_job: Mapped["IngestionJob"] = relationship(back_populates="processed_files") # Requires adding processed_files relationship to IngestionJob

    # Owner of the data (using email, consistent with users PK and Milvus owner)
    owner_email: Mapped[str] = mapped_column(String, ForeignKey('users.email'), nullable=False, index=True) # Added FK
    # Define relationship if needed for querying user details from file object
    user: Mapped["UserDB"] = relationship() 

    # Source information
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) 
    # e.g., 's3', 'azure_blob', 'email_attachment', 'sharepoint'
    
    # Unique identifier within the original source 
    # Examples: 
    # S3: s3://bucket/key
    # Azure: azure://container/path
    # Email: email_id/attachment_id 
    # SharePoint: drive_id/item_id
    source_identifier: Mapped[str] = mapped_column(Text, nullable=False, index=True) 

    # File details
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    r2_object_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True) # Unique key in R2
    content_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True) # Store size in bytes

    # Processing status (tracks workflow after R2 upload)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending_analysis', index=True)
    # e.g., 'pending_analysis', 'analysis_in_progress', 'analysis_complete', 'analysis_failed', 
    #       'embedding_pending', 'embedding_in_progress', 'embedding_complete', 'embedding_failed'

    # Additional metadata (e.g., source-specific IDs, analysis results)
    additional_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Store error message if status becomes '..._failed'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index('ix_processed_files_owner_status', 'owner_email', 'status'), # Index for user status lookup
        Index('ix_processed_files_status', 'status'), # Index for finding pending work
        # Add extend_existing=True as a safety measure
        {'extend_existing': True}
    )

    def __repr__(self) -> str:
        return f"<ProcessedFile(id={self.id}, owner='{self.owner_email}', r2_key='{self.r2_object_key}', status='{self.status}')>" 