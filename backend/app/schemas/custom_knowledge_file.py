from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class AnalysisStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class CustomKnowledgeFileBase(BaseModel):
    filename: str
    content_type: str
    file_size: int
    qdrant_collection: str
    status: AnalysisStatus = AnalysisStatus.pending
    uploaded_at: Optional[datetime] = None

class CustomKnowledgeFileCreate(CustomKnowledgeFileBase):
    pass

class CustomKnowledgeFileInDB(CustomKnowledgeFileBase):
    id: int
    user_email: str
    class Config:
        orm_mode = True

class CustomKnowledgeFileResponse(CustomKnowledgeFileInDB):
    pass
