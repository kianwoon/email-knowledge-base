import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

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
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding S3 item {item_in.s3_key} for user {user_id}: {e}", exc_info=True)
        raise # Re-raise other exceptions

def get_items_by_user(db: Session, *, user_id: str) -> List[S3SyncItem]:
    """Gets all S3 sync items for a specific user."""
    return db.query(S3SyncItem).filter(S3SyncItem.user_id == user_id).order_by(S3SyncItem.id).all()

def get_pending_items_by_user(db: Session, *, user_id: str) -> List[S3SyncItem]:
    """Gets all S3 sync items with status 'pending' for a specific user."""
    return db.query(S3SyncItem).filter(S3SyncItem.user_id == user_id, S3SyncItem.status == 'pending').order_by(S3SyncItem.id).all()

def get_item_by_user_and_key(db: Session, *, user_id: str, s3_bucket: str, s3_key: str) -> S3SyncItem | None:
    """Gets a specific S3 sync item by user, bucket, and key."""
    return db.query(S3SyncItem).filter(
        S3SyncItem.user_id == user_id,
        S3SyncItem.s3_bucket == s3_bucket,
        S3SyncItem.s3_key == s3_key
    ).first()

def remove_item(db: Session, *, db_item: S3SyncItem) -> S3SyncItem:
    """Removes an S3 sync item from the database."""
    db.delete(db_item)
    db.commit()
    logger.info(f"Removed S3 item (Bucket: {db_item.s3_bucket}, Key: {db_item.s3_key}) from sync list for user {db_item.user_id}.")
    return db_item

def update_item_status(db: Session, *, db_item: S3SyncItem, status: str) -> S3SyncItem:
    """Updates the status of an S3 sync item."""
    db_item.status = status
    db.add(db_item) # Add to session to track changes
    db.commit()
    db.refresh(db_item)
    logger.info(f"Updated status of S3 item (Bucket: {db_item.s3_bucket}, Key: {db_item.s3_key}) for user {db_item.user_id} to '{status}'.")
    return db_item 