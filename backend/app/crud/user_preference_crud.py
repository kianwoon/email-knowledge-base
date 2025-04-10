from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import logging
import uuid

from sqlalchemy.orm import Session
from app.models.user_preference import UserPreferenceDB, UserPreferenceCreate, UserPreference

logger = logging.getLogger(__name__)

def create_user_preference(db: Session, user_email: str, preference_key: str, preference_value: str) -> UserPreferenceDB:
    """
    Create a new user preference or update if it already exists
    """
    logger.debug(f"Creating/updating user preference {preference_key} for user {user_email}")
    
    # Check if preference already exists
    db_preference = get_user_preference(db, user_email, preference_key)
    
    if db_preference:
        # Update existing preference
        db_preference.preference_value = preference_value
        db_preference.updated_at = datetime.now(timezone.utc)
    else:
        # Create new preference
        db_preference = UserPreferenceDB(
            id=str(uuid.uuid4()),
            user_email=user_email,
            preference_key=preference_key,
            preference_value=preference_value
        )
        db.add(db_preference)
    
    db.commit()
    db.refresh(db_preference)
    logger.info(f"Successfully created/updated user preference {preference_key} for user {user_email}")
    return db_preference

def get_user_preference(db: Session, user_email: str, preference_key: str) -> Optional[UserPreferenceDB]:
    """
    Get a specific user preference by key
    """
    return db.query(UserPreferenceDB).filter(
        UserPreferenceDB.user_email == user_email,
        UserPreferenceDB.preference_key == preference_key
    ).first()

def get_user_preferences(db: Session, user_email: str) -> List[UserPreferenceDB]:
    """
    Get all preferences for a user
    """
    return db.query(UserPreferenceDB).filter(UserPreferenceDB.user_email == user_email).all()

def get_user_preferences_dict(db: Session, user_email: str) -> Dict[str, str]:
    """
    Get all preferences for a user as a dictionary
    """
    preferences = get_user_preferences(db, user_email)
    return {pref.preference_key: pref.preference_value for pref in preferences}

def delete_user_preference(db: Session, user_email: str, preference_key: str) -> bool:
    """
    Delete a user preference
    """
    db_preference = get_user_preference(db, user_email, preference_key)
    if not db_preference:
        return False
    
    db.delete(db_preference)
    db.commit()
    return True

# Specific preference helpers

def get_default_llm_model(db: Session, user_email: str) -> Optional[str]:
    """
    Get the user's default LLM model
    """
    preference = get_user_preference(db, user_email, "default_llm_model")
    return preference.preference_value if preference else None

def set_default_llm_model(db: Session, user_email: str, model_id: str) -> UserPreferenceDB:
    """
    Set the user's default LLM model
    """
    return create_user_preference(db, user_email, "default_llm_model", model_id) 