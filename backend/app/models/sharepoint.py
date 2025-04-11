from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl

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

# --- Models for Insights API (/insights/used) --- 
# Note: Renamed classes for clarity vs. TypeScript interfaces

class InsightResourceReference(BaseModel):
    """Reference to the resource associated with an insight."""
    webUrl: Optional[str] = None
    id: Optional[str] = None
    type: Optional[str] = None

class InsightResourceVisualization(BaseModel):
    """How the insight resource should be visualized."""
    title: Optional[str] = None
    type: Optional[str] = None # e.g., Word, Excel etc.
    previewImageUrl: Optional[str] = None

class UsedInsight(BaseModel):
    """Represents an item returned by the /insights/used endpoint."""
    id: str
    resourceVisualization: Optional[InsightResourceVisualization] = None
    resourceReference: Optional[InsightResourceReference] = None
    # Add lastUsed fields if needed later

# --- Models for /me/drive/recent Endpoint --- # (Corrected Syntax)

class FileSystemInfo(BaseModel):
    """Represents file system specific metadata."""
    createdDateTime: Optional[datetime] = None
    lastModifiedDateTime: Optional[datetime] = None

class Identity(BaseModel):
    """Represents an identity (user, application)."""
    displayName: Optional[str] = None
    # Add other fields like 'id' or 'email' if needed/available

class IdentitySet(BaseModel):
    """Represents a set of identities."""
    user: Optional[Identity] = None
    application: Optional[Identity] = None
    device: Optional[Identity] = None
    # Add group, etc. if needed

class BaseItemInfo(BaseModel):
    """Common properties for DriveItem."""
    id: str
    name: Optional[str] = None
    webUrl: Optional[str] = Field(None, alias="webUrl") # Use alias for consistency
    createdDateTime: Optional[datetime] = None
    lastModifiedDateTime: Optional[datetime] = None
    size: Optional[int] = None
    lastModifiedBy: Optional[IdentitySet] = None # Contains the last modifier info

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "extra": "ignore"
    }

class FileInfo(BaseModel):
    """Present on DriveItems that represent files."""
    mimeType: Optional[str] = None

class FolderInfo(BaseModel):
    """Present on DriveItems that represent folders."""
    childCount: Optional[int] = None

class RecentDriveItem(BaseItemInfo):
    """Represents a DriveItem specifically from the /recent endpoint."""
    file: Optional[FileInfo] = None
    folder: Optional[FolderInfo] = None

    @property
    def is_folder(self) -> bool:
        return self.folder is not None

    @property
    def last_modifier_name(self) -> Optional[str]:
        return self.lastModifiedBy.user.displayName if self.lastModifiedBy and self.lastModifiedBy.user else None

# --- End Models for /me/drive/recent ---

# Placeholder for SharedInsight model if needed later
# class SharedInsight(BaseModel): ... 