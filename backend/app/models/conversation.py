import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base

class AutogenConversation(Base):
    """
    SQLAlchemy model for storing AutoGen conversations.
    """
    __tablename__ = "autogen_conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.email"), nullable=False)
    title = Column(String, nullable=False)
    max_rounds = Column(Integer, default=10)
    agent_configs = Column(JSONB, nullable=True)  # Stores agent configuration used in this conversation
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("UserDB", back_populates="autogen_conversations")
    messages = relationship("AutogenMessage", back_populates="conversation", cascade="all, delete-orphan")
    
    def to_dict(self):
        """
        Convert conversation model to dictionary representation.
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "maxRounds": self.max_rounds,
            "agentsConfig": self.agent_configs,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "lastAccessedAt": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "messages": [message.to_dict() for message in self.messages]
        }


class AutogenMessage(Base):
    """
    SQLAlchemy model for storing AutoGen conversation messages.
    """
    __tablename__ = "autogen_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("autogen_conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    agent_name = Column(String, nullable=True)  # Name of the agent that generated this message
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    sequence_number = Column(Integer, nullable=False)  # Order of messages in conversation
    
    # Relationships
    conversation = relationship("AutogenConversation", back_populates="messages")
    
    def to_dict(self):
        """
        Convert message model to dictionary representation.
        """
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "role": self.role,
            "agentName": self.agent_name,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "sequence_number": self.sequence_number
        } 