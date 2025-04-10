import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import logging

from ..models.api_key import APIKeyDB, APIKey, APIKeyCreate
from ..utils.security import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

def create_api_key(db: Session, user_email: str, api_key_in: APIKeyCreate) -> APIKeyDB:
    """Create a new API key for a user."""
    logger.debug(f"Creating new {api_key_in.provider} API key for user {user_email}")
    
    encrypted_key = encrypt_token(api_key_in.key)
    if not encrypted_key:
        logger.error(f"Failed to encrypt API key for user {user_email}")
        raise ValueError("Failed to encrypt API key")
    
    db_api_key = APIKeyDB(
        id=str(uuid.uuid4()),
        user_email=user_email,
        provider=api_key_in.provider,
        encrypted_key=encrypted_key
    )
    
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    logger.info(f"Successfully created {api_key_in.provider} API key for user {user_email}")
    return db_api_key

def get_api_key(db: Session, user_email: str, provider: str) -> Optional[APIKeyDB]:
    """Get a user's API key for a specific provider."""
    logger.debug(f"Getting {provider} API key for user {user_email}")
    
    statement = (
        select(APIKeyDB)
        .where(APIKeyDB.user_email == user_email, 
               APIKeyDB.provider == provider,
               APIKeyDB.is_active == True)
    )
    return db.execute(statement).scalar_one_or_none()

def get_all_api_keys(db: Session, user_email: str) -> List[APIKeyDB]:
    """Get all API keys for a user."""
    logger.debug(f"Getting all API keys for user {user_email}")
    
    statement = (
        select(APIKeyDB)
        .where(APIKeyDB.user_email == user_email)
    )
    return list(db.execute(statement).scalars().all())

def update_api_key(db: Session, user_email: str, provider: str, new_key: str) -> Optional[APIKeyDB]:
    """Update an existing API key."""
    logger.debug(f"Updating {provider} API key for user {user_email}")
    
    db_api_key = get_api_key(db, user_email, provider)
    if not db_api_key:
        logger.warning(f"No {provider} API key found for user {user_email}")
        return None
    
    encrypted_key = encrypt_token(new_key)
    if not encrypted_key:
        logger.error(f"Failed to encrypt API key for user {user_email}")
        raise ValueError("Failed to encrypt API key")
    
    db_api_key.encrypted_key = encrypted_key
    db_api_key.last_used = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_api_key)
    logger.info(f"Successfully updated {provider} API key for user {user_email}")
    return db_api_key

def delete_api_key(db: Session, user_email: str, provider: str) -> bool:
    """Delete (deactivate) an API key."""
    logger.debug(f"Deleting {provider} API key for user {user_email}")
    
    db_api_key = get_api_key(db, user_email, provider)
    if not db_api_key:
        logger.warning(f"No {provider} API key found for user {user_email}")
        return False
    
    db_api_key.is_active = False
    db.commit()
    logger.info(f"Successfully deactivated {provider} API key for user {user_email}")
    return True

def get_decrypted_api_key(db: Session, user_email: str, provider: str) -> Optional[str]:
    """Get the decrypted API key."""
    logger.debug(f"Getting decrypted {provider} API key for user {user_email}")
    
    db_api_key = get_api_key(db, user_email, provider)
    if not db_api_key:
        logger.warning(f"No {provider} API key found for user {user_email}")
        return None
    
    # Update last_used timestamp
    db_api_key.last_used = datetime.now(timezone.utc)
    db.commit()
    
    return decrypt_token(db_api_key.encrypted_key)

def migrate_legacy_openai_key(db: Session, user_email: str, encrypted_key: str) -> Optional[APIKeyDB]:
    """Migrate a user's legacy OpenAI API key to the new API keys table.
    This is a special function for migration purposes only."""
    logger.info(f"Migrating legacy OpenAI API key for user {user_email}")
    
    # Check if user already has an OpenAI API key in the new table
    existing_key = get_api_key(db, user_email, "openai")
    if existing_key:
        logger.info(f"User {user_email} already has an OpenAI API key in the new table, skipping migration")
        return existing_key
    
    try:
        # Decrypt the existing key
        decrypted_key = decrypt_token(encrypted_key)
        if not decrypted_key:
            logger.error(f"Could not decrypt legacy API key for user {user_email}")
            return None
        
        # Create new API key in the new table with the decrypted value
        api_key_in = APIKeyCreate(provider="openai", key=decrypted_key)
        return create_api_key(db, user_email, api_key_in)
    
    except Exception as e:
        logger.error(f"Failed to migrate API key for user {user_email}: {e}")
        return None 