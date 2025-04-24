import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Any, Dict, Optional, List

from app.db.models.ingestion_job import IngestionJob # Assuming model path
from app.schemas.ingestion_job import IngestionJobCreate, IngestionJobUpdate # Schemas TBD

logger = logging.getLogger(__name__)

# Basic CRUD operations

def create_ingestion_job(db: Session, *, job_in: IngestionJobCreate, user_id: str) -> Optional[IngestionJob]:
    """Create a new ingestion job record."""
    try:
        db_obj = IngestionJob(
            user_id=user_id,
            source_type=job_in.source_type,
            job_details=job_in.job_details, # Directly assign dict from schema
            status='pending' # Initial status
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        logger.info(f"Created IngestionJob ID {db_obj.id} for user {user_id}, source {job_in.source_type}")
        return db_obj
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating IngestionJob for user {user_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating IngestionJob for user {user_id}: {e}", exc_info=True)
        return None

def get_ingestion_job(db: Session, job_id: int) -> Optional[IngestionJob]:
    """Get an ingestion job by its ID."""
    try:
        result = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        # if result:
        #     logger.debug(f"Found IngestionJob ID {job_id}")
        # else:
        #     logger.warning(f"IngestionJob ID {job_id} not found")
        return result
    except SQLAlchemyError as e:
        logger.error(f"Database error getting IngestionJob ID {job_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting IngestionJob ID {job_id}: {e}", exc_info=True)
        return None

def update_job_status(
    db: Session,
    *,
    job_id: int,
    status: str,
    error_message: Optional[str] = None,
    celery_task_id: Optional[str] = None
) -> Optional[IngestionJob]:
    """
    Updates the status, error message, and optionally Celery task ID of an ingestion job by ID IN THE SESSION.
    COMMIT MUST BE CALLED SEPARATELY by the calling function.
    """
    try:
        db_obj = get_ingestion_job(db=db, job_id=job_id)
        if not db_obj:
            logger.error(f"Cannot update status for non-existent IngestionJob ID {job_id}")
            return None

        db_obj.status = status
        if celery_task_id is not None:
             db_obj.celery_task_id = celery_task_id

        if status == 'failed':
            db_obj.error_message = error_message if error_message is not None else "Unknown error"
        elif status in ['completed', 'partial_complete']:
             db_obj.error_message = error_message
        elif status == 'processing':
            db_obj.error_message = None
        else:
            if error_message == "":
                 db_obj.error_message = None
            elif error_message is not None:
                db_obj.error_message = error_message

        db.add(db_obj) # Add the modified object back to the session
        # db.commit() # COMMIT REMOVED
        # db.refresh(db_obj) # Cannot refresh before commit
        logger.info(f"Updated IngestionJob ID {job_id} status to '{status}' in session.")
        return db_obj
    except SQLAlchemyError as e:
        # db.rollback() # ROLLBACK REMOVED
        logger.error(f"Database error preparing IngestionJob ID {job_id} update: {e}", exc_info=True)
        return None
    except Exception as e:
        # db.rollback() # ROLLBACK REMOVED
        logger.error(f"Unexpected error preparing IngestionJob ID {job_id} update: {e}", exc_info=True)
        return None


# Example of potential future function
def get_user_ingestion_jobs(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[IngestionJob]:
    """Retrieve ingestion jobs for a specific user."""
    try:
        return db.query(IngestionJob)\
                 .filter(IngestionJob.user_id == user_id)\
                 .order_by(IngestionJob.created_at.desc())\
                 .offset(skip)\
                 .limit(limit)\
                 .all()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting jobs for user {user_id}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting jobs for user {user_id}: {e}", exc_info=True)
        return [] 