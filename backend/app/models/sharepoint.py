from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Note: Aliases are used to map Pydantic fields to the camelCase keys
# returned by the Microsoft Graph API.

class SharePointSite(BaseModel):
    """Model representing a SharePoint site based on Graph API response."""
    id: str
    name: Optional[str] = None # Site name (sometimes not present in search results)
    display_name: str = Field(..., alias='displayName') # User-friendly display name
    web_url: str = Field(..., alias='webUrl') # URL to the site
    description: Optional[str] = None
    created_datetime: Optional[datetime] = Field(None, alias='createdDateTime')
    last_modified_datetime: Optional[datetime] = Field(None, alias='lastModifiedDateTime')

    class Config:
        populate_by_name = True # Allows using alias for population

class SharePointDrive(BaseModel):
    """Model representing a SharePoint document library (drive)."""
    id: str
    name: Optional[str] = None # Drive name
    drive_type: Optional[str] = Field(None, alias='driveType') # e.g., 'documentLibrary'
    web_url: str = Field(..., alias='webUrl') # URL to the drive
    description: Optional[str] = None
    created_datetime: Optional[datetime] = Field(None, alias='createdDateTime')
    last_modified_datetime: Optional[datetime] = Field(None, alias='lastModifiedDateTime')

    class Config:
        populate_by_name = True

class SharePointItem(BaseModel):
    """Model representing an item (file or folder) in a SharePoint drive."""
    id: str
    name: Optional[str] = None # File or folder name
    web_url: str = Field(..., alias='webUrl') # URL to the item
    size: Optional[int] = None # Size in bytes (present for files)
    created_datetime: Optional[datetime] = Field(None, alias='createdDateTime')
    last_modified_datetime: Optional[datetime] = Field(None, alias='lastModifiedDateTime')
    # These flags are added by the service layer, not from Graph directly
    is_folder: bool = Field(False, description="True if the item is a folder.") 
    is_file: bool = Field(False, description="True if the item is a file.")

    class Config:
        populate_by_name = True 

class SharePointDownloadRequest(BaseModel):
    """Request body for initiating a file download and processing task."""
    drive_id: str = Field(..., description="ID of the SharePoint drive containing the file.")
    item_id: str = Field(..., description="ID of the SharePoint file item to download.")
    # Optional: Add knowledge base ID or other processing parameters if needed
    # knowledge_base_id: Optional[str] = None 