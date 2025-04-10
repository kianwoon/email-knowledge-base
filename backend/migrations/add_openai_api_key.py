"""
Migration script to add openai_api_key column to users table
"""
import os
import sys
import logging
from sqlalchemy import Column, String, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the Python path to access the app package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import settings from app.config
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_migration():
    """Add openai_api_key column to the users table if it doesn't exist"""
    logger.info("Starting migration to add openai_api_key column to users table")
    
    # Check if the column already exists
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name='users' AND column_name='openai_api_key')"
        ))
        column_exists = result.scalar()
        
        if column_exists:
            logger.info("Column openai_api_key already exists in users table. Skipping migration.")
            return
        
        # Add the column if it doesn't exist
        logger.info("Adding openai_api_key column to users table")
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN openai_api_key VARCHAR(1024)"
        ))
        conn.commit()
        
    logger.info("Migration completed successfully")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}", exc_info=True)
        sys.exit(1)
    sys.exit(0) 