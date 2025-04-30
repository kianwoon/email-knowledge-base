# backend/app/crud/crud_export_job.py
import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, update 

from app.db.models.export_job import ExportJob, ExportJobStatus

logger = logging.getLogger(__name__)

def create_export_job(db: Session, *, user_id: str, token_id: int, export_params: Dict[str, Any]) -> ExportJob:
    """Creates a new export job record."""
    db_job = ExportJob(
        user_id=user_id,
        token_id=token_id,
        export_params=export_params,
        status=ExportJobStatus.PENDING
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    logger.info(f"Created ExportJob ID {db_job.id} for user {user_id} with token {token_id}.")
    return db_job

def get_export_job(db: Session, *, job_id: int) -> Optional[ExportJob]:
    """Gets an export job by its ID."""
    statement = select(ExportJob).where(ExportJob.id == job_id)
    result = db.execute(statement).scalar_one_or_none()
    return result

def update_job_status(
    db: Session, 
    *, 
    job_id: int, 
    status: ExportJobStatus, 
    celery_task_id: Optional[str] = None, 
    result_location: Optional[str] = None, 
    error_message: Optional[str] = None
) -> Optional[ExportJob]:
    """Updates the status and optionally other fields of an export job."""
    try:
        update_values = {"status": status}
        if celery_task_id is not None:
            update_values["celery_task_id"] = celery_task_id
        if result_location is not None:
            update_values["result_location"] = result_location
        if error_message is not None:
            update_values["error_message"] = error_message
        # Ensure updated_at is automatically handled by onupdate=func.now()

        statement = (
            update(ExportJob)
            .where(ExportJob.id == job_id)
            .values(**update_values)
            .returning(ExportJob) # Return the updated row
        )
        
        result = db.execute(statement).scalar_one_or_none()
        
        if result:
            db.commit()
            logger.info(f"Updated ExportJob ID {job_id} status to '{status}'. Task ID: {celery_task_id}, Result: {result_location}, Error: {error_message}")
            return result
        else:
            logger.warning(f"Attempted to update non-existent ExportJob ID {job_id}.")
            db.rollback()
            return None
    except Exception as e:
        logger.error(f"Failed to update ExportJob ID {job_id}: {e}", exc_info=True)
        db.rollback()
        return None 