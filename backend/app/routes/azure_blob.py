import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.azure_blob import AzureAuthType
from app.schemas.azure_blob import (
    AzureBlobConnectionCreate,
    AzureBlobConnectionRead,
    AzureBlobObject,
    AzureBlobSyncItemCreate,
    AzureBlobSyncItemRead,
    # AzureBlobConnectionUpdate # Import when needed for update endpoint
    AzureIngestRequest
)
from app.crud import crud_azure_blob, crud_azure_blob_sync_item
from app.services.azure_blob_service import AzureBlobService
from app.dependencies.auth import get_current_active_user
from app.tasks.azure_tasks import process_azure_ingestion_task
from app.schemas.tasks import TaskStatusResponse

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
    # Ensure the user is providing a connection string
    if connection_in.auth_type != AzureAuthType.CONNECTION_STRING:
        logger.warning(f"Attempt to create connection with unsupported auth type '{connection_in.auth_type}'. Expected CONNECTION_STRING.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid authentication type specified. Only connection strings are supported."
        )

    try:
        # CRUD function expects credentials (connection string) in obj_in
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

@router.delete(
    "/connections/{connection_id}",
    response_model=AzureBlobConnectionRead, # Return the deleted connection data
    status_code=status.HTTP_200_OK,
    summary="Delete Azure Blob Storage Connection",
    description="Deletes a specific Azure Blob Storage connection configuration by its ID."
)
def delete_azure_blob_connection(
    *, 
    db: Session = Depends(get_db),
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Delete an Azure Blob Storage connection owned by the current user."""
    logger.info(f"User {current_user.email} attempting to delete Azure Blob connection ID: {connection_id}")
    deleted_connection = crud_azure_blob.remove_connection(
        db=db, connection_id=connection_id, user_id=current_user.id
    )

    if not deleted_connection:
        logger.warning(f"Azure Blob connection ID {connection_id} not found or not owned by user {current_user.email}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Azure Blob connection not found."
        )
    
    logger.info(f"Successfully deleted Azure Blob connection {connection_id} for user {current_user.email}.")
    return deleted_connection

@router.get(
    "/connections/{connection_id}/containers",
    response_model=List[str],
    summary="List Containers for a Connection",
    description="Lists all accessible containers for a specific Azure Blob Storage connection."
)
async def list_azure_blob_containers(
    *, 
    db: Session = Depends(get_db),
    connection_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve container names for a specific Azure connection owned by the user."""
    # Get connection with decrypted credentials (which is the connection string)
    # Function now returns a tuple: (connection_obj, decrypted_credential)
    result = crud_azure_blob.get_connection_with_decrypted_credentials(
        db=db, connection_id=connection_id, user_id=current_user.id
    )

    if not result:
        # CRUD function returns None if not found OR decryption fails
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Azure Blob connection not found or credentials could not be decrypted."
        )
    
    # Unpack the tuple
    connection, decrypted_connection_string = result

    # --- DEBUG LOG: Log the decrypted string --- 
    # WARNING: This logs the sensitive connection string to the console.
    # Remove this log in production or when debugging is complete.
    logger.info(f"[Route Decrypt Check] Decrypted connection string for {connection.id}: '{decrypted_connection_string}'")
    # --- END DEBUG LOG --- 

    # Ensure we are handling the correct auth type (connection string)
    if connection.auth_type != AzureAuthType.CONNECTION_STRING:
        logger.error(f"Connection {connection_id} has unexpected auth type {connection.auth_type} when expecting CONNECTION_STRING.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, # Should not happen if created correctly
            detail=f"Internal configuration error for connection authentication type."
        )

    if not decrypted_connection_string:
        # This check should now be redundant as crud function handles it, but keep for safety
        logger.error(f"Missing decrypted connection string after successful fetch for connection {connection_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal configuration error: Missing connection string.")

    try:
        # Use async context manager and await the async method
        # Pass the CORRECT decrypted connection string to the service
        async with AzureBlobService(connection_string=decrypted_connection_string) as service:
            containers = await service.list_containers()
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
async def list_azure_blob_objects(
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
    result = crud_azure_blob.get_connection_with_decrypted_credentials(
        db=db, connection_id=connection_id, user_id=current_user.id
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Azure Blob connection not found or credentials could not be decrypted."
        )
    
    # Unpack the tuple
    connection, decrypted_connection_string = result

    # --- DEBUG LOG: Log the decrypted string --- 
    # WARNING: This logs the sensitive connection string to the console.
    # Remove this log in production or when debugging is complete.
    logger.info(f"[Route Decrypt Check] Decrypted connection string for {connection.id}: '{decrypted_connection_string}'")
    # --- END DEBUG LOG --- 

    # Check auth type
    if connection.auth_type != AzureAuthType.CONNECTION_STRING:
        logger.warning(f"Unsupported auth type {connection.auth_type} for connection {connection_id}. Expected CONNECTION_STRING.")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Listing blobs via auth type '{connection.auth_type}' is not supported."
        )

    if not decrypted_connection_string:
        # This check should now be redundant as crud function handles it, but keep for safety
        logger.error(f"Missing decrypted connection string after successful fetch for connection {connection_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal configuration error: Missing connection string.")

    try:
        # 2. Use async context manager and await the async method
        # Pass the CORRECT decrypted connection string to the service
        async with AzureBlobService(connection_string=decrypted_connection_string) as service:
            # 3. Call the service method to list blobs
            blobs = await service.list_blobs(container_name=container_name, prefix=prefix)
            return blobs # Return the list of AzureBlobObject dicts
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

@router.post(
    "/sync_items",
    response_model=AzureBlobSyncItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add Azure Blob Item to Sync List",
    description="Adds a specific Azure blob or prefix to the user's sync list."
)
def add_azure_sync_item(
    item_in: AzureBlobSyncItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Basic validation
    if item_in.item_type not in ['blob', 'prefix']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid item_type. Must be 'blob' or 'prefix'.")
    if item_in.item_type == 'prefix' and not item_in.item_path.endswith('/'):
        item_in.item_path += '/'

    # Ensure the connection exists and belongs to the user before adding item
    connection = crud_azure_blob.get_connection(db=db, connection_id=item_in.connection_id, user_id=current_user.id)
    if not connection:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Azure connection {item_in.connection_id} not found or not owned by user.")

    logger.info(f"User {current_user.email} adding Azure sync item: {item_in.item_path} for connection {item_in.connection_id}")
    db_item = crud_azure_blob_sync_item.add_sync_item(db=db, item_in=item_in, user_id=current_user.id)
    if db_item is None:
        # Item already exists, fetch and return it
        existing_item = db.execute(select(crud_azure_blob_sync_item.AzureBlobSyncItem).where(
            crud_azure_blob_sync_item.AzureBlobSyncItem.connection_id == item_in.connection_id,
            crud_azure_blob_sync_item.AzureBlobSyncItem.item_path == item_in.item_path,
            crud_azure_blob_sync_item.AzureBlobSyncItem.user_id == current_user.id
        )).scalars().first()
        if existing_item:
            logger.warning(f"Item {item_in.item_path} already in sync list for connection {item_in.connection_id}, returning existing (ID: {existing_item.id}).")
            return existing_item
        else:
            logger.error(f"IntegrityError adding {item_in.item_path} but couldn't find existing item.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error checking for existing sync item.")

    logger.info(f"Successfully added Azure sync item {db_item.id} ('{db_item.item_path}') for user {current_user.email}")
    return db_item

@router.get(
    "/sync_items",
    response_model=List[AzureBlobSyncItemRead],
    summary="Get Azure Blob Sync List for Connection",
    description="Retrieves sync items, optionally filtered by connection and status."
)
def get_azure_sync_items(
    connection_id: Optional[uuid.UUID] = Query(None, description="Filter items by a specific connection ID. If omitted, returns items for all user connections."),
    status: Optional[str] = Query(None, description="Filter items by status (e.g., 'pending', 'completed', 'error')"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Log the request details
    logger.info(f"User {current_user.email} requesting sync items. Connection filter: {connection_id}, Status filter: {status}")

    # Fetch items based on whether connection_id is provided
    try:
        # Ensure status is handled correctly (e.g., split if multiple statuses are supported later)
        status_list = [status] if status else None # Currently handles single status
        
        # Pass optional connection_id to CRUD
        items = crud_azure_blob_sync_item.get_items_by_user_and_connection(
            db=db, 
            user_id=current_user.id, 
            connection_id=connection_id, # Pass None if not provided
            status_filter=status_list
        )
        logger.info(f"Found {len(items)} sync items for user {current_user.email} with filters: Connection={connection_id}, Status={status}")
        return items
    except Exception as e:
        logger.error(f"Error fetching sync items for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sync items."
        )

@router.delete(
    "/sync_items/{item_id}",
    response_model=AzureBlobSyncItemRead, # Return the deleted item
    status_code=status.HTTP_200_OK,
    summary="Remove Azure Blob Item from Sync List",
    description="Removes an item from the Azure sync list by its database ID."
)
def remove_azure_sync_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"User {current_user.email} attempting to remove Azure sync item ID: {item_id}")
    deleted_item = crud_azure_blob_sync_item.remove_sync_item(db=db, item_id=item_id, user_id=current_user.id)

    if not deleted_item:
        logger.warning(f"Azure sync item ID {item_id} not found or not owned by user {current_user.email}.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Azure sync item not found.")

    logger.info(f"Successfully removed Azure sync item {item_id} for user {current_user.email}.")
    return deleted_item

@router.post(
    "/ingest",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process Pending Azure Blob Sync Items for a Connection",
    description="Initiates a background task to process pending Azure items for a specific connection."
)
def trigger_azure_ingestion_endpoint(
    ingest_request: AzureIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    connection_id = ingest_request.connection_id
    logger.info(f"User {current_user.email} requested processing of pending Azure sync items for connection {connection_id}.")

    # Ensure connection exists and belongs to user (also implicitly checks ownership for items)
    connection = crud_azure_blob.get_connection(db=db, connection_id=connection_id, user_id=current_user.id)
    if not connection:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Azure connection {connection_id} not found or not owned by user.")

    # Fetch pending items for this connection
    logger.info(f"Fetching pending sync items for connection {ingest_request.connection_id}...")
    pending_items = crud_azure_blob_sync_item.get_items_by_user_and_connection(
        db=db, 
        connection_id=ingest_request.connection_id, 
        user_id=current_user.id, 
        status_filter=['pending'] # Use correct function name and pass status as a list
    )

    if not pending_items:
        logger.info(f"No pending Azure sync items found for connection {ingest_request.connection_id}. Nothing to process.")
        return TaskStatusResponse(
            task_id=None,
            status="NO_OP",
            message=f"No pending Azure items found for connection {connection.name} to process."
        )

    # Prepare payload for Celery task (still only needs user_id, task fetches items again)
    task_payload = {
        "user_id_str": str(current_user.id),
        # Consider passing connection_id if the task needs to filter by it initially?
        # For now, task fetches all pending for user and groups by connection.
    }

    # Submit task to Celery
    try:
        task = process_azure_ingestion_task.delay(**task_payload)
        logger.info(f"Submitted Azure ingestion task {task.id} for user {current_user.email} (triggered for conn {connection_id}) to process {len(pending_items)} items.")
        return TaskStatusResponse(
            task_id=task.id,
            status="PENDING",
            message=f"Azure ingestion task submitted to process {len(pending_items)} pending item(s) for connection {connection.name}."
        )
    except Exception as e:
        logger.error(f"Failed to submit Azure ingestion task for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start Azure ingestion task.")

# TODO: Add endpoints for GET /connections/{id}, PUT/PATCH /connections/{id}, DELETE /connections/{id}
# TODO: Add endpoints for upload, download, delete blobs (likely nested under connections/{id}/...)

# TODO: Add endpoints for GET /connections/{id}, PUT/PATCH /connections/{id}, DELETE /connections/{id}
# TODO: Add endpoints for upload, download, delete blobs (likely nested under connections/{id}/...) 