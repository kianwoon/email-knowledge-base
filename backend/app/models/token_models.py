from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

# SQLAlchemy imports
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text
# Use PostgreSQL specific UUID type
from sqlalchemy.dialects.postgresql import UUID as PG_UUID 
from app.db.session import Base # Import Base from the session file

# --- Base Models --- 

class AccessRule(BaseModel):
    field: str = Field(..., description="Metadata field to apply rule on, e.g., 'tags', 'source_id', 'document_type'")
    values: List[str] = Field(..., description="List of values for the field. Allow rule requires ALL values, Deny rule requires ANY value.")

    @validator('values')
    def check_values_not_empty(cls, v):
        if not v:
            raise ValueError('Values list cannot be empty')
        return v
    
    @validator('field')
    def check_field_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Field name cannot be empty')
        return v.strip()

# --- API Request Models --- 

class TokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User-friendly name for the token")
    description: Optional[str] = Field(None, max_length=500, description="Optional description for the token")
    sensitivity: str = Field(..., description="Sensitivity level, e.g., 'public', 'internal'") # TODO: Use Enum?
    allow_rules: List[AccessRule] = Field(default_factory=list, description="List of rules that MUST ALL be met for access")
    deny_rules: List[AccessRule] = Field(default_factory=list, description="List of rules where ANY match denies access")
    expiry: Optional[datetime] = Field(None, description="Optional expiry date/time for the token")
    is_editable: bool = Field(True, description="Whether the token configuration can be edited after creation")

class TokenUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sensitivity: Optional[str] = Field(None) # TODO: Use Enum?
    allow_rules: Optional[List[AccessRule]] = None
    deny_rules: Optional[List[AccessRule]] = None
    expiry: Optional[datetime] = None
    is_editable: Optional[bool] = None
    # Cannot update is_active directly via API, managed internally based on expiry
    # Cannot update token_value

# NEW: Model for bundling tokens
class TokenBundleRequest(BaseModel):
    token_ids: List[uuid.UUID] = Field(..., description="List of token UUIDs to bundle.", min_items=2)
    name: str = Field(..., min_length=1, max_length=100, description="Name for the new bundled token.")
    description: Optional[str] = Field(None, max_length=500, description="Optional description for the bundled token.")

# --- SQLAlchemy Database Model (Refactored for PostgreSQL) --- 

class TokenDB(Base):
    __tablename__ = "tokens"

    # Use PG_UUID for PostgreSQL
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True) # Use Text for potentially longer descriptions
    # token_value: Do we need to store the raw value in DB? 
    # Typically NO. We store the hash and return raw value only once upon creation.
    # Let's remove the raw token_value column from the DB model for better security.
    hashed_token = Column(String, nullable=False, unique=True, index=True) # Store the hash for verification
    sensitivity = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    owner_email = Column(String, nullable=False, index=True) # Assuming email is string
    expiry = Column(DateTime(timezone=True), nullable=True)
    is_editable = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True) 
    allow_rules = Column(JSON, nullable=False, default=lambda: []) # JSON type is generally compatible
    deny_rules = Column(JSON, nullable=False, default=lambda: [])  # JSON type is generally compatible

    # Removed Pydantic Config and validators from SQLAlchemy model

# --- API Response Models --- 

class TokenResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    token_value: Optional[str] = None # Only include raw token on create, otherwise None
    sensitivity: str
    created_at: datetime
    updated_at: datetime
    owner_email: str
    expiry: Optional[datetime] = None
    is_editable: bool
    is_active: bool
    allow_rules: List[AccessRule] # Parse JSONB back into model
    deny_rules: List[AccessRule]  # Parse JSONB back into model

    @validator('allow_rules', 'deny_rules', pre=True)
    def parse_rules(cls, v):
        if isinstance(v, list):
            # If already parsed (e.g., from DB model via orm_mode), return directly
            if all(isinstance(item, AccessRule) for item in v):
                 return v
             # If coming from raw JSON/dict list from DB
            return [AccessRule(**item) for item in v]
        return [] # Default to empty list if input is not a list

    class Config:
        orm_mode = True

# --- Token Export Model (for middleware consumption) --- 

class TokenExport(BaseModel):
    id: uuid.UUID # Added ID here as well
    # token_value: str -> Should not be needed here if middleware verifies hash
    hashed_token: str = Field(..., description="Hashed token value for server-side verification")
    sensitivity: str = Field(..., description="Sensitivity level associated with the token")
    owner_email: str = Field(..., description="Email of the token owner")
    is_active: bool = Field(..., description="Whether the token is currently active (not expired, etc.)")
    allow_rules: List[AccessRule] = Field(..., description="List of allow rules")
    deny_rules: List[AccessRule] = Field(..., description="List of deny rules")

    class Config:
        orm_mode = True # Useful if creating from TokenDB objects

    @validator('allow_rules', 'deny_rules', pre=True)
    def parse_rules_for_export(cls, v):
        if isinstance(v, list):
             # Similar parsing logic as TokenResponse
            if all(isinstance(item, AccessRule) for item in v):
                 return v
            # If coming from raw JSON/dict list from DB
            return [AccessRule(**item) for item in v]
        return [] # Default to empty list if input is not a list 