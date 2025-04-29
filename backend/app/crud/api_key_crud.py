import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update, exists
import logging

from ..models.api_key import APIKeyDB, APIKey, APIKeyCreate
from ..utils.security import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

def create_api_key(db: Session, user_email: str, api_key_in: APIKeyCreate) -> APIKeyDB:
    """Create a new API key for a user, or reactivate/update an existing inactive one."""
    logger.debug(f"Attempting to create/update {api_key_in.provider} API key for user {user_email}")

    # --- MODIFICATION START: Check for existing inactive key --- 
    inactive_key_statement = (
        select(APIKeyDB)
        .where(APIKeyDB.user_email == user_email, 
               APIKeyDB.provider == api_key_in.provider,
               APIKeyDB.is_active == False)
        .limit(1) # Optimization: we only need one if it exists
    )
    result = db.execute(inactive_key_statement)
    existing_inactive_key = result.unique().scalar_one_or_none()

    if existing_inactive_key:
        logger.info(f"Found existing inactive {api_key_in.provider} key for {user_email}. Reactivating and updating.")
        encrypted_key = encrypt_token(api_key_in.key)
        if not encrypted_key:
            logger.error(f"Failed to encrypt API key for reactivation, user {user_email}")
            raise ValueError("Failed to encrypt API key for reactivation")
            
        existing_inactive_key.encrypted_key = encrypted_key
        existing_inactive_key.model_base_url = api_key_in.model_base_url
        existing_inactive_key.is_active = True
        existing_inactive_key.last_used = datetime.now(timezone.utc) # Update last_used on reactivation/update
        
        db.commit()
        db.refresh(existing_inactive_key)
        logger.info(f"Successfully reactivated and updated {api_key_in.provider} API key for user {user_email}")
        return existing_inactive_key
    # --- MODIFICATION END ---

    # --- Original creation logic if no inactive key found ---
    logger.info(f"No inactive {api_key_in.provider} key found for {user_email}. Creating a new record.")
    encrypted_key = encrypt_token(api_key_in.key)
    if not encrypted_key:
        logger.error(f"Failed to encrypt API key for user {user_email}")
        raise ValueError("Failed to encrypt API key")
    
    db_api_key = APIKeyDB(
        id=str(uuid.uuid4()),
        user_email=user_email,
        provider=api_key_in.provider,
        encrypted_key=encrypted_key,
        model_base_url=api_key_in.model_base_url,
        is_active=True # Ensure new keys are created as active
    )
    
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    logger.info(f"Successfully created new {api_key_in.provider} API key for user {user_email}")
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
    result = db.execute(statement)
    result = result.unique()
    return result.scalar_one_or_none()

def get_all_api_keys(db: Session, user_email: str) -> List[APIKeyDB]:
    """Get all API keys for a user."""
    logger.debug(f"Getting all API keys for user {user_email}")
    
    statement = (
        select(APIKeyDB)
        .where(APIKeyDB.user_email == user_email)
    )
    result = db.execute(statement)
    result = result.unique()
    return list(result.scalars().all())

def update_api_key(db: Session, user_email: str, provider: str, new_key: Optional[str] = None, model_base_url: Optional[str] = None) -> Optional[APIKeyDB]:
    """Update an existing API key."""
    logger.debug(f"Updating {provider} API key for user {user_email}")
    
    db_api_key = get_api_key(db, user_email, provider)
    if not db_api_key:
        logger.warning(f"No {provider} API key found for user {user_email}")
        return None
    
    updated = False
    # Update key if provided
    if new_key:
        encrypted_key = encrypt_token(new_key)
        if not encrypted_key:
            logger.error(f"Failed to encrypt API key for user {user_email}")
            raise ValueError("Failed to encrypt API key")
        db_api_key.encrypted_key = encrypted_key
        updated = True
        
    # Update model_base_url unconditionally
    # Check if the provided value is different from the existing one
    if model_base_url != db_api_key.model_base_url:
        db_api_key.model_base_url = model_base_url # Assign the new value (could be None or "")
        updated = True

    if updated:
        db_api_key.last_used = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_api_key)
        logger.info(f"Successfully updated {provider} API key for user {user_email}")
    else:
        logger.info(f"No update necessary for {provider} API key for user {user_email}")
        
    return db_api_key

def delete_api_key(db: Session, user_email: str, provider: str) -> bool:
    """Delete (deactivate) an API key. Handles potential duplicates by deactivating all matching keys."""
    logger.debug(f"Deactivating {provider} API key(s) for user {user_email}")

    statement = (
        select(APIKeyDB)
        .where(APIKeyDB.user_email == user_email, 
               APIKeyDB.provider == provider,
               APIKeyDB.is_active == True)
    )
    results = db.execute(statement)
    keys_to_deactivate = list(results.unique().scalars().all())

    if not keys_to_deactivate:
        logger.warning(f"No active {provider} API key found for user {user_email} to deactivate")
        return False
    
    deactivated_count = 0
    for db_api_key in keys_to_deactivate:
        db_api_key.is_active = False
        deactivated_count += 1
        
    if deactivated_count > 0:
        db.commit()
        logger.info(f"Successfully deactivated {deactivated_count} {provider} API key(s) for user {user_email}")
        return True
    else:
        # Should not happen if keys_to_deactivate was not empty, but included for safety
        return False

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