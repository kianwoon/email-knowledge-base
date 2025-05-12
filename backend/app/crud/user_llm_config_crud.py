import logging
from sqlalchemy.orm import Session
from typing import Optional
from fastapi import HTTPException

from app.db.models.user_llm_config import UserLLMConfig
from app.models.llm_config import UserLLMConfigCreate, UserLLMConfigUpdate

logger = logging.getLogger(__name__)

def get_user_llm_config(db: Session, user_id: str) -> Optional[UserLLMConfig]:
    """
    Get a user's LLM configuration.
    
    Args:
        db: Database session
        user_id: ID of the user
        
    Returns:
        UserLLMConfig if found, None otherwise
    """
    # Convert UUID to string if it's not already a string
    user_id_str = str(user_id) if user_id else None
    if not user_id_str:
        logger.warning("Attempted to get user LLM config with empty user_id")
        return None
        
    return db.query(UserLLMConfig).filter(UserLLMConfig.user_id == user_id_str).first()

def create_user_llm_config(db: Session, config: UserLLMConfigCreate) -> UserLLMConfig:
    """
    Create a new user LLM configuration.
    
    Args:
        db: Database session
        config: Configuration data
        
    Returns:
        Created UserLLMConfig
    """
    db_config = UserLLMConfig(
        user_id=config.user_id,
        default_model_id=config.default_model_id,
        preferences=config.preferences
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

def update_user_llm_config(db: Session, user_id: str, config: UserLLMConfigUpdate) -> UserLLMConfig:
    """
    Update a user's LLM configuration.
    
    Args:
        db: Database session
        user_id: ID of the user
        config: Updated configuration data
        
    Returns:
        Updated UserLLMConfig
    """
    db_config = get_user_llm_config(db, user_id)
    if not db_config:
        raise HTTPException(status_code=404, detail="User LLM configuration not found")
    
    # Update fields if provided
    if config.default_model_id is not None:
        db_config.default_model_id = config.default_model_id
    if config.preferences is not None:
        db_config.preferences = config.preferences
    
    db.commit()
    db.refresh(db_config)
    return db_config

def delete_user_llm_config(db: Session, user_id: str) -> bool:
    """
    Delete a user's LLM configuration.
    
    Args:
        db: Database session
        user_id: ID of the user
        
    Returns:
        True if deleted, False if not found
    """
    db_config = get_user_llm_config(db, user_id)
    if not db_config:
        return False
    
    db.delete(db_config)
    db.commit()
    return True 