import uuid
import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete

from app.models.azure_blob import AzureBlobConnection
from app.models.azure_blob import AzureAuthType
from app.models.azure_blob_sync_item import AzureBlobSyncItem
from app.schemas.azure_blob import AzureBlobConnectionCreate, AzureBlobConnectionUpdate
from app.utils.security import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

def create_connection(
    db: Session, *, obj_in: AzureBlobConnectionCreate, user_id: uuid.UUID
) -> AzureBlobConnection:
    """Create a new Azure Blob connection, encrypting the connection string."""
    # Encrypt the connection string provided in credentials field
    encrypted_connection_string = encrypt_token(obj_in.credentials)
    if not encrypted_connection_string:
        logger.error(f"Failed to encrypt connection string for user {user_id}.")
        raise ValueError("Failed to encrypt connection string")

    logger.info(f"[CRUD Create] Storing encrypted credentials: {encrypted_connection_string}") # LOG ENCRYPTED DATA
    db_obj = AzureBlobConnection(
        # Exclude plain text credentials, explicitly set encrypted value
        **obj_in.model_dump(exclude={"credentials"}), 
        user_id=user_id,
        # account_key=None, # Ensure account_key is None
        credentials=encrypted_connection_string # Store encrypted conn string if applicable
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
) -> Optional[Tuple[AzureBlobConnection, str]]:
    """Get a connection and attempt to decrypt the stored connection string.
       Returns a tuple containing the original DB object and the decrypted connection string,
       or None if decryption fails, connection not found, or required credential is missing.
       Does NOT modify the returned DB object.
    """
    logger.info(f"[CRUD Decrypt] Attempting to find connection ID: {connection_id} for user ID: {user_id}")
    db_obj = get_connection(db=db, connection_id=connection_id, user_id=user_id)
    if db_obj:
        logger.info(f"[CRUD Decrypt] Found connection ID: {connection_id}. Auth type: {db_obj.auth_type}. Attempting decryption of credentials field.")
        if db_obj.auth_type != AzureAuthType.CONNECTION_STRING:
            logger.error(f"[CRUD Decrypt] Connection {db_obj.id} has unexpected auth type {db_obj.auth_type}. Expected CONNECTION_STRING.")
            return None # Cannot proceed if type doesn't match expected data
            
        stored_encrypted_credentials = db_obj.credentials
        if not stored_encrypted_credentials:
            logger.error(f"[CRUD Decrypt] Connection {db_obj.id} uses CONNECTION_STRING auth but the credentials field is empty.")
            return None
        
        logger.info(f"[CRUD Decrypt] Attempting to decrypt stored value: {stored_encrypted_credentials}") # LOG DATA BEFORE DECRYPT
        decrypted_creds = decrypt_token(stored_encrypted_credentials)
        if decrypted_creds is None:
            logger.error(f"[CRUD Decrypt] Failed to decrypt credentials field for connection {db_obj.id}.")
            return None
        logger.info(f"[CRUD Decrypt] Successfully decrypted credentials field for connection ID: {connection_id}. Returning object and decrypted string.")
        # Return the original object and the decrypted string separately
        return db_obj, decrypted_creds
              
    else:
        logger.warning(f"[CRUD Decrypt] Connection ID {connection_id} not found for user ID: {user_id}.")
        return None # Return None if connection not found

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
    """Update an Azure Blob connection, encrypting connection string if provided."""
    update_data = obj_in.model_dump(exclude_unset=True)
    # Handle update for connection string (credentials)
    if "credentials" in update_data:
        new_connection_string = update_data.pop("credentials")
        if new_connection_string:
            encrypted_cs = encrypt_token(new_connection_string)
            if not encrypted_cs: raise ValueError("Failed to encrypt new connection string")
            setattr(db_obj, "credentials", encrypted_cs)
            # Ensure auth_type is correct
            if db_obj.auth_type != AzureAuthType.CONNECTION_STRING:
                setattr(db_obj, "auth_type", AzureAuthType.CONNECTION_STRING)
            # Ensure account_key is None if model still has it
            # if hasattr(db_obj, "account_key"): setattr(db_obj, "account_key", None)
        else:
            setattr(db_obj, "credentials", None) # Clear if provided as empty
            logger.warning(f"Attempted to update connection {db_obj.id} with empty connection string.")
            # Potentially mark as inactive or handle error if needed

    # Update other fields provided in update_data
    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

# Function to remove a connection (Handles sync items)
def remove_connection(db: Session, *, connection_id: uuid.UUID, user_id: uuid.UUID) -> AzureBlobConnection | None:
    """Removes an Azure Blob connection by its ID if it belongs to the user."""
    db_connection = get_connection(db=db, connection_id=connection_id, user_id=user_id)
    if db_connection:
        try:
            # Delete dependent sync items first to avoid foreign key violation
            delete_sync_items_stmt = delete(AzureBlobSyncItem).where(
                AzureBlobSyncItem.connection_id == connection_id,
                AzureBlobSyncItem.user_id == user_id
            )
            result = db.execute(delete_sync_items_stmt)
            logger.info(f"Deleted {result.rowcount} associated sync items for connection {connection_id}.")

            # Now delete the connection itself
            db.delete(db_connection)
            db.commit()
            logger.info(f"Removed Azure Blob connection ID {connection_id} ('{db_connection.name}') for user {user_id}.")
            return db_connection # Return the deleted item
        except Exception as e:
            db.rollback()
            logger.error(f"Error removing Azure Blob connection ID {connection_id} for user {user_id}: {e}", exc_info=True)
            raise
    else:
        logger.warning(f"Attempt to remove non-existent or unowned Azure Blob connection ID {connection_id} by user {user_id}.")
        return None # Indicate item not found or not owned
# --- End NEW Function --- 