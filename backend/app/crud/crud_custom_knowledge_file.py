from sqlalchemy.orm import Session
from app.models.custom_knowledge_file import CustomKnowledgeFile, AnalysisStatus
from app.schemas.custom_knowledge_file import CustomKnowledgeFileCreate
from typing import List, Optional
from datetime import datetime, timezone

def create_custom_knowledge_file(db: Session, *, user_email: str, file_in: CustomKnowledgeFileCreate) -> CustomKnowledgeFile:
    db_file = CustomKnowledgeFile(
        user_email=user_email,
        filename=file_in.filename,
        content_type=file_in.content_type,
        file_size=file_in.file_size,
        qdrant_collection=file_in.qdrant_collection,
        status=file_in.status,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def get_user_custom_knowledge_files(db: Session, user_email: str, skip: int = 0, limit: int = 100) -> List[CustomKnowledgeFile]:
    return db.query(CustomKnowledgeFile).filter(CustomKnowledgeFile.user_email == user_email).order_by(CustomKnowledgeFile.uploaded_at.desc()).offset(skip).limit(limit).all()
