import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base

class UserSettings(Base):
    """
    SQLAlchemy model for storing user settings for the application.
    """
    __tablename__ = "user_settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.email"), nullable=False, unique=True)
    max_rounds = Column(Integer, default=10)
    default_model = Column(String, default="gpt-3.5-turbo")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("UserDB", back_populates="settings")
    
    def to_dict(self):
        """
        Convert user settings model to dictionary representation.
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "maxRounds": self.max_rounds,
            "defaultModel": self.default_model,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        } 