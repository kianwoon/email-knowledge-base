from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

# SQLAlchemy model for database
class APIKeyDB(Base):
    __tablename__ = "api_keys"
    
    id: Mapped[str] = mapped_column(primary_key=True, index=True)
    user_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    provider: Mapped[str] = mapped_column(String, index=True)  # e.g., "openai", "anthropic"
    encrypted_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationship to user
    user = relationship("UserDB", back_populates="api_keys")

# Pydantic models for API
class APIKeyBase(BaseModel):
    provider: str
    
class APIKeyCreate(APIKeyBase):
    key: str  # Raw API key to be encrypted
    
class APIKey(APIKeyBase):
    id: str
    user_email: str
    created_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool = True
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    ) 