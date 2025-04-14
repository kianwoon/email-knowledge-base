import logging
from typing import List, Optional, Dict, Any, IO
from datetime import datetime
from azure.storage.blob.aio import BlobServiceClient, ContainerClient, BlobClient
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError, ServiceRequestError, HttpResponseError
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
# from azure.identity.aio import DefaultAzureCredential # For future use if supporting Managed Identity
# from azure.core.credentials import AzureKeyCredential
import asyncio
from app.config import settings

# --- Add specific logger for this service ---
logger = logging.getLogger(__name__) # Get logger specific to this module
logger.setLevel(logging.DEBUG) # Force this logger to DEBUG level
# --- End logger setup ---

def parse_connection_string(connection_string: str) -> Dict[str, str]:
    """Parses a connection string into a dictionary."""
    logger.debug(f"[Parser] Attempting to parse string: '{connection_string}'") # Log input
    parts = connection_string.split(';')
    logger.debug(f"[Parser] Split parts by ';': {parts}") # Log parts
    parsed_dict = {}
    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
            stripped_key = key.strip()
            stripped_value = value.strip()
            logger.debug(f"[Parser] Found key='{stripped_key}', value_preview='{stripped_value[:5]}...'") # Log found key/value
            parsed_dict[stripped_key] = stripped_value
        else:
            logger.debug(f"[Parser] Skipping part without '=': '{part}'") # Log skipped parts
    logger.debug(f"[Parser] Final parsed dictionary: {parsed_dict}") # Log final dict
    return parsed_dict

class AzureBlobService:
    """Service class for interacting with Azure Blob Storage."""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.blob_service_client: Optional[BlobServiceClient] = None # Initialize as None
        # Keep parsing for logging/potential future use, but don't use for client creation
        self._parsed_conn_parts = parse_connection_string(connection_string)
        self._log_parsed_parts()
        # Validate essential parts were parsed for logging sanity check
        if not self._parsed_conn_parts.get('AccountName') or not self._parsed_conn_parts.get('AccountKey'):
             logger.warning("[Service Init] Parser did not extract AccountName/AccountKey, but proceeding with from_connection_string.")

    def _log_parsed_parts(self):
        """Helper to log parsed components (avoids cluttering init)."""
        account_name = self._parsed_conn_parts.get('AccountName')
        account_key = self._parsed_conn_parts.get('AccountKey')
        endpoint_suffix = self._parsed_conn_parts.get('EndpointSuffix', 'core.windows.net')
        
        logger.info(f"[Service Init - Parsed] AccountName: '{account_name}'")
        key_preview = f"{account_key[:4]}...{account_key[-4:]}" if account_key and len(account_key) > 8 else "None/Invalid"
        logger.info(f"[Service Init - Parsed] AccountKey Preview: '{key_preview}'")
        logger.info(f"[Service Init - Parsed] EndpointSuffix: '{endpoint_suffix}'")

    async def __aenter__(self):
        """Async context manager entry: Initialize the client."""
        try:
            logger.info("[Service Init] Attempting to create BlobServiceClient using from_connection_string...")
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            logger.info("[Service Init] BlobServiceClient created successfully via from_connection_string.")
            # Perform a quick connectivity test (e.g., get properties)
            await self.test_connection() # Add a connection test method
            return self # Return the service instance
        except ValueError as e:
            logger.error(f"Invalid connection string format provided to BlobServiceClient: {e}", exc_info=True)
            # Re-raise ValueError to be caught by the route handler as 400 Bad Request
            raise ValueError(f"Invalid connection string format: {e}") from e
        except ClientAuthenticationError as e:
            logger.error(f"Authentication failed with Azure using the provided connection string: {e}", exc_info=True)
            # Raise PermissionError to be caught by route handler as 403 Forbidden
            raise PermissionError(f"Authentication failed: {e}") from e 
        except Exception as e:
            # Catch other potential init errors (DNS issues, etc.)
            logger.error(f"Unexpected error initializing Azure BlobServiceClient from connection string: {e}", exc_info=True)
            # Raise a generic RuntimeError to be caught as 500 Internal Server Error
            raise RuntimeError("Could not initialize connection to Azure Blob Storage.") from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit: Close the client."""
        if self.blob_service_client:
            logger.info("Closing Azure BlobServiceClient...")
            await self.blob_service_client.close()
            logger.info("Azure BlobServiceClient closed.")
        self.blob_service_client = None # Ensure it's cleared

    async def test_connection(self):
        """Tests the connection by attempting to get service properties."""
        if not self.blob_service_client:
            raise RuntimeError("Blob service client not initialized.")
        try:
            logger.info("Testing connection by getting account information...")
            # Getting account info is a good lightweight test
            account_info = await self.blob_service_client.get_account_information()
            logger.info(f"Connection test successful. Account Kind: {account_info.get('account_kind')}")
        except ClientAuthenticationError as e:
            logger.error(f"Connection Test Failed: Authentication error: {e}", exc_info=True)
            raise PermissionError(f"Authentication failed during connection test: {e}") from e
        except Exception as e:
            # Catch other potential errors like DNS resolution, network issues
            logger.error(f"Connection Test Failed: Error getting account info: {e}", exc_info=True)
            raise RuntimeError(f"Failed to connect or communicate with Azure Storage: {e}") from e

    async def list_containers(self) -> List[str]:
        """Lists all container names in the storage account."""
        container_names = []
        try:
            async for container_properties in self.blob_service_client.list_containers():
                container_names.append(container_properties.name)
            logger.info(f"Successfully listed {len(container_names)} containers.")
            return container_names
        except ClientAuthenticationError as e:
            logger.error(f"Authentication failed when listing containers: {e}")
            raise PermissionError("Authentication failed with Azure Blob Storage.") from e
        except Exception as e:
            logger.error(f"Error listing containers: {e}", exc_info=True)
            raise RuntimeError("An error occurred while listing containers.") from e

    async def list_blobs(self, container_name: str, prefix: str = "") -> List[Dict[str, Any]]:
        """Lists blobs (files and directories) within a specific container and prefix asynchronously."""
        if not container_name:
            raise ValueError("Container name cannot be empty.")

        blobs_info: List[Dict[str, Any]] = []
        try:
            container_client: ContainerClient = self.blob_service_client.get_container_client(container_name)
            async for item in container_client.walk_blobs(name_starts_with=prefix, delimiter='/'):
                 # item can be BlobProperties (file) or BlobPrefix (directory)
                 if hasattr(item, 'size'): # Check if it's a blob (BlobProperties has size)
                    blobs_info.append({
                        "name": item.name.split('/')[-1], 
                        "path": item.name,
                        "isDirectory": False,
                        "size": item.size,
                        "lastModified": item.last_modified.isoformat() if item.last_modified else None,
                        "etag": item.etag,
                        "content_type": item.content_settings.content_type,
                    })
                 else: # It's a prefix (directory)
                     if item.name != prefix:
                         blobs_info.append({
                            "name": item.name.replace(prefix, '', 1).split('/')[0] + '/', 
                            "path": item.name,
                            "isDirectory": True,
                            "size": None,
                            "lastModified": None, 
                         })
            
            logger.info(f"Retrieved {len(blobs_info)} item(s) from container '{container_name}' with prefix '{prefix}'.")
            return blobs_info
        except ResourceNotFoundError:
            logger.warning(f"Container '{container_name}' not found when listing blobs with prefix '{prefix}'.")
            raise FileNotFoundError(f"Container '{container_name}' not found.")
        except ClientAuthenticationError as e:
            logger.error(f"Authentication failed when listing blobs in '{container_name}' with prefix '{prefix}': {e}")
            raise PermissionError("Authentication failed with Azure Blob Storage.") from e
        except Exception as e:
            logger.error(f"Error listing blobs in '{container_name}' with prefix '{prefix}': {e}", exc_info=True)
            raise RuntimeError(f"An error occurred while listing blobs in '{container_name}' with prefix '{prefix}'.") from e

    async def download_blob_content(self, container_name: str, blob_path: str) -> Optional[bytes]:
        """Downloads the content of a specific blob asynchronously."""
        if not container_name or not blob_path:
            raise ValueError("Container name and blob path are required.")
        logger.debug(f"Attempting to download blob: {container_name}/{blob_path}")
        try:
            blob_client: BlobClient = self.blob_service_client.get_blob_client(container=container_name, blob=blob_path)
            download_stream = await blob_client.download_blob()
            data = await download_stream.readall()
            logger.info(f"Successfully downloaded {len(data)} bytes from {container_name}/{blob_path}")
            return data
        except ResourceNotFoundError:
            logger.warning(f"Blob '{blob_path}' not found in container '{container_name}'.")
            return None
        except ClientAuthenticationError as e:
            logger.error(f"Authentication failed downloading blob {container_name}/{blob_path}: {e}")
            raise PermissionError("Authentication failed with Azure Blob Storage.") from e
        except Exception as e:
            logger.error(f"Error downloading blob {container_name}/{blob_path}: {e}", exc_info=True)
            raise RuntimeError(f"An error occurred while downloading blob '{blob_path}'.") from e

    # --- Placeholder methods for future implementation ---
    # upload_blob would also need to be async
    # delete_blob would also need to be async

    # def upload_blob(self, container_name: str, blob_name: str, data: bytes | IO) -> BlobProperties:
    #     """Uploads data to a blob."""
    #     # Implementation needed
    #     pass

    # def download_blob(self, container_name: str, blob_name: str) -> bytes:
    #     """Downloads a blob's content."""
    #     # Implementation needed
    #     pass

    # def delete_blob(self, container_name: str, blob_name: str) -> None:
    #     """Deletes a blob."""
    #     # Implementation needed
    #     pass 