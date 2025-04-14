import logging
from typing import List, Optional, Dict, Any
from datetime import datetime # Import datetime
from azure.storage.blob import BlobServiceClient, ContainerProperties, BlobProperties, BlobPrefix
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError

logger = logging.getLogger(__name__)

class AzureBlobService:
    """Service class for interacting with Azure Blob Storage."""

    def __init__(self, connection_string: str):
        """Initializes the service with Azure Blob Storage credentials."""
        if not connection_string:
            logger.error("Azure connection string is missing.")
            raise ValueError("Azure connection string is required to initialize AzureBlobService")
        
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            logger.info("Azure BlobServiceClient initialized successfully.")
        except ValueError as e:
            # Often indicates a malformed connection string
            logger.error(f"Invalid Azure connection string format: {e}")
            raise ValueError("Invalid Azure connection string provided.") from e
        except Exception as e:
            # Catch other potential init errors
            logger.error(f"Failed to initialize Azure BlobServiceClient: {e}", exc_info=True)
            raise RuntimeError("Could not connect to Azure Blob Storage.") from e

    def list_containers(self) -> List[str]:
        """Lists all container names in the storage account."""
        containers: List[str] = []
        try:
            container_properties_list = self.blob_service_client.list_containers()
            for container in container_properties_list:
                containers.append(container.name)
            logger.info(f"Retrieved {len(containers)} container(s).")
            return containers
        except ClientAuthenticationError as e:
            logger.error(f"Authentication failed when listing Azure containers: {e}")
            # Re-raise maybe? Or return empty list with error logged?
            # Raising allows the route handler to return a specific HTTP error
            raise PermissionError("Authentication failed with Azure Blob Storage.") from e
        except Exception as e:
            logger.error(f"Error listing Azure containers: {e}", exc_info=True)
            raise RuntimeError("An error occurred while listing Azure containers.") from e

    def list_blobs(self, container_name: str, prefix: str = "") -> List[Dict[str, Any]]:
        """Lists blobs (files and directories) within a specific container and prefix."""
        if not container_name:
            raise ValueError("Container name cannot be empty.")

        blobs_info: List[Dict[str, Any]] = []
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            # Use walk_blobs to get both blobs and prefixes (directories)
            # Specify delimiter='/\' to treat '/' as directory separator
            blob_iter = container_client.walk_blobs(name_starts_with=prefix, delimiter='/')
            
            for item in blob_iter:
                 # item can be BlobProperties (file) or BlobPrefix (directory)
                if isinstance(item, BlobProperties):
                    # It's a file
                    blobs_info.append({
                        "name": item.name.split('/')[-1], # Get the base name
                        "path": item.name,
                        "isDirectory": False,
                        "size": item.size,
                        "lastModified": item.last_modified.isoformat() if item.last_modified else None,
                        "etag": item.etag,
                        "content_type": item.content_settings.content_type,
                    })
                elif isinstance(item, BlobPrefix):
                     # It's a directory (represented by prefix)
                     # Ensure we don't add the parent directory itself if prefix is not empty
                    if item.name != prefix:
                         blobs_info.append({
                            "name": item.name.replace(prefix, '', 1).split('/')[0] + '/', # Get the immediate directory name
                            "path": item.name,
                            "isDirectory": True,
                            "size": None,
                            "lastModified": None, # Directories don't have this directly
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

    # --- Placeholder methods for future implementation ---

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