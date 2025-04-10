from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict
# SQLAlchemy imports
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON, LargeBinary
from sqlalchemy.sql import func # For default timestamps
from sqlalchemy.dialects.postgresql import UUID # If using UUID
import uuid # If using UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import LargeBinary # Import LargeBinary
from sqlalchemy.dialects.postgresql import JSONB # Import JSONB for PostgreSQL
from sqlalchemy import func # Import func for server_default
from typing import List as TypeList

# --- Removed for Manual Encryption (Option A) ---
# from sqlalchemy_utils import EncryptedType 
# from app.config import settings
# --- End Removed ---

# Import the Base class from your SQLAlchemy setup
from app.db.base_class import Base 


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: List[str]


class UserBase(BaseModel):
    email: EmailStr
    display_name: str


class UserCreate(UserBase):
    pass


class User(UserBase):
    id: str | None = None # Microsoft Graph User ID (GUID)
    created_at: datetime | None = None
    last_login: datetime | None = None
    ms_token_data: Optional[TokenData] = None
    is_active: bool = True
    preferences: Dict[str, Any] = Field(default_factory=dict)
    photo_url: Optional[str] = None
    organization: Optional[str] = None
    # Add field to temporarily hold MS token passed via JWT
    ms_access_token: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        # Exclude these fields when creating from attributes if they don't exist
        populate_by_name=True,
        extra="ignore"  # Ignore extra fields to avoid errors
    )


class UserInDB(User):
    hashed_password: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime


class AuthResponse(BaseModel):
    user: User
    token: Token


# --- NEW: SQLAlchemy DB Model --- 

class UserDB(Base):
    __tablename__ = "users"

    # Assuming email is the primary identifier used in MS Graph & JWT 'sub'
    # If using the MS Graph GUID 'id' as primary key, change accordingly
    email: Mapped[str] = mapped_column(primary_key=True, index=True, unique=True, nullable=False)
    id: Mapped[str] = mapped_column(index=True, unique=True, nullable=True) # Store the MS Graph ID, maybe not PK?
    display_name: Mapped[str] = mapped_column(nullable=False)
    # Use server_default for created_at
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Use onupdate for last_login? Or set manually.
    last_login: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login: datetime = Column(DateTime(timezone=True), nullable=True)
    is_active: bool = Column(Boolean, default=True, nullable=False)
    # Store preferences as JSON
    preferences: Dict[str, Any] = Column(JSON, default=dict, nullable=False)
    photo_url: str = Column(Text, nullable=True) # Use Text for potentially long URLs
    organization: str = Column(String, nullable=True)
    # Note: MS Token data is complex, consider if it needs to be stored in DB 
    # or just kept in memory/session. Storing refresh tokens requires encryption.
    # --- Reverted to String for Base64 Encoded Encrypted Token --- 
    ms_refresh_token: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Store as Base64 Text
    # --- End Reverted ---
    # hashed_password: str = Column(String, nullable=True) # If using password auth later
    
    # +++ Add field for last KB task ID +++
    last_kb_task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    # --- End Add --- 

    # Relationship to API keys
    api_keys = relationship("APIKeyDB", back_populates="user", cascade="all, delete-orphan")
    
    # Relationship to user preferences - use Mapped
    preferences_list: Mapped[TypeList["UserPreferenceDB"]] = relationship("UserPreferenceDB", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserDB(email='{self.email}', name='{self.display_name}')>"
