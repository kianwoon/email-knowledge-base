"""
Migration script to remove the openai_api_key column from users table after data migration
This script should be run AFTER the migration to the api_keys table is complete and verified
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the Python path to access the app package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import settings from app.config
from app.config import settings
from app.crud import user_crud

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_migration():
    """Remove the openai_api_key column from users table after verification"""
    logger.info("Starting migration to remove openai_api_key column from users table")
    
    # First, verify that data has been migrated
    db = SessionLocal()
    try:
        # Check if the openai_api_key column exists
        has_column = user_crud.check_column_exists(db, 'users', 'openai_api_key')
        
        if not has_column:
            logger.info("Column openai_api_key does not exist in users table. Skipping migration.")
            return
        
        # Count users with API keys in the old column
        users_with_old_keys = db.execute(text(
            "SELECT COUNT(*) FROM users WHERE openai_api_key IS NOT NULL"
        )).scalar()
        
        # Check if api_keys table exists and count migrated keys
        api_keys_table_exists = db.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_keys')"
        )).scalar()
        
        if not api_keys_table_exists:
            logger.error("api_keys table does not exist. Cannot proceed with column removal.")
            logger.error("Please run add_api_keys_table.py first to create the table and migrate data.")
            return
        
        users_with_new_keys = db.execute(text(
            "SELECT COUNT(DISTINCT user_email) FROM api_keys WHERE provider = 'openai' AND is_active = TRUE"
        )).scalar()
        
        logger.info(f"Found {users_with_old_keys} users with keys in old column")
        logger.info(f"Found {users_with_new_keys} users with keys in new api_keys table")
        
        # Safety check - make sure we've migrated keys before removing the column
        if users_with_old_keys > 0 and users_with_new_keys == 0:
            logger.error("SAFETY CHECK FAILED: Found users with old API keys but none in the new table.")
            logger.error("This suggests that migration has not yet been performed.")
            logger.error("Please run add_api_keys_table.py first to migrate the data.")
            return
        
        # Let's allow the removal if no users have keys or if we have some new keys
        # In production, you might want a more strict check ensuring all keys are migrated
        
        # Prompt for confirmation before proceeding
        print("\n!!! WARNING !!!")
        print("This will permanently remove the openai_api_key column from the users table.")
        print(f"- {users_with_old_keys} users have keys in the old column")
        print(f"- {users_with_new_keys} users have keys in the new api_keys table")
        
        if users_with_old_keys > users_with_new_keys:
            print("\nWARNING: Some API keys may not have been migrated!")
            print(f"There are {users_with_old_keys - users_with_new_keys} more users with old keys than new keys.")
        
        confirmation = input("\nAre you ABSOLUTELY SURE you want to proceed? (type 'YES' to confirm): ")
        
        if confirmation != "YES":
            logger.info("Migration cancelled by user.")
            return
        
        # Remove the column
        logger.info("Removing openai_api_key column from users table")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users DROP COLUMN openai_api_key"))
            conn.commit()
        
        logger.info("Column openai_api_key successfully removed from users table")
        
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