from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

# SQLAlchemy model for database
class UserPreferenceDB(Base):
    __tablename__ = "user_preferences"
    
    id: Mapped[str] = mapped_column(primary_key=True, index=True)
    user_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True)
    preference_key: Mapped[str] = mapped_column(String, index=True)  # e.g., "default_llm_model"
    preference_value: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship to user
    user = relationship("UserDB", back_populates="preferences_list")

# Pydantic models for API
class UserPreferenceBase(BaseModel):
    preference_key: str
    preference_value: str
    
class UserPreferenceCreate(UserPreferenceBase):
    pass
    
class UserPreference(UserPreferenceBase):
    id: str
    user_email: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    ) 