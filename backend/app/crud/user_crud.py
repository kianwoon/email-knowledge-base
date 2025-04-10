import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session, load_only # Import load_only
from sqlalchemy import select, exists, update, text # Import exists, update, and text
import sqlalchemy.exc

# Import BOTH the Pydantic User and the SQLAlchemy UserDB models
from ..models.user import User, UserDB 

logger = logging.getLogger(__name__)

def get_user_full_instance(db: Session, email: str) -> UserDB | None:
    """Fetches the UserDB instance WITHOUT the refresh token field initially."""
    try:
        # If column doesn't exist, explicitly load all columns EXCEPT ms_refresh_token
        statement = (
            select(UserDB)
            .where(UserDB.email == email)
            .options(load_only(
                UserDB.email, 
                UserDB.id, 
                UserDB.display_name, 
                UserDB.created_at, 
                UserDB.last_login, 
                UserDB.is_active, 
                UserDB.json_preferences, 
                UserDB.photo_url, 
                UserDB.organization,
                UserDB.last_kb_task_id
                # Explicitly omitting UserDB.ms_refresh_token
            ))
        )
        
        # Use unique() to handle the joined eager loads
        result = db.execute(statement)
        result = result.unique()
        user_db = result.scalar_one_or_none()
        return user_db
    except Exception as e:
        # Catch potential errors during the fetch itself (like the type error)
        logger.error(f"Error fetching full user instance for {email}: {e}", exc_info=True)
        # Re-raise the exception to be handled by the caller (e.g., auth route)
        raise e

def check_column_exists(db: Session, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        result = db.execute(text(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            f"WHERE table_name='{table_name}' AND column_name='{column_name}')"
        ))
        return result.scalar()
    except sqlalchemy.exc.ProgrammingError:
        # If we can't even run this query (e.g., SQLite doesn't have information_schema)
        # we'll just try accessing the table and catch any errors
        try:
            db.execute(text(f"SELECT {column_name} FROM {table_name} LIMIT 1"))
            return True
        except Exception:
            return False
    except Exception as e:
        logger.error(f"Error checking if column {column_name} exists in table {table_name}: {e}")
        return False

def does_user_exist(db: Session, email: str) -> bool:
    """Checks if a user exists by email using an efficient EXISTS query."""
    try:
        statement = select(exists().where(UserDB.email == email))
        return db.execute(statement).scalar()
    except Exception as e:
        logger.error(f"Error checking user existence for {email}: {e}", exc_info=True)
        # Treat check failure as potentially non-existent or raise
        raise e

def create_or_update_user(db: Session, user_data: User) -> UserDB:
    """
    Retrieves an existing user OR creates a new UserDB instance.
    Updates attributes for existing users.
    Does NOT commit the transaction; the caller is responsible for setting
    the refresh token (if applicable) and committing.
    """
    try:
        user_exists = does_user_exist(db, email=user_data.email)

        if user_exists:
            # Fetch the full ORM instance to update. If this fails, the error originates here.
            logger.debug(f"User {user_data.email} exists. Fetching full instance...")
            db_user = get_user_full_instance(db, email=user_data.email)
            if not db_user:
                 # This case indicates inconsistency or fetch error
                 logger.error(f"User {user_data.email} existence check mismatch or fetch failed.")
                 raise Exception(f"User {user_data.email} existence check mismatch or fetch failed.")

            # Update attributes on the existing instance (in memory)
            logger.debug(f"Updating attributes for existing user {user_data.email}")
            db_user.id = user_data.id
            db_user.display_name = user_data.display_name
            db_user.last_login = user_data.last_login
            db_user.photo_url = user_data.photo_url
            db_user.organization = user_data.organization
                
            # The instance is now 'dirty' but not committed.
            return db_user # Return the persistent instance with pending changes

        else:
            # Create a new transient UserDB instance (not yet saved)
            logger.debug(f"User {user_data.email} does not exist. Creating new instance.")
            
            # Prepare user attributes
            user_attrs = {
                'email': user_data.email,
                'id': user_data.id,
                'display_name': user_data.display_name,
                'last_login': user_data.last_login,
                'photo_url': user_data.photo_url,
                'organization': user_data.organization,
                # ms_refresh_token will be set by the caller before commit
            }
                
            db_user = UserDB(**user_attrs)
            return db_user # Return the transient instance
            
    except Exception as e:
        logger.error(f"Error in create_or_update_user for {user_data.email}: {e}", exc_info=True)
        # Re-raise the exception to be handled by the caller (e.g., auth route)
        raise e

# Function to update specific fields if needed (example)
def update_user_preferences(db: Session, user_email: str, preferences: Dict[str, Any]):
    try:
        statement = (
            update(UserDB)
            .where(UserDB.email == user_email)
            .values(json_preferences=preferences)
        )
        result = db.execute(statement)
        if result.rowcount == 0:
            logger.warning(f"Attempted to update preferences for non-existent user: {user_email}")
            return False
        db.commit()
        logger.info(f"Updated preferences for user {user_email}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating preferences for {user_email}: {e}", exc_info=True)
        raise e

# Add other user CRUD functions here as needed (e.g., create_user, update_user)
# These functions would typically take Pydantic models as input (e.g., UserCreate)
# and return the created/updated UserDB object.
# Example:
# def create_user(db: Session, user_in: UserCreate) -> UserDB:
#     db_user = UserDB(
#         email=user_in.email,
#         display_name=user_in.display_name,
#         # ... set other fields, handle password hashing if needed ...
#     )
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#     return db_user 