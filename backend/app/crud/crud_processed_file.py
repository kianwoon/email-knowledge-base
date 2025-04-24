# backend/app/crud/crud_processed_file.py
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional # Import Optional

from app.db.models.processed_file import ProcessedFile

logger = logging.getLogger(__name__)

def create_processed_file_entry(db: Session, file_data: ProcessedFile) -> ProcessedFile | None:
    """
    Adds a new ProcessedFile record to the database, commits the transaction,
    and refreshes the instance to load the database-generated ID.

    Args:
        db: The database session.
        file_data: A ProcessedFile model instance containing the data to be saved.

    Returns:
        The committed and refreshed ProcessedFile object, or None if an error occurred.
    """
    try:
        db.add(file_data)
        db.commit() # Commit the transaction
        db.refresh(file_data) # Refresh to get the ID and other DB defaults
        logger.info(f"Created and committed ProcessedFile record ID {file_data.id} for R2 key {file_data.r2_object_key}.")
        return file_data
    except SQLAlchemyError as e:
        db.rollback() # Rollback on error
        logger.error(f"Database error creating ProcessedFile record for R2 key {getattr(file_data, 'r2_object_key', 'N/A')}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback() # Rollback on error
        logger.error(f"Unexpected error creating ProcessedFile record for R2 key {getattr(file_data, 'r2_object_key', 'N/A')}: {e}", exc_info=True)
        return None

def get_processed_file_by_r2_key(db: Session, r2_object_key: str) -> Optional[ProcessedFile]:
    """Gets a ProcessedFile entry by its unique R2 object key."""
    try:
        return db.query(ProcessedFile).filter(ProcessedFile.r2_object_key == r2_object_key).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting ProcessedFile by R2 key {r2_object_key}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting ProcessedFile by R2 key {r2_object_key}: {e}", exc_info=True)
        return None

def count_processed_files_by_source(db: Session, owner_email: str, source_type: str) -> int:
    """Counts ProcessedFile entries for a specific owner and source type."""
    try:
        count = db.query(ProcessedFile)\
                  .filter(ProcessedFile.owner_email == owner_email)\
                  .filter(ProcessedFile.source_type == source_type)\
                  .count()
        return count
    except SQLAlchemyError as e:
        logger.error(f"Database error counting ProcessedFiles for owner {owner_email}, source {source_type}: {e}", exc_info=True)
        return 0
    except Exception as e:
        logger.error(f"Unexpected error counting ProcessedFiles for owner {owner_email}, source {source_type}: {e}", exc_info=True)
        return 0

# TODO: Add other potential CRUD operations for ProcessedFile if needed
# - Get by ID
# - Update status
# - List by job ID
# - List by owner and status 