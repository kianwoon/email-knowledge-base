from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB # Use JSONB for PostgreSQL
import enum  # Add enum import

# SQLAlchemy imports
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text, Enum, TIMESTAMP, Integer
# Use PostgreSQL specific UUID type
from sqlalchemy.dialects.postgresql import UUID as PG_UUID 
# Import Base from the canonical definition in base_class
from app.db.base_class import Base 
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer

# Define Enum for token_type
class TokenType(enum.Enum):
    PUBLIC = "public"
    SHARE = "share"

# --- Base Models --- 

# Remove AccessRule model
# class AccessRule(BaseModel): ... 

# --- API Request Models --- 

class TokenCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User-friendly name for the token")
    description: Optional[str] = Field(None, max_length=500, description="Optional description for the token")
    sensitivity: str = Field(..., description="Sensitivity level, e.g., 'public', 'internal'") # TODO: Use Enum?
    allow_rules: Optional[List[str]] = Field(default_factory=list, description="List of rules that MUST ALL be met for access")
    deny_rules: Optional[List[str]] = Field(default_factory=list, description="List of rules where ANY match denies access")
    expiry_days: Optional[int] = Field(None, description="Optional number of days until the token expires") # Clarified description
    is_editable: bool = Field(True, description="Whether the token configuration can be edited after creation")

    # --- NEW FIELDS from v3 Plan --- 
    token_type: TokenType = Field(TokenType.PUBLIC, description="Type of the token (public or share)") # Default to PUBLIC
    provider_base_url: Optional[str] = Field(None, description="Base URL of the provider Jarvis (only for share tokens)")
    audience: Optional[Dict[str, Any]] = Field(None, description="Optional audience restrictions (e.g., IP range, org ID)")
    can_export_vectors: bool = Field(False, description="Allow raw vector embeddings in export")
    allow_columns: Optional[List[str]] = Field(None, description="Whitelist of allowed column names for data access") # Use None default for optional list
    allow_attachments: bool = Field(False, description="Allow access to attachments associated with data")
    row_limit: int = Field(10000, description="Maximum number of rows returned per request/export", ge=1)

    # Removed expiry datetime field, using expiry_days as per previous definition

class TokenUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    sensitivity: Optional[str] = Field(None) # TODO: Use Enum?
    allow_rules: Optional[List[str]] = None # Updating rules will trigger backend embedding update
    deny_rules: Optional[List[str]] = None  # Updating rules will trigger backend embedding update
    expiry_days: Optional[int] = Field(None, description="Update expiry in days from now. Use 0 or negative to clear expiry.") # Allow updating expiry days
    is_editable: Optional[bool] = None
    is_active: Optional[bool] = None # Allow updating active status directly if needed

    # --- NEW FIELDS from v3 Plan (Optional for update) ---
    # token_type: is generally not updatable once created
    provider_base_url: Optional[str] = Field(None, description="Update Base URL of the provider Jarvis (only for share tokens)")
    audience: Optional[Dict[str, Any]] = Field(None, description="Update audience restrictions")
    can_export_vectors: Optional[bool] = Field(None, description="Update permission to export raw vector embeddings")
    allow_columns: Optional[List[str]] = Field(None, description="Update whitelist of allowed column names")
    allow_attachments: Optional[bool] = Field(None, description="Update permission to access attachments")
    row_limit: Optional[int] = Field(None, description="Update maximum number of rows", ge=1)

    # Removed expiry datetime field

# NEW: Model for bundling tokens (Assuming bundling combines rules/embeddings appropriately - needs logic adjustment in route)
class TokenBundleRequest(BaseModel):
    token_ids: List[int] = Field(..., description="List of token IDs to bundle.", min_items=1)
    name: str = Field(..., min_length=1, max_length=100, description="Name for the new bundled token.")
    description: Optional[str] = Field(None, max_length=500, description="Optional description for the bundled token.")

# --- API Response Models --- 

class TokenResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    sensitivity: str
    token_preview: str # e.g., "token_123...abc"
    owner_email: str
    created_at: datetime
    expiry: Optional[datetime]
    is_active: bool
    is_editable: bool # Added is_editable to response
    allow_rules: Optional[List[str]] = Field(default_factory=list)
    deny_rules: Optional[List[str]] = Field(default_factory=list)
    
    # --- NEW FIELDS from v3 Plan --- 
    token_type: TokenType 
    provider_base_url: Optional[str]
    audience: Optional[Dict[str, Any]]
    accepted_by: Optional[int] # Include receiver acceptance info
    accepted_at: Optional[datetime] # Include receiver acceptance info
    can_export_vectors: bool
    allow_columns: Optional[List[str]]
    allow_attachments: bool
    row_limit: int
    # --- End NEW FIELDS ---
    
    # Embeddings not included in standard response
    
    model_config = ConfigDict(
        from_attributes=True,  # Use this instead of orm_mode for Pydantic v2
        use_enum_values=True # Ensure Enum values are used in the response
    )

# --- Token Export Model (for middleware consumption) --- 

class TokenExport(BaseModel):
    id: int # Changed to int to match TokenDB
    hashed_token: str = Field(..., description="Hashed token value for server-side verification")
    sensitivity: str = Field(..., description="Sensitivity level associated with the token")
    owner_email: str = Field(..., description="Email of the token owner")
    is_active: bool = Field(..., description="Whether the token is currently active (not expired, etc.)")
    allow_rules: List[str] = Field(default_factory=list)
    deny_rules: List[str] = Field(default_factory=list)

    # --- NEW FIELDS from v3 Plan (for Gateway Logic) --- 
    token_type: TokenType 
    provider_base_url: Optional[str]
    audience: Optional[Dict[str, Any]]
    can_export_vectors: bool
    allow_columns: Optional[List[str]] # Crucial for projection logic
    allow_attachments: bool # Crucial for attachment handling
    row_limit: int # Crucial for limiting results
    # accepted_by/at not needed for export/gateway logic directly
    # --- End NEW FIELDS ---

    # Embeddings are internal, not typically exported unless needed by middleware
    # For now, assume middleware only needs rules

    model_config = ConfigDict(
        from_attributes=True,  # Use this instead of orm_mode for Pydantic v2
        use_enum_values=True # Ensure Enum values are used
    )

# SQLAlchemy model for the 'tokens' table
class TokenDB(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True) 
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True) 
    # REMOVED old hashed_token column
    # hashed_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    
    # --- ADDED prefix and secret columns --- 
    token_prefix: Mapped[Optional[str]] = mapped_column(String(11), unique=True, index=True, nullable=True) # e.g., kb_ + 8 hex chars = 11 len. Unique & Indexed. Nullable for migration.
    hashed_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True) # Hash of secret part. Nullable for migration.
    # --- END ADDITION --- 
    
    owner_email: Mapped[str] = mapped_column(String(255), index=True) 
    sensitivity: Mapped[str] = mapped_column(String(50), nullable=False, default="public", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Add is_editable column definition
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Change rules columns to list of strings
    allow_rules: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    deny_rules: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    # Embeddings stored as JSONB (likely List[List[float]])
    allow_embeddings: Mapped[Optional[List[Any]]] = mapped_column(JSONB, nullable=True)
    deny_embeddings: Mapped[Optional[List[Any]]] = mapped_column(JSONB, nullable=True)
    
    # --- NEW COLUMNS from v3 Plan ---
    token_type: Mapped[TokenType] = mapped_column(Enum(TokenType), nullable=False, default=TokenType.PUBLIC, server_default=TokenType.PUBLIC.value)
    provider_base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audience: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True) # Using Dict for JSONB
    accepted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # As per plan, using INT. Consider FK later.
    accepted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    can_export_vectors: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    allow_columns: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True) # JSONB can store lists
    allow_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    row_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10000, server_default='10000')
    # --- End NEW COLUMNS ---

    def __repr__(self):
        return f"<TokenDB(id={self.id}, name='{self.name}', owner='{self.owner_email}', type='{self.token_type.value}')>" # Updated repr

# Model to return the full token value ONCE upon creation
class TokenCreateResponse(TokenResponse):
     token_value: str

# Model for internal validation of token value
class TokenValidationRequest(BaseModel):
    token_value: str

class TokenValidationResponse(BaseModel):
    is_valid: bool
    # token_data would use TokenExport, which now excludes embeddings
    token_data: Optional[TokenExport] = None # Return exported data if valid 
    
# +++ ADDED: Response model for shared search results +++
class SharedMilvusResult(BaseModel):
    """
    Represents a single search result item returned by the shared knowledge search endpoint.
    Metadata is filtered based on the requesting token's permissions.
    """
    id: str = Field(..., description="The unique identifier (PK) of the retrieved document chunk from Milvus.")
    score: float = Field(..., description="The relevance score of the result (higher is generally better after reranking).")
    metadata: Dict[str, Any] = Field(..., description="Associated metadata for the document chunk, filtered according to the token's 'allow_columns' and 'allow_attachments' permissions.")

    model_config = ConfigDict(
        from_attributes=True, # Allow creation from ORM/DB objects if needed elsewhere
    )

# NEW: Request body model for POST /search
class SharedSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The search query string.")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of search results to return (subject to token row limit). Default is 10.")

# Pydantic model for creating a token
class TokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
# --- END ADDITION --- 