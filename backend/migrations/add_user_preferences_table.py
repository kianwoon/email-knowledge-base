"""
Migration script to create the user_preferences table
"""
import logging
import os
import sys
from uuid import uuid4

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.config import settings
from app.db.session import engine

# Removed the circular imports
# from app.models.user_preference import UserPreferenceDB
# from app.db.base import Base

logger = logging.getLogger(__name__)

def run_migration():
    """Create the user_preferences table if it doesn't exist"""
    logger.info("Starting migration to create user_preferences table")
    
    # Get a new connection
    conn = engine.connect()
    
    # Get metadata
    from sqlalchemy import MetaData
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    # Check if the table already exists
    if 'user_preferences' in metadata.tables:
        logger.info("Table user_preferences already exists. Skipping table creation.")
        return
    
    # Create the user_preferences table
    logger.info("Creating user_preferences table")
    conn.execute(text("""
    CREATE TABLE user_preferences (
        id VARCHAR(255) PRIMARY KEY,
        user_email VARCHAR(255) NOT NULL REFERENCES users(email) ON DELETE CASCADE,
        preference_key VARCHAR(255) NOT NULL,
        preference_value VARCHAR(1024) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """))
    
    # Create indexes
    logger.info("Creating indexes for user_preferences table")
    conn.execute(text("""
    CREATE INDEX idx_user_preferences_user_email ON user_preferences(user_email)
    """))
    
    conn.execute(text("""
    CREATE INDEX idx_user_preferences_key ON user_preferences(preference_key)
    """))
    
    conn.execute(text("""
    CREATE UNIQUE INDEX idx_user_preferences_user_key ON user_preferences(user_email, preference_key)
    """))
    
    # Commit the transaction
    conn.commit()
    
    logger.info("Successfully created user_preferences table")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    run_migration() 