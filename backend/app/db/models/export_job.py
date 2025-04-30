# backend/app/db/models/export_job.py
import datetime
import enum # Use standard enum
from typing import Dict, Any, Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.token_models import TokenDB # For relationship typing if needed

class ExportJobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExportJob(Base):
    __tablename__ = 'export_jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Link to the user who initiated the job
    user_id: Mapped[str] = mapped_column(String, ForeignKey('users.email'), nullable=False, index=True) # Assuming users.email is PK

    # Link to the token whose rules govern this export
    token_id: Mapped[int] = mapped_column(Integer, ForeignKey('tokens.id'), nullable=False, index=True)

    # Overall status of the export request
    status: Mapped[ExportJobStatus] = mapped_column(
        SQLAlchemyEnum(ExportJobStatus, name="exportjobstatus", create_type=False), 
        nullable=False, 
        default=ExportJobStatus.PENDING, 
        index=True
    )

    # JSONB column to store source-specific parameters and filters
    export_params: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Example: {"source": "iceberg_emails", "format": "csv", "filters": {"keywords": ["report"], "date_range": [...]}}

    # Link to the Celery task processing this job
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Location of the resulting export file (e.g., R2 key or URL)
    result_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Store error message if the job failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships (optional, but can be useful)
    # owner: Mapped["User"] = relationship(back_populates="export_jobs") # Assuming User model has export_jobs relationship
    # token: Mapped["TokenDB"] = relationship() # One-way relationship sufficient for now

    def __repr__(self):
        return f"<ExportJob(id={self.id}, user_id='{self.user_id}', token_id={self.token_id}, status='{self.status}')>"

# Ensure the Enum type is created in the database if it doesn't exist
# This usually happens during migration, but good practice to include check/creation logic if needed elsewhere.
# from sqlalchemy import event
# from sqlalchemy.schema import CreateEnum
# event.listen(ExportJob.__table__, 'before_create', CreateEnum(ExportJobStatus, name='exportjobstatus')) 