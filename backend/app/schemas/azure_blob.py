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