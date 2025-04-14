import uuid
import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete

from app.models.azure_blob import AzureBlobConnection
from app.schemas.azure_blob import AzureBlobConnectionCreate, AzureBlobConnectionUpdate
from app.utils.security import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

def create_connection(
    db: Session, *, obj_in: AzureBlobConnectionCreate, user_id: uuid.UUID
) -> AzureBlobConnection:
    """Create a new Azure Blob connection, encrypting credentials."""
    encrypted_credentials = encrypt_token(obj_in.credentials)
    if not encrypted_credentials:
        logger.error(f"Failed to encrypt credentials for user {user_id} during connection creation.")
        # Decide on error handling: raise exception or return None/handle in service layer
        raise ValueError("Failed to encrypt credentials")

    db_obj = AzureBlobConnection(
        **obj_in.model_dump(exclude={"credentials"}),
        user_id=user_id,
        credentials=encrypted_credentials
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_connection(
    db: Session, *, connection_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[AzureBlobConnection]:
    """Get a specific connection by ID for a specific user.
       Credentials remain encrypted.
    """
    statement = select(AzureBlobConnection).where(
        AzureBlobConnection.id == connection_id,
        AzureBlobConnection.user_id == user_id
    )
    result = db.execute(statement)
    return result.scalars().first()

def get_connection_with_decrypted_credentials(
    db: Session, *, connection_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[AzureBlobConnection]:
    """Get a connection and attempt to decrypt its credentials.
       Returns the object with credentials decrypted, or None if decryption fails.
       Be careful where this is used!
    """
    db_obj = get_connection(db=db, connection_id=connection_id, user_id=user_id)
    if db_obj:
        decrypted_creds = decrypt_token(db_obj.credentials)
        if decrypted_creds is None:
            logger.error(
                f"Failed to decrypt credentials for connection {db_obj.id} "
                f"belonging to user {user_id}. Stored credential might be invalid."
            )
            # Return the object but with credentials set to None or raise error?
            # For now, let's return None to indicate failure to get usable credentials.
            return None
        db_obj.credentials = decrypted_creds
    return db_obj

def get_connections_by_user(
    db: Session, *, user_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> List[AzureBlobConnection]:
    """Get all connections for a specific user. Credentials remain encrypted."""
    statement = (
        select(AzureBlobConnection)
        .where(AzureBlobConnection.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .order_by(AzureBlobConnection.name)
    )
    result = db.execute(statement)
    return list(result.scalars().all())

def update_connection(
    db: Session, *, db_obj: AzureBlobConnection, obj_in: AzureBlobConnectionUpdate
) -> AzureBlobConnection:
    """Update an Azure Blob connection, encrypting credentials if provided."""
    update_data = obj_in.model_dump(exclude_unset=True)

    if "credentials" in update_data:
        new_credentials = update_data.pop("credentials") # Remove from dict before iteration
        if new_credentials:
            encrypted_credentials = encrypt_token(new_credentials)
            if not encrypted_credentials:
                logger.error(f"Failed to encrypt new credentials for connection {db_obj.id}")
                raise ValueError("Failed to encrypt new credentials during update")
            setattr(db_obj, "credentials", encrypted_credentials)
        # If new_credentials was None or empty, we effectively remove/don't update it.

    if not update_data and "credentials" not in obj_in.model_dump(exclude_unset=True): # Check if only credentials was passed and handled
        return db_obj # No other fields to update

    # Update other fields
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def delete_connection(
    db: Session, *, connection_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[AzureBlobConnection]:
    """Delete a connection by ID for a specific user."""
    db_obj = get_connection(db=db, connection_id=connection_id, user_id=user_id)
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj # Returns the deleted object or None if not found 