from sqlalchemy.orm import Session
from sqlalchemy import select, update
from typing import Optional
from datetime import datetime, timezone

# Import BOTH the Pydantic User and the SQLAlchemy UserDB models
from ..models.user import User, UserDB 

def get_user(db: Session, email: str) -> Optional[UserDB]:
    """
    Fetches a single user by their email address from the database.

    Args:
        db: The database session.
        email: The email address of the user to fetch.

    Returns:
        The UserDB object if found, otherwise None.
    """
    # Use the SQLAlchemy model (UserDB) in the query
    statement = select(UserDB).where(UserDB.email == email)
    user_db = db.execute(statement).scalar_one_or_none()
    return user_db

# NEW function to create or update user in the database
def create_or_update_user(db: Session, user_data: User) -> UserDB:
    """Creates a new user or updates an existing one based on email.

    Args:
        db: The database session.
        user_data: The Pydantic User model containing user info.

    Returns:
        The created or updated UserDB object.
    """
    existing_user = get_user(db, email=user_data.email)
    
    if existing_user:
        # Update existing user
        update_data = user_data.model_dump(exclude_unset=True, exclude={'email', 'created_at'}) # Exclude PK and creation time
        # Ensure last_login is updated
        update_data['last_login'] = datetime.now(timezone.utc)
        
        statement = (
            update(UserDB)
            .where(UserDB.email == user_data.email)
            .values(**update_data)
            .returning(UserDB) # Return the updated row
        )
        updated_user = db.execute(statement).scalar_one()
        db.commit()
        return updated_user
    else:
        # Create new user
        # Map Pydantic User fields to UserDB columns
        db_user = UserDB(
            email=user_data.email,
            id=user_data.id, # Store MS Graph ID
            display_name=user_data.display_name,
            # created_at has server_default
            last_login=datetime.now(timezone.utc),
            is_active=user_data.is_active,
            preferences=user_data.preferences,
            photo_url=user_data.photo_url,
            organization=user_data.organization
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

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