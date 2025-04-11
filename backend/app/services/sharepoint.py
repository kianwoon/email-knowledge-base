import httpx
from typing import List, Dict, Any, Optional
from app.models.sharepoint import SharePointSite, SharePointDrive, SharePointItem
import logging
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MS_GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"

class SharePointService:
    def __init__(self, access_token: str):
        if not access_token:
            raise ValueError("Access token cannot be empty.")
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _make_graph_request(self, url: str, method: str = "GET", **kwargs) -> Optional[Dict[str, Any]]:
        """Helper function to make requests to Microsoft Graph API."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, headers=self.headers, **kwargs)
                response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
                if response.status_code == 204: # No content
                    return None
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
                # Consider re-raising or returning a specific error structure
                raise
            except httpx.RequestError as e:
                logger.error(f"Request error occurred: {e}")
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                raise

    async def search_accessible_sites(self) -> List[SharePointSite]:
        """Searches for SharePoint sites accessible by the signed-in user."""
        # Changed endpoint from /me/followedSites to /sites?search=*
        sites_url = f"{MS_GRAPH_ENDPOINT}/sites?search=*"
        logger.info(f"Attempting to fetch accessible sites using: {sites_url}")
        try:
            response_data = await self._make_graph_request(sites_url)
            if response_data and "value" in response_data:
                # The response structure for search might differ slightly, 
                # but the SharePointSite model should handle common fields like id, name, displayName, webUrl.
                # Log the raw response for debugging if needed.
                # logger.debug(f"Raw site search response: {response_data['value']}")
                sites = [SharePointSite(**site) for site in response_data["value"]]
                logger.info(f"Found {len(sites)} accessible sites.")
                return sites
            logger.info("No accessible sites found in the response.")
            return []
        except Exception as e:
            # Log the specific exception
            logger.error(f"Error searching accessible sites: {e}", exc_info=True)
            return [] # Return empty list on error

    async def list_drives_for_site(self, site_id: str) -> List[SharePointDrive]:
        """Lists document libraries (drives) for a specific SharePoint site."""
        drives_url = f"{MS_GRAPH_ENDPOINT}/sites/{site_id}/drives"
        try:
            response_data = await self._make_graph_request(drives_url)
            if response_data and "value" in response_data:
                drives = [SharePointDrive(**drive) for drive in response_data["value"]]
                return drives
            return []
        except Exception as e:
            logger.error(f"Error listing drives for site {site_id}: {e}")
            return []

    async def list_drive_items(self, drive_id: str, item_id: Optional[str] = None) -> List[SharePointItem]:
        """
        Lists items within a specific drive or folder.
        If item_id is None, lists items in the root of the drive.
        If item_id is provided, lists items within that folder.
        """
        if item_id:
            items_url = f"{MS_GRAPH_ENDPOINT}/drives/{drive_id}/items/{item_id}/children"
        else:
            items_url = f"{MS_GRAPH_ENDPOINT}/drives/{drive_id}/root/children"

        try:
            # Add select query parameter to get necessary fields, including file and folder info
            params = {"$select": "id,name,webUrl,createdDateTime,lastModifiedDateTime,size,file,folder,parentReference"}
            response_data = await self._make_graph_request(items_url, params=params)

            if response_data and "value" in response_data:
                items = [SharePointItem(**item) for item in response_data["value"]]
                return items
            return []
        except Exception as e:
            logger.error(f"Error listing items in drive {drive_id} (item: {item_id}): {e}")
            return []

    async def download_file_content(self, drive_id: str, item_id: str) -> Optional[bytes]:
        """Downloads the content of a file from a SharePoint drive."""
        download_url_endpoint = f"{MS_GRAPH_ENDPOINT}/drives/{drive_id}/items/{item_id}/content"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(download_url_endpoint, headers=self.headers, follow_redirects=True)
                response.raise_for_status()
                return response.content
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error downloading file {item_id} from drive {drive_id}: {e.response.status_code} - {e.response.text}")
                return None
            except httpx.RequestError as e:
                logger.error(f"Request error downloading file {item_id} from drive {drive_id}: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error downloading file {item_id} from drive {drive_id}: {e}")
                return None

    # --- Placeholder for processing/embedding ---
    # This part will likely need the TaskManager and integration
    # with embedding/knowledge base services, similar to OutlookService

    async def process_file_content(self, drive_id: str, item_id: str, filename: str):
        """
        Placeholder function to download, parse, and process file content.
        This should eventually integrate with parsing and knowledge base services.
        """
        logger.info(f"Starting processing for file: {filename} (ID: {item_id}) in drive {drive_id}")
        content = await self.download_file_content(drive_id, item_id)
        if content:
            logger.info(f"Successfully downloaded {len(content)} bytes for {filename}. Need to implement parsing and embedding.")
            # 1. Determine file type (e.g., from filename extension)
            # 2. Call appropriate parser (from services.parser)
            # 3. Call embedding service (from services.embedder)
            # 4. Call knowledge base service (from services.knowledge_service)
            # This will likely happen in a background task managed by TaskManager
            pass
        else:
            logger.warning(f"Could not download content for file: {filename}") 