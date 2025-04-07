from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict
# SQLAlchemy imports
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON
from sqlalchemy.sql import func # For default timestamps
from sqlalchemy.dialects.postgresql import UUID # If using UUID
import uuid # If using UUID

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

    model_config = ConfigDict(from_attributes=True)


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
    email: str = Column(String, primary_key=True, index=True, unique=True, nullable=False)
    id: str = Column(String, index=True, unique=True, nullable=True) # Store the MS Graph ID, maybe not PK?
    display_name: str = Column(String, nullable=False)
    # Use server_default for created_at
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Use onupdate for last_login? Or set manually.
    last_login: datetime = Column(DateTime(timezone=True), nullable=True)
    is_active: bool = Column(Boolean, default=True, nullable=False)
    # Store preferences as JSON
    preferences: Dict[str, Any] = Column(JSON, default=dict, nullable=False)
    photo_url: str = Column(Text, nullable=True) # Use Text for potentially long URLs
    organization: str = Column(String, nullable=True)
    # Note: MS Token data is complex, consider if it needs to be stored in DB 
    # or just kept in memory/session. Storing refresh tokens requires encryption.
    # For now, omitting ms_token_data columns.
    # hashed_password: str = Column(String, nullable=True) # If using password auth later

    def __repr__(self):
        return f"<UserDB(email='{self.email}', name='{self.display_name}')>"
