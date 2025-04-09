from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB # Use JSONB for PostgreSQL

# SQLAlchemy imports
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text
# Use PostgreSQL specific UUID type
from sqlalchemy.dialects.postgresql import UUID as PG_UUID 
# Import Base from the canonical definition in base_class
from app.db.base_class import Base 
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer

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
    allow_topics: Optional[List[str]] = None
    deny_topics: Optional[List[str]] = None
    expiry_days: Optional[int] = None # Optional expiry in days

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
    allow_topics: Optional[List[str]] = None
    deny_topics: Optional[List[str]] = None

# NEW: Model for bundling tokens
class TokenBundleRequest(BaseModel):
    token_ids: List[uuid.UUID] = Field(..., description="List of token UUIDs to bundle.", min_items=2)
    name: str = Field(..., min_length=1, max_length=100, description="Name for the new bundled token.")
    description: Optional[str] = Field(None, max_length=500, description="Optional description for the bundled token.")

# --- API Response Models --- 

class TokenResponse(BaseModel):
    # This model definition seems duplicated later - keeping the second one
    pass # Placeholder - remove this section later if the second one is confirmed correct

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

# SQLAlchemy model for the 'tokens' table - THIS IS THE SECOND, CORRECT DEFINITION
class TokenDB(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True) 
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Added description
    hashed_token: Mapped[str] = mapped_column(String(255), unique=True, index=True) 
    owner_email: Mapped[str] = mapped_column(String(255), index=True) 
    sensitivity: Mapped[str] = mapped_column(String(50), nullable=False, default="public", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_rules: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, nullable=True)
    deny_rules: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONB, nullable=True)
    
    def __repr__(self):
        return f"<TokenDB(id={self.id}, name='{self.name}', owner='{self.owner_email}')>"

# Model to return the full token value ONCE upon creation
class TokenCreateResponse(TokenResponse):
     token_value: str 