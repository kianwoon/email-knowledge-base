import uuid
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.azure_blob import AzureAuthType
from app.schemas.azure_blob import (
    AzureBlobConnectionCreate,
    AzureBlobConnectionRead,
    AzureBlobObject,
    # AzureBlobConnectionUpdate # Import when needed for update endpoint
)
from app.crud import crud_azure_blob
from app.services.azure_blob_service import AzureBlobService
from app.dependencies.auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/connections",
    response_model=AzureBlobConnectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Azure Blob Storage Connection",
    description="Stores connection details for Azure Blob Storage, encrypting credentials."
)
def create_azure_blob_connection(
    *, 
    db: Session = Depends(get_db),
    connection_in: AzureBlobConnectionCreate,
    current_user: User = Depends(get_current_active_user)
):
    """Create a new Azure Blob Storage connection configuration for the current user."""
    # Ensure the user is providing a connection string for now
    if connection_in.auth_type != AzureAuthType.CONNECTION_STRING:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Authentication type '{connection_in.auth_type}' is not yet supported."
        )
    
    try:
        connection = crud_azure_blob.create_connection(
            db=db, obj_in=connection_in, user_id=current_user.id
        )
        return connection
    except ValueError as e:
        # Handle potential encryption errors from CRUD
        logger.error(f"Failed to create Azure Blob connection for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Failed to create connection: {e}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating Azure Blob connection for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the connection."
        )

@router.get(
    "/connections",
    response_model=List[AzureBlobConnectionRead],
    summary="List Azure Blob Storage Connections",
    description="Retrieves all Azure Blob Storage connection configurations for the current user."
)
def list_azure_blob_connections(
    *, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 100
):
    """Retrieve Azure Blob Storage connections belonging to the current user."""
    connections = crud_azure_blob.get_connections_by_user(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )
    return connections

@router.get(
    "/connections/{connection_id}/containers",
    response_model=List[str],
    summary="List Containers for a Connection",
    description="Lists all accessible containers for a specific Azure Blob Storage connection."
)
def list_azure_blob_containers(
    *, 
    db: Session = Depends(get_db),
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve container names for a specific Azure connection owned by the user."""
    # Get connection with decrypted credentials
    connection = crud_azure_blob.get_connection_with_decrypted_credentials(
        db=db, connection_id=connection_id, user_id=current_user.id
    )

    if not connection:
        # This covers both connection not found and decryption failure
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Azure Blob connection not found or credentials could not be decrypted."
        )

    # Check auth type (only connection string supported initially)
    if connection.auth_type != AzureAuthType.CONNECTION_STRING:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Listing containers via auth type '{connection.auth_type}' is not yet supported."
        )

    try:
        # Initialize service with decrypted connection string
        service = AzureBlobService(connection_string=connection.credentials)
        containers = service.list_containers()
        return containers
    except ValueError as e:
        # Handle invalid connection string from service init
        logger.warning(f"Invalid connection string for connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection configuration is invalid: {e}"
        )
    except PermissionError as e:
        # Handle authentication errors from service
        logger.warning(f"Authentication failed for connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Authentication failed with Azure Blob Storage: {e}"
        )
    except FileNotFoundError as e: # If service raises this for specific cases
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        # Handle generic runtime errors from service
        logger.error(f"Runtime error listing containers for connection {connection_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while communicating with Azure: {e}"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing containers for connection {connection_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )

@router.get(
    "/connections/{connection_id}/containers/{container_name}/objects",
    response_model=List[AzureBlobObject],
    summary="List Blobs (Objects) in a Container",
    description="Lists blobs (files and directories) within a specific container and prefix."
)
def list_azure_blob_objects(
    *, 
    db: Session = Depends(get_db),
    connection_id: uuid.UUID,
    container_name: str,
    prefix: str = Query("", description="Optional path prefix to filter blobs (e.g., 'folder1/subfolder/')"),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve blobs (files and directories) for a specific container and prefix."""
    logger.info(f"Request: GET /api/v1/azure_blob/connections/{connection_id}/containers/{container_name}/objects?prefix={prefix} by user {current_user.email}")
    # 1. Get connection and decrypt credentials
    connection = crud_azure_blob.get_connection_with_decrypted_credentials(
        db=db, connection_id=connection_id, user_id=current_user.id
    )

    if not connection:
        logger.warning(f"Azure Blob connection {connection_id} not found or decryption failed for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Azure Blob connection not found or credentials could not be decrypted."
        )

    # Check auth type (only connection string supported initially)
    if connection.auth_type != AzureAuthType.CONNECTION_STRING:
        logger.warning(f"Unsupported auth type {connection.auth_type} for connection {connection_id}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Listing blobs via auth type '{connection.auth_type}' is not yet supported."
        )

    # 2. Initialize AzureBlobService and list blobs
    try:
        service = AzureBlobService(connection_string=connection.credentials)
        blobs = service.list_blobs(container_name, prefix)
        logger.info(f"Successfully listed {len(blobs)} blobs for connection {connection_id}, container {container_name}, prefix '{prefix}'")
        return blobs
    except ValueError as e:
        # Handle invalid connection string from service init or bad container name?
        logger.warning(f"Invalid configuration for connection {connection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection configuration is invalid: {e}"
        )
    except PermissionError as e:
        # Handle authentication errors from service
        logger.warning(f"Authentication failed for connection {connection_id} listing blobs in {container_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Authentication failed with Azure Blob Storage: {e}"
        )
    except FileNotFoundError as e: # Container not found
         logger.warning(f"Container '{container_name}' not found for connection {connection_id}")
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        # Handle generic runtime errors from service
        logger.error(f"Runtime error listing blobs for connection {connection_id}, container {container_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while communicating with Azure: {e}"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing blobs for connection {connection_id}, container {container_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing blobs."
        )

# TODO: Add endpoints for GET /connections/{id}, PUT/PATCH /connections/{id}, DELETE /connections/{id}
# TODO: Add endpoints for upload, download, delete blobs (likely nested under connections/{id}/...) 