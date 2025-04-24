import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List, Optional
from sqlalchemy import or_

from app.schemas.s3 import S3SyncItemCreate # Import the correct Pydantic schema
from app.db.models.s3_sync_item import S3SyncItem # Import the SQLAlchemy model

logger = logging.getLogger(__name__)

def add_item(db: Session, *, item_in: S3SyncItemCreate, user_id: str) -> S3SyncItem | None:
    """
    Adds a new S3 item to the user's sync list in the database.

    Args:
        db: The database session.
        item_in: The Pydantic model containing the item details.
        user_id: The ID (email) of the user adding the item.

    Returns:
        The created S3SyncItem object or None if it already exists (IntegrityError).
    """
    db_item = S3SyncItem(
        **item_in.model_dump(),
        user_id=user_id,
        status='pending'
    )
    try:
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        logger.info(f"Added S3 item '{item_in.item_name}' (Bucket: {item_in.s3_bucket}, Key: {item_in.s3_key}) to sync list for user {user_id} with status {db_item.status}.")
        return db_item
    except IntegrityError: # Handles unique constraint violation (uq_user_s3_item)
        db.rollback()
        logger.warning(f"S3 item (Bucket: {item_in.s3_bucket}, Key: {item_in.s3_key}) already exists in sync list for user {user_id}. Skipping.")
        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error adding S3 item {item_in.s3_key} for user {user_id}: {e}", exc_info=True)
        return None # Return None on other DB errors
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error adding S3 item {item_in.s3_key} for user {user_id}: {e}", exc_info=True)
        return None # Return None on unexpected errors

def get_items_by_user(db: Session, *, user_id: str) -> List[S3SyncItem]:
    """Gets all S3 sync items for a specific user."""
    try:
        return db.query(S3SyncItem).filter(S3SyncItem.user_id == user_id).order_by(S3SyncItem.id).all()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting S3 items for user {user_id}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting S3 items for user {user_id}: {e}", exc_info=True)
        return []

def get_pending_items_by_user(db: Session, *, user_id: str) -> List[S3SyncItem]:
    """Gets all S3 sync items with status 'pending' for a specific user."""
    try:
        return db.query(S3SyncItem).filter(S3SyncItem.user_id == user_id, S3SyncItem.status == 'pending').order_by(S3SyncItem.id).all()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting pending S3 items for user {user_id}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting pending S3 items for user {user_id}: {e}", exc_info=True)
        return []

def get_completed_or_failed_items_by_user(db: Session, *, user_id: str, limit: int = 100) -> List[S3SyncItem]:
    """Gets the most recent completed or failed S3 sync items for a specific user."""
    try:
        return db.query(S3SyncItem)\
                 .filter(S3SyncItem.user_id == user_id, S3SyncItem.status.in_(['completed', 'failed']))\
                 .order_by(S3SyncItem.id.desc())\
                 .limit(limit)\
                 .all()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting history S3 items for user {user_id}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting history S3 items for user {user_id}: {e}", exc_info=True)
        return []

def get_item_by_user_and_key(db: Session, *, user_id: str, s3_bucket: str, s3_key: str) -> S3SyncItem | None:
    """Gets a specific S3 sync item by user, bucket, and key."""
    try:
        return db.query(S3SyncItem).filter(
            S3SyncItem.user_id == user_id,
            S3SyncItem.s3_bucket == s3_bucket,
            S3SyncItem.s3_key == s3_key
        ).first()
    except SQLAlchemyError as e:
        logger.error(f"Database error getting S3 item {s3_bucket}/{s3_key} for user {user_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting S3 item {s3_bucket}/{s3_key} for user {user_id}: {e}", exc_info=True)
        return None

def remove_item(db: Session, *, db_item: S3SyncItem) -> S3SyncItem | None:
    """
    Marks an S3 sync item for deletion in the session.
    COMMIT MUST BE CALLED SEPARATELY by the calling function.
    """
    item_id = db_item.id # Capture details before potential error
    user_id = db_item.user_id
    key = db_item.s3_key
    try:
        db.delete(db_item)
        # db.commit() # COMMIT REMOVED
        logger.info(f"Marked S3 item ID {item_id} (Key: {key}) for deletion for user {user_id}.")
        return db_item # Return the object marked for deletion
    except SQLAlchemyError as e:
        # db.rollback() # ROLLBACK REMOVED
        logger.error(f"Database error marking S3 item ID {item_id} for deletion for user {user_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        # db.rollback() # ROLLBACK REMOVED
        logger.error(f"Unexpected error marking S3 item ID {item_id} for deletion for user {user_id}: {e}", exc_info=True)
        return None

def update_item_status(db: Session, *, db_item: S3SyncItem, status: str) -> S3SyncItem | None:
    """
    Updates the status of an S3 sync item IN THE SESSION.
    COMMIT MUST BE CALLED SEPARATELY by the calling function.
    """
    item_id = db_item.id # Capture details before potential update error
    user_id = db_item.user_id
    key = db_item.s3_key
    old_status = db_item.status
    try:
        db_item.status = status
        db.add(db_item) # Add to session to track changes
        # db.commit() # COMMIT REMOVED
        # db.refresh(db_item) # Cannot refresh before commit
        logger.info(f"Updated status of S3 item ID {item_id} (Key: {key}) for user {user_id} from '{old_status}' to '{status}' in session.")
        return db_item
    except SQLAlchemyError as e:
        # db.rollback() # ROLLBACK REMOVED
        logger.error(f"Database error preparing S3 item ID {item_id} status update for user {user_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        # db.rollback() # ROLLBACK REMOVED
        logger.error(f"Unexpected error preparing S3 item ID {item_id} status update for user {user_id}: {e}", exc_info=True)
        return None

def get_and_mark_pending_items_for_job(
    db: Session,
    *,
    user_email: str,
    bucket: str,
    key_or_prefix: str
) -> List[S3SyncItem]:
    """
    Finds pending S3SyncItems matching the job criteria (user, bucket, key/prefix)
    and updates their status to 'processing' within the session.
    COMMIT MUST BE CALLED SEPARATELY by the calling function.

    Args:
        db: Database session.
        user_email: User's email.
        bucket: S3 bucket name.
        key_or_prefix: Specific S3 key or prefix (ending with '/').

    Returns:
        A list of S3SyncItem objects whose status was successfully updated to 'processing' in the session.
    """
    marked_items = []
    try:
        # Build the base query
        query = db.query(S3SyncItem).filter(
            S3SyncItem.user_id == user_email,
            S3SyncItem.s3_bucket == bucket,
            S3SyncItem.status == 'pending'
        )

        # Add filter for key or prefix
        if key_or_prefix.endswith('/'):
            # Prefix match: key starts with the prefix
            query = query.filter(S3SyncItem.s3_key.startswith(key_or_prefix))
        else:
            # Exact key match
            query = query.filter(S3SyncItem.s3_key == key_or_prefix)

        # Use with_for_update() for row-level locking
        items_to_process = query.with_for_update().all()

        if not items_to_process:
            logger.info(f"No pending S3SyncItems found for user {user_email}, bucket {bucket}, key/prefix '{key_or_prefix}'")
            return []

        # Update status within the transaction (in session)
        for item in items_to_process:
            item.status = 'processing'
            db.add(item)
            marked_items.append(item)

        # db.commit() # COMMIT REMOVED - Handled by caller (Celery task)

        # No need to refresh items here as the commit hasn't happened yet.

        logger.info(f"Marked {len(marked_items)} S3SyncItems as 'processing' in session for user {user_email}, bucket {bucket}, key/prefix '{key_or_prefix}'")
        return marked_items

    except SQLAlchemyError as e:
        # db.rollback() # ROLLBACK REMOVED - Handled by caller
        logger.error(f"Database error finding/marking pending S3 items for user {user_email}, bucket {bucket}, key/prefix '{key_or_prefix}': {e}", exc_info=True)
        return [] # Return empty list on error
    except Exception as e:
        # db.rollback() # ROLLBACK REMOVED - Handled by caller
        logger.error(f"Unexpected error finding/marking pending S3 items for user {user_email}, bucket {bucket}, key/prefix '{key_or_prefix}': {e}", exc_info=True)
        return [] # Return empty list on error 