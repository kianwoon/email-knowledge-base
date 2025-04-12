import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.sharepoint_sync import SharePointSyncItemCreate
from app.db.models.sharepoint_sync_item import SharePointSyncItem

logger = logging.getLogger(__name__)

def add_item(db: Session, *, item_in: SharePointSyncItemCreate, user_id: str) -> SharePointSyncItem | None:
    """
    Adds a new SharePoint item to the user's sync list in the database.

    Args:
        db: The database session.
        item_in: The Pydantic model containing the item details.
        user_id: The ID (email) of the user adding the item.

    Returns:
        The created SharePointSyncItem object or None if it already exists.
    """
    db_item = SharePointSyncItem(
        **item_in.model_dump(),
        user_id=user_id
    )
    try:
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        logger.info(f"Added item '{item_in.item_name}' (ID: {item_in.sharepoint_item_id}) to sync list for user {user_id}.")
        return db_item
    except IntegrityError: # Handles unique constraint violation
        db.rollback()
        logger.warning(f"Item '{item_in.item_name}' (ID: {item_in.sharepoint_item_id}) already exists in sync list for user {user_id}. Skipping.")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding item {item_in.sharepoint_item_id} for user {user_id}: {e}", exc_info=True)
        raise # Re-raise other exceptions

def remove_item(db: Session, *, user_id: str, sharepoint_item_id: str) -> SharePointSyncItem | None:
    """
    Removes a specific SharePoint item from the user's sync list.

    Args:
        db: The database session.
        user_id: The ID (email) of the user.
        sharepoint_item_id: The SharePoint ID of the item to remove.

    Returns:
        The deleted SharePointSyncItem object or None if not found.
    """
    db_item = db.query(SharePointSyncItem).filter(
        SharePointSyncItem.user_id == user_id,
        SharePointSyncItem.sharepoint_item_id == sharepoint_item_id
    ).first()

    if db_item:
        try:
            db.delete(db_item)
            db.commit()
            logger.info(f"Removed item '{db_item.item_name}' (ID: {sharepoint_item_id}) from sync list for user {user_id}.")
            # Note: For Phase 2, Qdrant deletion logic would go here if status was 'processed'.
            return db_item
        except Exception as e:
            db.rollback()
            logger.error(f"Error removing item {sharepoint_item_id} for user {user_id}: {e}", exc_info=True)
            raise
    else:
        logger.warning(f"Attempted to remove non-existent item ID {sharepoint_item_id} for user {user_id}.")
        return None

def get_sync_list_for_user(db: Session, *, user_id: str) -> list[SharePointSyncItem]:
    """
    Retrieves the entire sync list for a given user.

    Args:
        db: The database session.
        user_id: The ID (email) of the user.

    Returns:
        A list of SharePointSyncItem objects for the user.
    """
    return db.query(SharePointSyncItem).filter(SharePointSyncItem.user_id == user_id).all()

def clear_sync_list_for_user(db: Session, *, user_id: str) -> int:
    """
    Deletes all items from the sync list for a given user.

    Args:
        db: The database session.
        user_id: The ID (email) of the user whose list should be cleared.

    Returns:
        The number of items deleted.
    """
    try:
        num_deleted = db.query(SharePointSyncItem).filter(SharePointSyncItem.user_id == user_id).delete()
        db.commit()
        logger.info(f"Cleared {num_deleted} items from sync list for user {user_id}.")
        # Note: For Phase 2, corresponding Qdrant deletions might be needed if items were processed.
        return num_deleted
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing sync list for user {user_id}: {e}", exc_info=True)
        raise 