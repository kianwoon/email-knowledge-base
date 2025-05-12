from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as SQLAlchemyUUID
import uuid

from app.db.base_class import Base

class UserLLMConfig(Base):
    """Database model for user LLM configurations."""
    __tablename__ = "user_llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    default_model_id = Column(String, nullable=True)
    preferences = Column(JSON, nullable=True)
    
    # Optionally add relationship to User if needed
    # user = relationship("User", back_populates="llm_config") 