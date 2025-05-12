import logging
import uuid
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.models.user_settings import UserSettings

logger = logging.getLogger(__name__)

def get_user_settings(db: Session, user_id: uuid.UUID) -> Optional[UserSettings]:
    """
    Get user settings by user ID.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        UserSettings object if found, None otherwise
    """
    return db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

def create_user_settings(db: Session, user_id: uuid.UUID, settings: Dict[str, Any] = None) -> UserSettings:
    """
    Create new user settings.
    
    Args:
        db: Database session
        user_id: User UUID
        settings: Optional dict with settings values
        
    Returns:
        Created UserSettings object
    """
    if settings is None:
        settings = {}
        
    db_settings = UserSettings(
        user_id=user_id,
        max_rounds=settings.get('maxRounds', 10),
        default_model=settings.get('defaultModel', 'gpt-3.5-turbo')
    )
    
    db.add(db_settings)
    db.commit()
    db.refresh(db_settings)
    
    logger.info(f"Created settings for user {user_id}")
    return db_settings

def update_user_settings(db: Session, user_id: uuid.UUID, settings: Dict[str, Any]) -> Optional[UserSettings]:
    """
    Update user settings.
    
    Args:
        db: Database session
        user_id: User UUID
        settings: Dict with settings values to update
        
    Returns:
        Updated UserSettings object if found, None otherwise
    """
    db_settings = get_user_settings(db, user_id)
    
    if db_settings is None:
        # If settings don't exist, create them
        return create_user_settings(db, user_id, settings)
    
    # Update settings
    if 'maxRounds' in settings:
        db_settings.max_rounds = settings['maxRounds']
    if 'defaultModel' in settings:
        db_settings.default_model = settings['defaultModel']
    
    db.commit()
    db.refresh(db_settings)
    
    logger.info(f"Updated settings for user {user_id}")
    return db_settings

def get_or_create_user_settings(db: Session, user_id: uuid.UUID) -> UserSettings:
    """
    Get user settings or create if they don't exist.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        UserSettings object
    """
    db_settings = get_user_settings(db, user_id)
    
    if db_settings is None:
        db_settings = create_user_settings(db, user_id)
    
    return db_settings 