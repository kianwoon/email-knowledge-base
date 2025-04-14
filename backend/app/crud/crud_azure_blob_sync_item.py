import uuid
import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.models.azure_blob_sync_item import AzureBlobSyncItem
from app.schemas.azure_blob import AzureBlobSyncItemCreate

logger = logging.getLogger(__name__)

def add_sync_item(
    db: Session, *, item_in: AzureBlobSyncItemCreate, user_id: uuid.UUID
) -> AzureBlobSyncItem | None:
    """Adds a new Azure Blob item to the sync list.

    Returns:
        The created object or None if it already exists (IntegrityError).
    """
    # Check if connection exists and belongs to user (optional, depends on security needs)
    # connection = db.get(AzureBlobConnection, item_in.connection_id)
    # if not connection or connection.user_id != user_id:
    #    logger.warning(f"Attempt to add sync item for invalid/unowned connection {item_in.connection_id} by user {user_id}")
    #    raise ValueError("Invalid connection ID")

    db_item = AzureBlobSyncItem(
        **item_in.model_dump(),
        user_id=user_id,
        status='pending'
    )
    try:
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        logger.info(f"Added Azure sync item '{item_in.item_path}' for connection {item_in.connection_id} for user {user_id}.")
        return db_item
    except IntegrityError:
        db.rollback()
        logger.warning(f"Azure sync item '{item_in.item_path}' for connection {item_in.connection_id} already exists for user {user_id}. Skipping.")
        return None # Indicate item already exists
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding Azure sync item '{item_in.item_path}' for user {user_id}: {e}", exc_info=True)
        raise # Re-raise other exceptions

def get_items_by_user_and_connection(
    db: Session, *, user_id: uuid.UUID, connection_id: Optional[uuid.UUID] = None, status_filter: Optional[List[str]] = None
) -> List[AzureBlobSyncItem]:
    """Gets sync items for a specific user, optionally filtering by connection and/or status list."""
    statement = select(AzureBlobSyncItem).where(
        AzureBlobSyncItem.user_id == user_id
    )
    # Apply optional filters
    if connection_id:
        statement = statement.where(AzureBlobSyncItem.connection_id == connection_id)
    if status_filter:
        statement = statement.where(AzureBlobSyncItem.status.in_(status_filter))
    
    statement = statement.order_by(AzureBlobSyncItem.id)
    result = db.execute(statement)
    return list(result.scalars().all())

def get_sync_item_by_id(
    db: Session, *, item_id: int, user_id: uuid.UUID
) -> Optional[AzureBlobSyncItem]:
    """Gets a specific sync item by its DB ID, ensuring it belongs to the user."""
    statement = select(AzureBlobSyncItem).where(
        AzureBlobSyncItem.id == item_id,
        AzureBlobSyncItem.user_id == user_id
    )
    result = db.execute(statement)
    return result.scalars().first()

def remove_sync_item(
    db: Session, *, item_id: int, user_id: uuid.UUID
) -> Optional[AzureBlobSyncItem]:
    """Removes an Azure sync item by its DB ID if it belongs to the user."""
    db_item = get_sync_item_by_id(db=db, item_id=item_id, user_id=user_id)
    if db_item:
        try:
            db.delete(db_item)
            db.commit()
            logger.info(f"Removed Azure sync item ID {item_id} ('{db_item.item_path}') for user {user_id}.")
            return db_item # Return the deleted item
        except Exception as e:
            db.rollback()
            logger.error(f"Error removing Azure sync item ID {item_id} for user {user_id}: {e}", exc_info=True)
            raise
    else:
        logger.warning(f"Attempt to remove non-existent or unowned Azure sync item ID {item_id} by user {user_id}.")
        return None # Indicate item not found or not owned

def update_sync_item_status(
    db: Session, *, db_item: AzureBlobSyncItem, status: str
) -> AzureBlobSyncItem:
    """Updates the status of an Azure sync item."""
    db_item.status = status
    try:
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        logger.info(f"Updated status of Azure sync item ID {db_item.id} ('{db_item.item_path}') to '{status}'.")
        return db_item
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating status for Azure sync item ID {db_item.id}: {e}", exc_info=True)
        raise 