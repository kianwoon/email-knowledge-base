from pydantic import BaseModel, Field
from typing import Optional, List
import datetime

# --- S3 Configuration Schemas ---

class S3ConfigBase(BaseModel):
    role_arn: str = Field(..., description="AWS IAM Role ARN for S3 access", example="arn:aws:iam::123456789012:role/MyS3AccessRole")

class S3ConfigCreate(S3ConfigBase):
    pass

class S3ConfigResponse(S3ConfigBase):
    # Assuming user_email is the FK identifier used in the model
    user_email: str 
    # id: int # Include if you need the AwsCredential primary key ID

    class Config:
        from_attributes = True # Pydantic V2

# --- S3 Browser Schemas ---

class S3Bucket(BaseModel):
    name: str
    creation_date: Optional[datetime.datetime] = None

class S3Object(BaseModel):
    key: str # Full path including prefix
    is_folder: bool = False
    size: Optional[int] = None
    last_modified: Optional[datetime.datetime] = None

# --- S3 Ingestion Schemas ---

class S3IngestRequest(BaseModel):
    bucket: str
    keys: List[str] = Field(..., description="List of specific object keys or prefixes (folders) to ingest")


# --- S3 Sync Item Schemas (Similar to SharePoint) ---

class S3SyncItemBase(BaseModel):
    item_type: str = Field(..., description="Type of the item: 'file' or 'prefix'")
    s3_bucket: str = Field(..., description="Name of the S3 bucket")
    s3_key: str = Field(..., description="Full S3 key of the object or prefix")
    item_name: str = Field(..., description="Base name of the file/prefix")

class S3SyncItemCreate(S3SyncItemBase):
    pass # No extra fields needed for creation

class S3SyncItem(S3SyncItemBase):
    id: int # Database primary key
    user_id: str # User identifier (e.g., email)
    status: str = Field(..., description="Current status: pending, processing, completed, failed")

    class Config:
        from_attributes = True # Enable ORM mode 