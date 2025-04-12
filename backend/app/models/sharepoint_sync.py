from pydantic import BaseModel
from typing import Optional

# Pydantic model for the base data (used for creation and reading)
class SharePointSyncItemBase(BaseModel):
    item_type: str # 'file' or 'folder'
    sharepoint_item_id: str
    sharepoint_drive_id: str
    item_name: str
    # Status is NOT part of the base/creation model

# Pydantic model for creating an item (input)
# Only inherits fields needed for creation
class SharePointSyncItemCreate(SharePointSyncItemBase):
    pass # No extra fields needed for creation

# Pydantic model for representing an item read from the DB (output)
class SharePointSyncItem(SharePointSyncItemBase):
    id: int # Include the database ID
    user_id: str # Include the user ID
    status: str # <<< status field only needed for output

    class Config:
        from_attributes = True # Enable ORM mode 