import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

# Use 'Schema' suffix for Pydantic models to avoid confusion
from app.models.sharepoint_sync import SharePointSyncItem as SharePointSyncItemSchema, SharePointSyncItemCreate
# Use 'Model' suffix for SQLAlchemy models
from app.db.models.sharepoint_sync_item import SharePointSyncItem as SharePointSyncItemModel
# Import the 'in_' operator and func for lower()
from sqlalchemy import or_, func

logger = logging.getLogger(__name__)

def add_item(db: Session, *, item_in: SharePointSyncItemCreate, user_email: str) -> SharePointSyncItemModel | None:
    """
    Adds a new SharePoint item to the user's sync list in the database.

    Args:
        db: The database session.
        item_in: The Pydantic model containing the item details.
        user_email: The email address of the user adding the item.

    Returns:
        The created SharePointSyncItemModel object or None if it already exists.
    """
    # Instantiate the SQLAlchemy Model using user_email
    db_item = SharePointSyncItemModel(
        **item_in.model_dump(),
        user_id=user_email, # Store email in user_id column
        status='pending'
    )
    try:
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        logger.info(f"Added item '{item_in.item_name}' (ID: {item_in.sharepoint_item_id}) to sync list for user {user_email}.")
        return db_item
    except IntegrityError: # Handles unique constraint violation
        db.rollback()
        logger.warning(f"Item '{item_in.item_name}' (ID: {item_in.sharepoint_item_id}) already exists in sync list for user {user_email}. Skipping.")
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding item {item_in.sharepoint_item_id} for user {user_email}: {e}", exc_info=True)
        raise # Re-raise other exceptions

def remove_item(db: Session, *, user_email: str, sharepoint_item_id: str) -> SharePointSyncItemModel | None:
    """
    Removes a specific SharePoint item from the user's sync list.

    Args:
        db: The database session.
        user_email: The email address of the user.
        sharepoint_item_id: The SharePoint ID of the item to remove.

    Returns:
        The deleted SharePointSyncItemModel object or None if not found.
    """
    # Query using the SQLAlchemy Model and user_email
    db_item = db.query(SharePointSyncItemModel).filter(
        SharePointSyncItemModel.user_id == user_email, # Filter by email
        SharePointSyncItemModel.sharepoint_item_id == sharepoint_item_id
    ).first()

    if db_item:
        try:
            db.delete(db_item)
            db.commit()
            logger.info(f"Removed item '{db_item.item_name}' (ID: {sharepoint_item_id}) from sync list for user {user_email}.")
            # Note: For Phase 2, Qdrant deletion logic would go here if status was 'processed'.
            return db_item
        except Exception as e:
            db.rollback()
            logger.error(f"Error removing item {sharepoint_item_id} for user {user_email}: {e}", exc_info=True)
            raise
    else:
        logger.warning(f"Attempted to remove non-existent item ID {sharepoint_item_id} for user {user_email}.")
        return None

def get_sync_list_for_user(db: Session, *, user_email: str) -> List[SharePointSyncItemModel]:
    """
    Retrieves the entire sync list for a given user.

    Args:
        db: The database session.
        user_email: The email address of the user.

    Returns:
        A list of SharePointSyncItemModel objects for the user.
    """
    # Query using the SQLAlchemy Model and user_email
    return db.query(SharePointSyncItemModel).filter(SharePointSyncItemModel.user_id == user_email).all()

def clear_sync_list_for_user(db: Session, *, user_email: str) -> int:
    """
    Deletes all items from the sync list for a given user.

    Args:
        db: The database session.
        user_email: The email address of the user whose list should be cleared.

    Returns:
        The number of items deleted.
    """
    try:
        # Query using the SQLAlchemy Model and user_email
        num_deleted = db.query(SharePointSyncItemModel).filter(SharePointSyncItemModel.user_id == user_email).delete()
        db.commit()
        logger.info(f"Cleared {num_deleted} items from sync list for user {user_email}.")
        # Note: For Phase 2, corresponding Qdrant deletions might be needed if items were processed.
        return num_deleted
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing sync list for user {user_email}: {e}", exc_info=True)
        raise

def get_completed_sync_items_for_user(db: Session, *, user_email: str) -> List[SharePointSyncItemModel]:
    """
    Retrieves all sync items marked as 'completed' for a given user.

    Args:
        db: The database session.
        user_email: The email address of the user.

    Returns:
        A list of completed SharePointSyncItemModel objects for the user, ordered by item name.
    """
    # Assuming 'completed' is the string representation of the status in the database
    # Query using the SQLAlchemy Model and user_email
    return db.query(SharePointSyncItemModel).filter(
        SharePointSyncItemModel.user_id == user_email, # Filter by email
        SharePointSyncItemModel.status == 'completed'
    ).order_by(SharePointSyncItemModel.item_name.asc()).all()

def get_active_sync_list_for_user(db: Session, user_email: str) -> List[SharePointSyncItemModel]:
    """
    Retrieves sync list items with status 'pending' or 'processing' for a specific user.
    These represent items that have been added but not yet successfully completed.
    Comparison for email and status is case-insensitive.

    Args:
        db: The database session.
        user_email: The email address of the user.

    Returns:
        A list of active (pending or processing) SharePointSyncItemModel objects for the user.
    """
    lower_user_email = user_email.lower()
    active_statuses = ['pending', 'processing']
    logger.info(f"Querying active sync items for user_id (email, case-insensitive): {lower_user_email} with statuses: {active_statuses}")
    
    try:
        # Query using case-insensitive filters for email and status
        items = db.query(SharePointSyncItemModel).\
            filter(
                func.lower(SharePointSyncItemModel.user_id) == lower_user_email, 
                func.lower(SharePointSyncItemModel.status).in_(active_statuses)
            ).\
            all()
        logger.info(f"Database query returned {len(items)} active sync items for user {lower_user_email}.")
        return items
    except Exception as e:
        logger.error(f"Database error fetching active sync items for user {user_email}: {e}", exc_info=True)
        raise

def get_item_by_sp_id(db: Session, user_email: str, sharepoint_item_id: str) -> Optional[SharePointSyncItemModel]:
    """
    Retrieves a specific sync list item by its SharePoint ID for a user.

    Args:
        db: The database session.
        user_email: The email address of the user.
        sharepoint_item_id: The SharePoint ID of the item to retrieve.

    Returns:
        The retrieved SharePointSyncItemModel object or None if not found.
    """
    # Query using the SQLAlchemy Model and user_email
    return db.query(SharePointSyncItemModel).\
        filter(SharePointSyncItemModel.user_id == user_email, SharePointSyncItemModel.sharepoint_item_id == sharepoint_item_id).\
        first()

def update_item_status(db: Session, item_db_id: int, status: str) -> Optional[SharePointSyncItemModel]:
    """
    Updates the status of a specific sync list item by its database ID.
    NOTE: This function identifies the item by its *internal database ID* (item_db_id),
    not by user email. It assumes the item already belongs to the correct user context
    if called appropriately (e.g., from a task associated with that user).

    Args:
        db: The database session.
        item_db_id: The database ID of the item to update.
        status: The new status for the item.

    Returns:
        The updated SharePointSyncItemModel object or None if not found.
    """
    # Query using the SQLAlchemy Model
    db_item = db.query(SharePointSyncItemModel).filter(SharePointSyncItemModel.id == item_db_id).first()
    if db_item:
        db_item.status = status
        try:
            db.commit()
            db.refresh(db_item)
            return db_item
        except Exception as e:
            logger.error(f"Error updating status for item DB ID {item_db_id} to {status}: {e}", exc_info=True)
            db.rollback()
            raise # Re-raise after rollback
    return None

# Potential future functions:
# - update_item(...) to change name/drive/etc.?
# - bulk_update_status(...) 