from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date # Add date import

class SharedKnowledgeSearchRequest(BaseModel):
    query: str = Field(..., description="The search query string.")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results to return.")
    # Potential future filters can be added here
    # filter: Optional[Dict[str, Any]] = Field(None, description="Key-value filters for metadata.")


class SharedKnowledgeSearchResult(BaseModel):
    id: str = Field(..., description="Unique identifier of the knowledge item.")
    score: Optional[float] = Field(None, description="Relevance score (typically for vector search).")
    metadata: Dict[str, Any] = Field(..., description="Associated metadata for the item.")
    content: Optional[str] = Field(None, description="The text content or snippet.")
    
    class Config:
        from_attributes = True # Changed from orm_mode


# --- Schemas for Catalog Search ---

class CatalogSearchRequest(BaseModel):
    query: str = Field(..., description="The search query string (will be used for LIKE matching).")
    limit: int = Field(10, ge=1, le=1000, description="Maximum number of results to return (effective limit may be lower based on token).")
    sender: Optional[str] = Field(None, description="Filter results by sender email or name (exact match).")
    date_from: Optional[date] = Field(None, description="Filter results created on or after this date.")
    date_to: Optional[date] = Field(None, description="Filter results created on or before this date.")
    # Add more specific filters as needed, e.g., subject_contains: Optional[str] = None
    
    class Config:
        from_attributes = True


class CatalogSearchResultItem(BaseModel):
    # Define fields likely to exist in the catalog, matching potential token allow_columns
    # Make most fields optional as token might restrict them
    id: Optional[str] = Field(None, description="Unique identifier from the catalog (e.g., email message ID).")
    subject: Optional[str] = Field(None, description="Subject of the item.")
    sender_name: Optional[str] = Field(None, description="Sender's name.")
    sender_email: Optional[str] = Field(None, description="Sender's email address.")
    recipients_display: Optional[str] = Field(None, description="Display string of recipients.")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp.")
    content_preview: Optional[str] = Field(None, description="A short preview or snippet of the content.")
    # Add other potential columns like 'tags', 'source_type', 'attachment_count' etc. if available
    # Dynamically add other allowed columns based on token? Less type-safe.
    # Or return a flexible Dict[str, Any] ?

    class Config:
        from_attributes = True

# Using a generic Dict for flexibility with allow_columns for now
# Revisit if a stricter schema is feasible later
CatalogSearchResult = Dict[str, Any] 