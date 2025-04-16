from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.dependencies.auth import get_current_active_user_or_token_owner
from app.models.user import UserDB
from app.models.custom_knowledge_file import CustomKnowledgeFile, AnalysisStatus
from app.db.crud_custom_knowledge_file import get_custom_knowledge_history_for_user
from app.utils.qdrant import upsert_to_qdrant
import uuid
from datetime import datetime

router = APIRouter()

class CustomKnowledgeUpload(BaseModel):
    filename: str
    content_type: str
    file_size: int
    content_base64: str

class CustomKnowledgeFileOut(BaseModel):
    id: int
    filename: str
    content_type: str
    file_size: int
    qdrant_collection: str
    status: str
    uploaded_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

@router.post("/upload-base64")
async def upload_custom_knowledge_base64(
    payload: CustomKnowledgeUpload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user_or_token_owner)
):
    from app.services.embedder import create_embedding
    try:
        # Check for duplicate file for this user
        existing = db.query(CustomKnowledgeFile).filter(
            CustomKnowledgeFile.user_email == current_user.email,
            CustomKnowledgeFile.filename == payload.filename,
            CustomKnowledgeFile.status == AnalysisStatus.completed
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="File with this name has already been processed.")
        # Generate embedding for the filename (or a placeholder text)
        # This ensures the vector matches EMBEDDING_DIMENSION from settings
        embedding_dim = getattr(__import__('app.config', fromlist=['settings']).settings, 'EMBEDDING_DIMENSION', 1536)
        try:
            embedding = await create_embedding(payload.filename)
            if len(embedding) != embedding_dim:
                raise ValueError(f"Embedding returned dimension {len(embedding)} but expected {embedding_dim}")
        except Exception as embed_err:
            # Fallback to zero vector if embedding fails
            import logging
            logging.getLogger(__name__).warning(f"Embedding failed: {embed_err}. Using zero vector.")
            embedding = [0.0] * embedding_dim
        # --- Determine user-specific collection name ---
        sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
        collection_name = f"{sanitized_email}_custom_knowledge"
        points = [{
            "id": str(uuid.uuid4()),
            "vector": embedding,
            "payload": {
                "filename": payload.filename,
                "user_id": current_user.email,
                "content_base64": payload.content_base64,
                "analysis_status": "pending",
            }
        }]
        upsert_to_qdrant(points, collection_name=collection_name)
        # --- Create DB record for history ---
        file_record = CustomKnowledgeFile(
            user_email=current_user.email,
            filename=payload.filename,
            content_type=payload.content_type,
            file_size=payload.file_size,
            qdrant_collection=collection_name,
            status=AnalysisStatus.completed,  # Set to completed if Qdrant upsert succeeds
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to upsert to Qdrant")

@router.get("/history", response_model=List[CustomKnowledgeFileOut])
def get_custom_knowledge_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user_or_token_owner)
):
    """
    Return all processed custom knowledge files for the current user.
    """
    records = get_custom_knowledge_history_for_user(db, current_user.email)
    return records
