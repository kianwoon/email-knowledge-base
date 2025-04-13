import httpx
from typing import List, Dict, Any, Optional
from app.models.sharepoint import SharePointSite, SharePointDrive, SharePointItem, UsedInsight, RecentDriveItem
import logging
import base64
from fastapi import HTTPException
from pydantic import ValidationError
from datetime import datetime

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
        # Specify desired fields using $select
        select_fields = "id,displayName,name,webUrl"
        sites_url = f"{MS_GRAPH_ENDPOINT}/sites?search=*&$select={select_fields}"
        logger.info(f"Attempting to fetch accessible sites using: {sites_url}")
        try:
            response_data = await self._make_graph_request(sites_url)
            if response_data and "value" in response_data:
                # Log the first few raw site objects from the response for inspection
                logger.info(f"Raw site data from Graph API (first 5): {response_data['value'][:5]}")
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
                processed_items = []
                # +++ Add Logging: Log raw items from API +++
                logger.debug(f"list_drive_items raw response for drive {drive_id}, folder {item_id} (first 5): {response_data['value'][:5]}")
                
                for item in response_data["value"]:
                    item_data = item
                    # Log each raw item being processed
                    logger.debug(f"list_drive_items processing raw item: {item_data}")
                    
                    is_folder = item_data.get("folder") is not None
                    is_file = item_data.get("file") is not None 
                    # +++ Add Logging: Show determined flags +++
                    logger.debug(f"list_drive_items determined flags for item {item_data.get('id')}: is_folder={is_folder}, is_file={is_file}")
                    
                    try:
                        processed_items.append(SharePointItem(
                            **item, 
                            is_folder=is_folder, 
                            is_file=is_file
                        ))
                    except ValidationError as e:
                        logger.warning(f"Validation error processing drive item {item.get('id')}: {e}. Raw: {item}")
                return processed_items
            else:
                # Log if no 'value' key is found
                logger.debug(f"list_drive_items response for drive {drive_id}, folder {item_id} contained no 'value' key or was empty.")
            return []
        except Exception as e:
            logger.error(f"Error listing items in drive {drive_id} (item: {item_id}): {e}")
            return []

    async def get_item_details(self, drive_id: str, item_id: str) -> Optional[SharePointItem]:
        """Gets the metadata for a single drive item by its ID."""
        item_url = f"{MS_GRAPH_ENDPOINT}/drives/{drive_id}/items/{item_id}"
        params = {"$select": "id,name,webUrl,createdDateTime,lastModifiedDateTime,size,file,folder,parentReference"}
        logger.info(f"Fetching details for item {item_id} in drive {drive_id}")
        try:
            item_data = await self._make_graph_request(item_url, params=params)
            if item_data:
                # CORRECTED: Explicitly check for folder and file facets
                is_folder = item_data.get("folder") is not None
                is_file = item_data.get("file") is not None
                try:
                    return SharePointItem(
                        **item_data, 
                        is_folder=is_folder, 
                        is_file=is_file
                    )
                except ValidationError as e:
                    logger.warning(f"Validation error processing item details for {item_id}: {e}. Raw: {item_data}")
                    return None
            return None
        except Exception as e:
            logger.error(f"Error getting details for item {item_id} in drive {drive_id}: {e}")
            return None

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

    # --- Insight Methods --- 

    async def get_quick_access_items(self) -> List[UsedInsight]:
        """Retrieves items the user has recently used (viewed/modified)."""
        # Select fields we need for the model
        select_fields = "id,resourceVisualization,resourceReference"
        # Top parameter limits the number of results (e.g., top 20)
        quick_access_url = f"{MS_GRAPH_ENDPOINT}/me/insights/used?$select={select_fields}&$top=20"
        logger.info(f"Fetching quick access items: {quick_access_url}")
        try:
            response_data = await self._make_graph_request(quick_access_url)
            if response_data and "value" in response_data:
                # Log raw response for debugging if needed
                # logger.debug(f"Raw quick access response: {response_data['value']}")
                items = [UsedInsight(**item) for item in response_data["value"]]
                logger.info(f"Found {len(items)} quick access items.")
                return items
            logger.info("No quick access items found in the response.")
            return []
        except Exception as e:
            logger.error(f"Error fetching quick access items: {e}", exc_info=True)
            return []

    # +++ Method updated to use /me/drive/root/children +++
    async def get_recent_drive_items(self, token: str, top: int = 50) -> list[RecentDriveItem]:
        """Fetches items from the user's OneDrive root, sorted by last modified date."""
        # Use the /me/drive/root/children endpoint
        graph_url = f"{MS_GRAPH_ENDPOINT}/me/drive/root/children"
        params = {
            "$select": "id,name,webUrl,lastModifiedDateTime,lastModifiedBy,size,file,folder", # Select fields for RecentDriveItem
            "$orderby": "lastModifiedDateTime desc", # Order by modification date
            "$top": top
        }

        logger.info(f"Fetching OneDrive root items: {graph_url} with params {params}")

        try:
            async with httpx.AsyncClient(headers=self.headers) as client: 
                response = await client.get(graph_url, params=params)
                response.raise_for_status()
                data = response.json()

            items_data = data.get("value", [])
            logger.info(f"Found {len(items_data)} items in OneDrive root.")

            # Directly process items into RecentDriveItem (structure should match)
            processed_items = []
            for item_data in items_data:
                try:
                    # Directly validate, assuming the response matches the model fields
                    processed_items.append(RecentDriveItem.model_validate(item_data))
                except ValidationError as e:
                    # Log if validation fails, indicates API response mismatch or incomplete data
                    logger.warning(f"Validation error for OneDrive root item {item_data.get('id')}: {e}. Raw: {item_data}")
                    # Skip invalid items
                    pass 

            logger.info(f"Successfully processed {len(processed_items)} OneDrive items into RecentDriveItems.")
            return processed_items

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching from {graph_url}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Error fetching OneDrive items from Microsoft Graph: {e.response.text}")
        except Exception as e:
            logger.error(f"Unexpected error fetching from {graph_url}: {e}")
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred while fetching OneDrive items: {e}")
    # --- End New Method --- 

    async def search_drive(self, drive_id: str, query: str) -> List[SharePointItem]:
        """Searches for items within a specific drive."""
        search_url = f"{MS_GRAPH_ENDPOINT}/drives/{drive_id}/root/search(q='{query}')"
        params = {"$select": "id,name,webUrl,createdDateTime,lastModifiedDateTime,size,file,folder,parentReference"}
        try:
            response_data = await self._make_graph_request(search_url, params=params)
            if response_data and "value" in response_data:
                processed_items = []
                for item in response_data["value"]:
                    # Refined logic: Check for folder facet existence
                    item_data = item
                    is_folder = item_data.get("folder") is not None
                    is_file = not is_folder # If not a folder, it's a file
                    # Create the SharePointItem with the determined flags
                    try:
                        processed_items.append(SharePointItem(
                            **item, # Pass existing fields
                            is_folder=is_folder, 
                            is_file=is_file
                        ))
                    except ValidationError as e:
                        logger.warning(f"Validation error processing search result item {item.get('id')}: {e}. Raw: {item}")
                return processed_items # Return the processed list
            return []
        except Exception as e:
            logger.error(f"Error searching drive {drive_id}: {e}")
            return []