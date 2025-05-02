from sqlalchemy.orm import Session
from typing import List

from ..models.jarvis_token import JarvisExternalToken


def get_valid_tokens_for_user(db: Session, user_id: int) -> List[JarvisExternalToken]:
    """Fetches all valid JarvisExternalToken records for a given user ID."""
    return (
        db.query(JarvisExternalToken)
        .filter(JarvisExternalToken.user_id == user_id, JarvisExternalToken.is_valid == True)
        .order_by(JarvisExternalToken.created_at.asc()) # Or however you want to order them
        .all()
    )

# Add other CRUD functions here later if needed (e.g., update validity) 