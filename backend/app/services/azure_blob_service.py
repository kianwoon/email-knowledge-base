import logging
from typing import List, Optional
from azure.storage.blob import BlobServiceClient, ContainerProperties, BlobProperties
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

    # --- Placeholder methods for future implementation ---

    # def list_blobs(self, container_name: str) -> List[BlobProperties]:
    #     """Lists blobs within a specific container."""
    #     try:
    #         container_client = self.blob_service_client.get_container_client(container_name)
    #         blob_list = container_client.list_blobs()
    #         blobs = list(blob_list)
    #         logger.info(f"Retrieved {len(blobs)} blob(s) from container '{container_name}'.")
    #         return blobs
    #     except ResourceNotFoundError:
    #         logger.warning(f"Container '{container_name}' not found when listing blobs.")
    #         raise FileNotFoundError(f"Container '{container_name}' not found.")
    #     except ClientAuthenticationError as e:
    #         logger.error(f"Authentication failed when listing blobs in '{container_name}': {e}")
    #         raise PermissionError("Authentication failed with Azure Blob Storage.") from e
    #     except Exception as e:
    #         logger.error(f"Error listing blobs in '{container_name}': {e}", exc_info=True)
    #         raise RuntimeError(f"An error occurred while listing blobs in '{container_name}'.") from e

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