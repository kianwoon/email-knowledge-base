"""
Migration script to add the endpoint_url column to the jarvis_external_tokens table.

This migration:
1. Adds the endpoint_url column to the table with a default value
2. Then removes the default constraint once all rows have been updated
"""

from sqlalchemy import create_engine, Column, String, MetaData, Table, text
import logging
import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import settings from the app
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upgrade():
    """Add the endpoint_url column to the jarvis_external_tokens table."""
    logger.info("Starting migration to add endpoint_url column to jarvis_external_tokens table")
    
    # Use the database URL from settings
    DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI
    logger.info(f"Using database URL from settings")
    
    engine = create_engine(DATABASE_URL)
    meta = MetaData()
    meta.reflect(bind=engine)
    
    # Check if table exists
    if 'jarvis_external_tokens' not in meta.tables:
        logger.warning("jarvis_external_tokens table does not exist. Migration skipped.")
        return
    
    # Check if column already exists (idempotent migration)
    jarvis_tokens = meta.tables['jarvis_external_tokens']
    if 'endpoint_url' in jarvis_tokens.c:
        logger.info("endpoint_url column already exists. Migration skipped.")
        return
    
    # Use context manager to ensure connection is closed
    with engine.begin() as conn:
        # Add endpoint_url column with a default value
        # Initially we set a default value so existing rows get populated
        logger.info("Adding endpoint_url column with default value")
        conn.execute(text(
            "ALTER TABLE jarvis_external_tokens ADD COLUMN endpoint_url VARCHAR(512) DEFAULT 'https://api.example.com/v1/shared-knowledge/search' NOT NULL"
        ))
        
        # Now remove the default constraint for future rows
        logger.info("Removing default constraint from endpoint_url column")
        conn.execute(text(
            "ALTER TABLE jarvis_external_tokens ALTER COLUMN endpoint_url DROP DEFAULT"
        ))
    
    logger.info("Successfully added endpoint_url column to jarvis_external_tokens table")

def downgrade():
    """Remove the endpoint_url column from the jarvis_external_tokens table."""
    logger.info("Starting migration to remove endpoint_url column from jarvis_external_tokens table")
    
    # Use the database URL from settings
    DATABASE_URL = settings.SQLALCHEMY_DATABASE_URI
    
    engine = create_engine(DATABASE_URL)
    meta = MetaData()
    meta.reflect(bind=engine)
    
    # Check if table exists
    if 'jarvis_external_tokens' not in meta.tables:
        logger.warning("jarvis_external_tokens table does not exist. Downgrade skipped.")
        return
    
    # Check if column exists
    jarvis_tokens = meta.tables['jarvis_external_tokens']
    if 'endpoint_url' not in jarvis_tokens.c:
        logger.info("endpoint_url column does not exist. Downgrade skipped.")
        return
    
    # Drop the column
    with engine.begin() as conn:
        logger.info("Removing endpoint_url column")
        conn.execute(text(
            "ALTER TABLE jarvis_external_tokens DROP COLUMN endpoint_url"
        ))
    
    logger.info("Successfully removed endpoint_url column from jarvis_external_tokens table")

if __name__ == "__main__":
    # Run the migration
    logger.info("Running migration script to add endpoint_url column")
    upgrade() 