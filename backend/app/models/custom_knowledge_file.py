from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base
from app.models.user import UserDB
import enum

class AnalysisStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class CustomKnowledgeFile(Base):
    __tablename__ = "custom_knowledge_files"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, ForeignKey("users.email"), index=True, nullable=False)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    qdrant_collection = Column(String, nullable=False)
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.pending, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("UserDB", back_populates="custom_knowledge_files")

# Add back_populates to UserDB if not present:
# custom_knowledge_files = relationship("CustomKnowledgeFile", back_populates="user")
