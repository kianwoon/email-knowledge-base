from sqlalchemy.orm import Session
from app.models.custom_knowledge_file import CustomKnowledgeFile
import logging

logger = logging.getLogger(__name__)

def update_custom_knowledge_file_status(db: Session, file_id: int, status: str):
    """
    Update the status field of a CustomKnowledgeFile record.
    """
    file_record = db.query(CustomKnowledgeFile).filter(CustomKnowledgeFile.id == file_id).first()
    if not file_record:
        logger.error(f"CustomKnowledgeFile with id {file_id} not found for status update.")
        return
    file_record.status = status
    db.commit()
    logger.info(f"Updated CustomKnowledgeFile id={file_id} status to '{status}'")

def get_custom_knowledge_history_for_user(db: Session, user_email: str):
    """
    Return all CustomKnowledgeFile records for the given user, ordered by uploaded_at descending.
    """
    return (
        db.query(CustomKnowledgeFile)
        .filter(CustomKnowledgeFile.user_email == user_email)
        .order_by(CustomKnowledgeFile.uploaded_at.desc())
        .all()
    )
