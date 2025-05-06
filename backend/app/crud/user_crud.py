import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session, load_only # Import load_only
from sqlalchemy import select, exists, update, text # Import exists, update, and text
import sqlalchemy.exc
from datetime import datetime, timezone # Ensure datetime is imported
import uuid
from sqlalchemy import func
from fastapi import HTTPException

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

def get_user_with_refresh_token(db: Session, email: str) -> UserDB | None:
    """Fetches the UserDB instance INCLUDING the ms_refresh_token field."""
    try:
        # Fetch the user instance directly by email
        statement = select(UserDB).where(UserDB.email == email)
        result = db.execute(statement)
        result = result.unique()
        user_db = result.scalar_one_or_none()
        # The ms_refresh_token field is loaded by default unless excluded
        if user_db:
            logger.debug(f"Fetched user {email} with refresh token field included.")
        else:
            logger.debug(f"User {email} not found when attempting to fetch with refresh token.")
        return user_db
    except Exception as e:
        logger.error(f"Error fetching user {email} with refresh token: {e}", exc_info=True)
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

def update_user_refresh_token(db: Session, user_email: str, encrypted_refresh_token: str | None) -> bool:
    """Updates the encrypted Microsoft refresh token for a user.
    
    Returns:
        bool: True if update was successful (at least one row affected), False otherwise.
    Raises:
        Exception: If a database error occurs.
    """
    try:
        statement = (
            update(UserDB)
            .where(UserDB.email == user_email)
            .values(ms_refresh_token=encrypted_refresh_token) # Update the specific field
        )
        result = db.execute(statement)
        if result.rowcount == 0:
            logger.warning(f"Attempted to update refresh token for non-existent user: {user_email}")
            # Return False, but don't raise an error here, the caller might handle it.
            return False 
        db.commit() # Commit the change
        logger.info(f"Updated refresh token for user {user_email}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating refresh token for {user_email}: {e}", exc_info=True)
        # Re-raise the exception to let the caller handle the database failure
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

# +++ NEW Function to update all MS tokens +++
def update_user_ms_tokens(db: Session, user_email: str, access_token: str, expiry: datetime, refresh_token: Optional[str] = None) -> bool:
    """Updates the Microsoft access token, expiry, and optionally the refresh token.
    
    Args:
        db: The database session.
        user_email: The email of the user to update.
        access_token: The new Microsoft access token.
        expiry: The expiry datetime for the new access token.
        refresh_token: The new refresh token, if provided by Microsoft.

    Returns:
        bool: True if update was successful, False if user not found.
    Raises:
        Exception: If a database error occurs.
    """
    try:
        values_to_update = {
            "ms_access_token": access_token,
            "ms_token_expiry": expiry,
        }
        # Only include refresh token in the update if a new one was provided
        if refresh_token is not None:
            values_to_update["ms_refresh_token"] = refresh_token

        statement = (
            update(UserDB)
            .where(UserDB.email == user_email)
            .values(**values_to_update) # Use dictionary unpacking
        )
        result = db.execute(statement)
        if result.rowcount == 0:
            logger.warning(f"Attempted to update MS tokens for non-existent user: {user_email}")
            return False
        db.commit() # Commit the change
        logger.info(f"Updated MS tokens for user {user_email}. New expiry: {expiry}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating MS tokens for {user_email}: {e}", exc_info=True)
        raise e

# +++ NEW Function to get user by ID +++
def get_user_by_id(db: Session, user_id: uuid.UUID) -> UserDB | None:
    """Fetches the UserDB instance by its UUID id."""
    try:
        # Fetch the user instance directly by UUID id
        statement = select(UserDB).where(UserDB.id == user_id)
        result = db.execute(statement)
        # Add .unique() to handle potential joined eager loads
        result = result.unique() 
        user_db = result.scalar_one_or_none()
        if user_db:
            logger.debug(f"Fetched user {user_id} by ID.")
        else:
            logger.debug(f"User {user_id} not found when fetching by ID.")
        return user_db
    except Exception as e:
        logger.error(f"Error fetching user by ID {user_id}: {e}", exc_info=True)
        raise e
# --- End NEW Function ---

def get_or_create_user_from_ms_graph(
    db: Session, 
    email: str, 
    ms_id: str, 
    display_name: str,
    organization: Optional[str],
    photo_url: Optional[str]
) -> UserDB:
    """
    Finds a user by email. If found, updates details. 
    If not found, creates a new user with a generated internal UUID 
    and stores the Microsoft Graph ID.
    Commits the changes and returns the UserDB object.
    """
    try:
        logger.debug(f"Attempting to get/create user from MS Graph info for email: {email}")
        
        # Try to fetch the user by email (case-insensitive if DB supports it)
        user = db.query(UserDB).filter(func.lower(UserDB.email) == email.lower()).first()

        now = datetime.now(timezone.utc)

        if user:
            # User exists, update details
            logger.info(f"Found existing user: {email}. Updating details.")
            user.display_name = display_name
            user.organization = organization
            user.photo_url = photo_url
            user.last_login = now
            # Add logic here to update microsoft_id if you add that field to UserDB
            # user.microsoft_id = ms_id 
            
        else:
            # User does not exist, create new one
            logger.info(f"Creating new user: {email}")
            new_internal_uuid = uuid.uuid4() # Generate internal UUID
            user = UserDB(
                email=email,
                id=new_internal_uuid, # Assign internal UUID
                # microsoft_id=ms_id, # Store MS Graph ID if field exists
                display_name=display_name,
                organization=organization,
                photo_url=photo_url,
                created_at=now,
                last_login=now,
                is_active=True,
                json_preferences={} # Initialize preferences
            )
            db.add(user)
            
        # Commit changes (for both update and create)
        db.commit()
        db.refresh(user) # Ensure the session has the latest state
        logger.info(f"User {email} successfully processed (created or updated). Internal ID: {user.id}")
        return user

    except sqlalchemy.exc.IntegrityError as ie:
        db.rollback()
        logger.error(f"Database integrity error processing user {email}: {ie}", exc_info=True)
        # This might happen if email constraint fails despite initial check (rare race condition)
        raise HTTPException(status_code=500, detail="Database error processing user.") from ie
    except Exception as e:
        db.rollback()
        logger.error(f"Error in get_or_create_user_from_ms_graph for {email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error processing user information.") from e

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