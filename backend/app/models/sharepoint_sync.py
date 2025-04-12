from pydantic import BaseModel
from typing import Optional

# Pydantic models for SharePoint Sync Items (Phase 1)

class SharePointSyncItemBase(BaseModel):
    """Base model with common fields for a SharePoint item to be synced."""
    item_type: str  # e.g., 'file', 'folder'
    sharepoint_item_id: str
    sharepoint_drive_id: str
    item_name: str

class SharePointSyncItemCreate(SharePointSyncItemBase):
    """Model used when adding a new item to the sync list via the API."""
    # For Phase 1, user_id will be derived from the authenticated session
    # in the CRUD layer, so it's not included here.
    pass

class SharePointSyncItem(SharePointSyncItemBase):
    """Model representing a sync item retrieved from the database."""
    id: int
    user_id: str  # Assuming user_id stored in DB is the email string

    class Config:
        from_attributes = True  # Enable ORM mode 