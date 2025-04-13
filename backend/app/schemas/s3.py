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