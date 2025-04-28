# backend/app/crud/crud_processed_file.py
import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List # Import Optional and List

from app.db.models.processed_file import ProcessedFile

logger = logging.getLogger(__name__)

# TODO: Implement create_processed_file_entry
# TODO: Implement get_processed_file_by_source_id
# TODO: Implement get_processed_file_by_r2_key

def create_processed_file_entry(db: Session, file_data: ProcessedFile) -> ProcessedFile | None:
    """Creates a new ProcessedFile record in the database."""
    try:
        db.add(file_data)
        # We might commit here or let the caller handle commit as part of a larger transaction.
        # For now, let's assume the caller (task) handles the commit.
        # db.commit()
        # db.refresh(file_data) # Refresh might fail if commit is handled outside
        # Let's flush to get potential errors early without full commit
        db.flush() 
        db.refresh(file_data) # Refresh after flush should work within the transaction
        logger.info(f"ProcessedFile entry added to session for source: {file_data.source_identifier}, R2 key: {file_data.r2_object_key}")
        return file_data
    except SQLAlchemyError as e:
        logger.error(f"Database error creating ProcessedFile entry: {e}", exc_info=True)
        # db.rollback() # Rollback should be handled by the caller task in case of errors
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating ProcessedFile entry: {e}", exc_info=True)
        # db.rollback() # Rollback should be handled by the caller task
        return None

def get_processed_file_by_r2_key(db: Session, r2_object_key: str) -> ProcessedFile | None:
    """Retrieves a ProcessedFile record by its r2_object_key."""
    if not r2_object_key: # Prevent querying with empty string
        return None
    try:
        return db.query(ProcessedFile).filter(ProcessedFile.r2_object_key == r2_object_key).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving ProcessedFile by r2_object_key '{r2_object_key}': {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving ProcessedFile by r2_object_key '{r2_object_key}': {e}", exc_info=True)
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

# TODO: Implement get_processed_file_by_source_id
def get_processed_file_by_source_id(db: Session, source_identifier: str) -> Optional[ProcessedFile]:
    """Retrieves a ProcessedFile record by its source_identifier."""
    try:
        return db.query(ProcessedFile).filter(ProcessedFile.source_identifier == source_identifier).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving ProcessedFile by source_identifier '{source_identifier}': {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving ProcessedFile by source_identifier '{source_identifier}': {e}", exc_info=True)
        return None

# TODO: Add other potential CRUD operations for ProcessedFile if needed
# - Get by ID
# - Update status
# - List by job ID
# - List by owner and status 