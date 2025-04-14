import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.azure_blob import AzureAuthType # Import the enum from the model

# Base properties shared by other schemas
class AzureBlobConnectionBase(BaseModel):
    name: str = Field(..., example="My Work Storage")
    account_name: str = Field(..., example="myazurestorageaccount")
    auth_type: AzureAuthType = Field(AzureAuthType.CONNECTION_STRING, example=AzureAuthType.CONNECTION_STRING)
    container_name: Optional[str] = Field(None, example="default-container")
    is_active: bool = True

# Properties required for creation (sensitive credentials here)
class AzureBlobConnectionCreate(AzureBlobConnectionBase):
    # Credentials are required on creation, but not shown on read
    credentials: str = Field(..., example="DefaultEndpointsProtocol=https...AccountKey=...")

# Properties required for updating
class AzureBlobConnectionUpdate(BaseModel):
    name: Optional[str] = None
    account_name: Optional[str] = None
    auth_type: Optional[AzureAuthType] = None
    credentials: Optional[str] = None # Allow updating credentials
    container_name: Optional[str] = None
    is_active: Optional[bool] = None

# Properties to return to client (sensitive credentials NOT included)
class AzureBlobConnectionRead(AzureBlobConnectionBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Pydantic V2 uses this instead of orm_mode

# Schema for representing a blob object (file or directory) in a listing
class AzureBlobObject(BaseModel):
    name: str = Field(..., description="Name of the blob or directory (basename)", example="document.pdf or folder/")
    path: str = Field(..., description="Full path of the blob or prefix", example="folder/document.pdf or folder/subfolder/")
    isDirectory: bool = Field(..., description="True if the item is a directory (prefix)", example=False)
    size: Optional[int] = Field(None, description="Size of the blob in bytes (None for directories)", example=10240)
    lastModified: Optional[datetime] = Field(None, description="Last modified timestamp (None for directories)", example="2023-10-27T10:30:00Z")
    etag: Optional[str] = Field(None, description="ETag of the blob (None for directories)", example='"0x8DBB7B8..."')
    content_type: Optional[str] = Field(None, description="Content type of the blob (None for directories)", example="application/pdf")

    class Config:
        from_attributes = True # Allow creating from object attributes 