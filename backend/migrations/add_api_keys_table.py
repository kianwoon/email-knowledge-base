"""
Migration script to create the api_keys table
"""
import os
import sys
import logging
import uuid
from sqlalchemy import Column, String, create_engine, text, MetaData, Table, ForeignKey, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the Python path to access the app package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import settings from app.config
from app.config import settings
from app.crud import user_crud, api_key_crud
from app.models.api_key import APIKeyCreate

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_migration():
    """Create the api_keys table if it doesn't exist and migrate existing keys"""
    logger.info("Starting migration to create api_keys table")
    
    # Check if the table already exists
    with engine.connect() as conn:
        metadata = MetaData()
        metadata.reflect(bind=engine)
        
        if 'api_keys' in metadata.tables:
            logger.info("Table api_keys already exists. Skipping table creation.")
        else:
            # Create the api_keys table
            logger.info("Creating api_keys table")
            conn.execute(text("""
                CREATE TABLE api_keys (
                    id VARCHAR(36) PRIMARY KEY,
                    user_email VARCHAR NOT NULL REFERENCES users(email) ON DELETE CASCADE,
                    provider VARCHAR NOT NULL,
                    encrypted_key VARCHAR(1024) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN DEFAULT TRUE,
                    
                    CONSTRAINT unique_user_provider UNIQUE (user_email, provider)
                )
            """))
            
            # Create an index on user_email
            conn.execute(text("""
                CREATE INDEX idx_api_keys_user_email ON api_keys(user_email)
            """))
            
            # Create an index on provider
            conn.execute(text("""
                CREATE INDEX idx_api_keys_provider ON api_keys(provider)
            """))
            
            conn.commit()
            logger.info("api_keys table created successfully")
    
    # Migrate existing OpenAI API keys from users table
    logger.info("Beginning migration of existing API keys")
    
    db = SessionLocal()
    try:
        # Check if the openai_api_key column exists in users table
        has_column = user_crud.check_column_exists(db, 'users', 'openai_api_key')
        
        if has_column:
            logger.info("openai_api_key column exists, proceeding with data migration")
            
            # Get all users with existing API keys
            result = db.execute(text(
                "SELECT email, openai_api_key FROM users WHERE openai_api_key IS NOT NULL"
            ))
            
            migrated_count = 0
            failed_count = 0
            
            for row in result:
                user_email = row[0]
                encrypted_key = row[1]
                
                try:
                    # Check if user already has a key in the new table
                    existing_key = db.execute(text(
                        "SELECT id FROM api_keys WHERE user_email = :email AND provider = 'openai' AND is_active = TRUE"
                    ), {"email": user_email}).fetchone()
                    
                    if existing_key:
                        logger.info(f"User {user_email} already has an API key in the new table, skipping")
                        continue
                    
                    # Import directly to avoid circular imports
                    from app.utils.security import decrypt_token
                    
                    # Decrypt the existing key
                    decrypted_key = decrypt_token(encrypted_key)
                    if not decrypted_key:
                        logger.warning(f"Could not decrypt API key for user {user_email}, skipping")
                        failed_count += 1
                        continue
                    
                    # Create a new entry in the api_keys table
                    # Manually encrypt and insert to avoid circular imports
                    from app.utils.security import encrypt_token
                    new_encrypted_key = encrypt_token(decrypted_key)
                    
                    if not new_encrypted_key:
                        logger.warning(f"Failed to re-encrypt API key for user {user_email}, skipping")
                        failed_count += 1
                        continue
                    
                    api_key_id = str(uuid.uuid4())
                    db.execute(text(
                        """
                        INSERT INTO api_keys (id, user_email, provider, encrypted_key, created_at, is_active)
                        VALUES (:id, :email, 'openai', :key, CURRENT_TIMESTAMP, TRUE)
                        """
                    ), {"id": api_key_id, "email": user_email, "key": new_encrypted_key})
                    
                    db.commit()
                    logger.info(f"Successfully migrated API key for user {user_email}")
                    migrated_count += 1
                    
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to migrate API key for user {user_email}: {e}")
                    failed_count += 1
            
            logger.info(f"API key migration complete. Migrated: {migrated_count}, Failed: {failed_count}")
        else:
            logger.info("openai_api_key column does not exist in users table, no data to migrate")
    
    finally:
        db.close()
    
    logger.info("Migration completed successfully")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}", exc_info=True)
        sys.exit(1)
    sys.exit(0) 