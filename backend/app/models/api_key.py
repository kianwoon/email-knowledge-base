"""API Key model definitions."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean, func

from .base import Base

# Remove TYPE_CHECKING and ForwardRef imports as we'll use string literals
# if TYPE_CHECKING:
#     from .user import UserDB

class APIKeyDB(Base):
    """SQLAlchemy model for API keys."""
    __tablename__ = "api_keys"
    
    id: Mapped[str] = mapped_column(primary_key=True)
    user_email: Mapped[str] = mapped_column(ForeignKey("users.email", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Use string literal for forward reference
    user: Mapped["UserDB"] = relationship(
        "UserDB",
        back_populates="api_keys",
        lazy="joined"
    )

    def __repr__(self) -> str:
        return f"<APIKeyDB(id='{self.id}', user_email='{self.user_email}', provider='{self.provider}')>"

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