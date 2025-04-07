from pydantic import BaseModel, Field, EmailStr, validator
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

# Define allowed sensitivity levels (adjust as needed)
# TODO: Potentially move SENSITIVITY_LEVELS to settings or a central config
SENSITIVITY_LEVELS = ["public", "internal", "confidential", "strict-confidential"] # Example levels

class AccessRule(BaseModel):
    """ Defines a rule based on metadata field and allowed/denied values """
    field: str = Field(..., description="Metadata field to filter on (e.g., 'tags', 'source', 'document_type')")
    values: List[str] = Field(..., description="List of allowed/denied values for the field")

class TokenBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User-friendly name for the token")
    description: Optional[str] = Field(None, max_length=500, description="Optional description for the token")
    sensitivity: str = Field(..., description=f"Maximum sensitivity level allowed by this token. Must be one of {SENSITIVITY_LEVELS}")
    allow_rules: List[AccessRule] = Field(default_factory=list, description="List of rules defining allowed metadata values (Acts like AND for filtering results)")
    deny_rules: List[AccessRule] = Field(default_factory=list, description="List of rules defining denied metadata values (Acts like OR for filtering results)")
    expiry: Optional[datetime] = Field(None, description="Optional expiration timestamp for the token (UTC recommended)")
    is_editable: bool = Field(True, description="Whether the token configuration can be edited after creation")

    # Validator for sensitivity level
    @validator('sensitivity')
    def sensitivity_must_be_valid(cls, v):
        if v not in SENSITIVITY_LEVELS:
            raise ValueError(f'Sensitivity must be one of {SENSITIVITY_LEVELS}')
        return v

class TokenCreate(TokenBase):
    # Owner is added during creation based on authenticated user
    pass

class TokenInDBBase(TokenBase):
    id: UUID = Field(..., description="Unique identifier for the token (Qdrant point ID)")
    owner_email: EmailStr = Field(..., description="Email of the user who owns the token")
    created_at: datetime = Field(..., description="Timestamp when the token was created")
    updated_at: datetime = Field(..., description="Timestamp when the token was last updated")

# Represents a token object as stored in Qdrant's payload
class TokenPayload(TokenInDBBase):
    pass

# Represents a token object returned by API endpoints
class Token(TokenInDBBase):
    pass

class TokenUpdate(BaseModel):
    # Allows partial updates via PATCH
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sensitivity: Optional[str] = None
    allow_rules: Optional[List[AccessRule]] = None
    deny_rules: Optional[List[AccessRule]] = None
    expiry: Optional[datetime] = None # Use Optional[datetime] to allow setting expiry to None
    is_editable: Optional[bool] = None

    # Validator for sensitivity level if provided
    @validator('sensitivity')
    def sensitivity_must_be_valid(cls, v):
        if v is not None and v not in SENSITIVITY_LEVELS:
            raise ValueError(f'Sensitivity must be one of {SENSITIVITY_LEVELS}')
        return v 