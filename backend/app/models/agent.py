import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from typing import TYPE_CHECKING

from app.db.base_class import Base

# Forward references for type hints
if TYPE_CHECKING:
    from app.models.user import UserDB

class Agent(Base):
    """
    SQLAlchemy model for storing agents that can be reused in AutoGen conversations.
    """
    __tablename__ = "agents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.email"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'assistant', 'researcher', 'coder', 'critic', 'custom'
    system_message = Column(Text, nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("UserDB", back_populates="agents")
    
    def to_dict(self):
        """
        Convert agent model to dictionary representation.
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.name,
            "type": self.type,
            "systemMessage": self.system_message,
            "isPublic": self.is_public,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        } 