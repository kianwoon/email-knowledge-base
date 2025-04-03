import httpx
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from app.models.email import EmailPreview, EmailContent, EmailAttachment
from app.config import settings

# Set up logger
logger = logging.getLogger(__name__)

class OutlookService:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "ConsistencyLevel": "eventual",
            "Prefer": "outlook.timezone=\"UTC\""
        }
        self.client = httpx.AsyncClient(
            base_url="https://graph.microsoft.com/v1.0",
            headers=self.headers,
            timeout=30.0
        )

    async def get_user_info(self) -> Dict[str, Any]:
        """Get user information from Microsoft Graph API"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def get_user_photo(self) -> Optional[str]:
        """Get user profile photo from Microsoft Graph API
        
        Returns:
            Optional[str]: Base64 encoded photo or None if no photo is available
        """
        async with httpx.AsyncClient() as client:
            try:
                # Try to get the photo
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/photo/$value",
                    headers=self.headers
                )
                response.raise_for_status()
                
                # Convert photo to base64
                import base64
                photo_base64 = base64.b64encode(response.content).decode('utf-8')
                return f"data:image/jpeg;base64,{photo_base64}"
            except Exception as e:
                print(f"Error getting user photo: {str(e)}")
                return None

    async def get_email_folders(self) -> List[Dict[str, Any]]:
        """Get list of email folders from Outlook, including hierarchy."""
        logger.info("[FOLDERS] Fetching all folders to build hierarchy...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/mailFolders",
                    params={
                        # Remove filter to get all folders
                        # "$filter": "parentFolderId eq null", 
                        "$select": "id,displayName,parentFolderId", # Select fields needed for hierarchy
                        "$top": 500, # Increase top limit further to fetch more folders if needed
                        "$orderby": "displayName"
                    },
                    headers=self.headers
                )
                response.raise_for_status() # Raise HTTPStatusError for bad responses
                data = response.json()
                folders = data.get("value", [])
                logger.info(f"[FOLDERS] Fetched {len(folders)} total folders.")

                # --- Corrected Hierarchy Building Logic --- 
                if not folders:
                    return [] # Return early if no folders fetched
                    
                folder_map = {folder["id"]: folder for folder in folders}
                
                # Initialize children and link parents that ARE in the map
                for folder_id, folder in folder_map.items():
                    folder["children"] = []
                    parent_id = folder.get("parentFolderId")
                    if parent_id and parent_id in folder_map:
                        folder_map[parent_id]["children"].append(folder)
                        
                # Identify root folders (no parent OR parent not in the fetched map)
                root_folders = []
                for folder_id, folder in folder_map.items():
                    parent_id = folder.get("parentFolderId")
                    if not parent_id or parent_id not in folder_map:
                        root_folders.append(folder)
                # --- End Corrected Hierarchy Building Logic --- 

                # Optional: Sort children recursively (can be removed if order doesn't matter)
                def sort_folders_recursively(folder_list):
                    folder_list.sort(key=lambda x: x.get("displayName", "").lower())
                    for f in folder_list:
                        if f["children"]:
                            sort_folders_recursively(f["children"])
                
                sort_folders_recursively(root_folders)
                # --- End Hierarchy Building Logic --- 

                logger.info(f"[FOLDERS] Built hierarchy with {len(root_folders)} root folders.")
                return root_folders # Return only the root folders, which contain their children

        except httpx.HTTPStatusError as e:
            logger.error(f"[FOLDERS] Graph API HTTP error fetching folders: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise HTTPException(status_code=e.response.status_code, detail=f"Error fetching folders: {e.response.text}")
        except Exception as e:
            logger.error(f"[FOLDERS] Unexpected error fetching folders: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error fetching folders")

    def sanitize_keyword(self, keyword: str) -> str:
        # Remove any quotes and escape special characters
        return keyword.replace("'", "").replace('"', "")

    async def get_email_preview(
        self,
        folder_id: str = None,
        keywords: List[str] = None,
        next_link: str = None,
        per_page: int = 10,
        start_date: str = None,
        end_date: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Get email previews. Uses $search + manual filter for keywords, or $filter for non-keyword queries."""
        
        logger.info(f"[INPUT] Received raw input: folder_id={folder_id}, keywords={keywords}, next_link={next_link}, per_page={per_page}, start_date={start_date}, end_date={end_date}")
        
        try:
            # --- Handle pagination using next_link --- 
            if next_link:
                logger.info(f"[PAGINATION] Using next_link: {next_link}")
                
                # Determine if manual filtering needed based on *this pagination request's* keywords
                pagination_use_search = bool(keywords and any(kw.strip() for kw in keywords))
                logger.info(f"[PAGINATION] Mode check: pagination_use_search={pagination_use_search}")

                async with httpx.AsyncClient(base_url="https://graph.microsoft.com", timeout=30.0) as client:
                    response = await client.get(
                        next_link,
                        headers={ 
                            "Authorization": f"Bearer {self.access_token}",
                            "Accept": "application/json",
                            "ConsistencyLevel": "eventual",
                            "Prefer": "outlook.timezone=\"UTC\""
                        }
                    )
                response.raise_for_status()
                data = response.json()
                logger.info(f"[PAGINATION] Next link response data keys: {data.keys()}")

                items_raw = data.get("value", [])
                next_link_from_response = data.get("@odata.nextLink")
                odata_count = data.get("@odata.count") # Get count if provided by API

                # --- Manual Filtering for Pagination (if keywords provided in this request) ---
                filtered_items = []
                if pagination_use_search:
                    logger.info("[PAGINATION-FILTER] Applying manual filtering based on pagination request parameters.")
                    # Use filters provided in *this* pagination request
                    dt_start_obj, dt_end_obj = self._parse_dates_for_filtering(start_date, end_date)
                    for item in items_raw:
                        if self._passes_manual_filter(item, folder_id, dt_start_obj, dt_end_obj):
                            filtered_items.append(item)
                    logger.info(f"[PAGINATION-FILTER] Filtered {len(items_raw)} items down to {len(filtered_items)}.")
                else:
                    # No manual filtering needed if no keywords in this pagination request
                    filtered_items = items_raw
                # --- End Manual Filtering --- 

                # Determine Total Count for Pagination Response
                total_count_paginated = 0
                # Base decision on pagination_use_search determined for this specific call
                if pagination_use_search and odata_count is None:
                    total_count_paginated = -1 if bool(next_link_from_response) else len(filtered_items)
                else:
                    total_count_paginated = odata_count if odata_count is not None else len(filtered_items)

                logger.info(f"[RESPONSE-PAGINATION] Items: {len(filtered_items)}, Total: {total_count_paginated}, Has Next: {bool(next_link_from_response)}")
                return {
                    "items": [self._format_email_preview(email) for email in filtered_items],
                    "total": total_count_paginated,
                    "next_link": next_link_from_response
                }
            # --- End pagination handling ---

            # --- Build and execute initial request (Search or Filter) ---
            # Determine mode based on initial request's keywords
            initial_use_search_mode = bool(keywords and any(kw.strip() for kw in keywords))
            logger.info(f"[MODE-INITIAL] initial_use_search_mode={initial_use_search_mode}")
            
            select_fields = "id,subject,sender,receivedDateTime,hasAttachments,importance,bodyPreview,parentFolderId"
            base_url = "/me/messages"
            params = {
                "$select": select_fields,
                "$count": "true",
                "$top": per_page 
            }
            headers = {
                **self.headers, # Base headers
                "ConsistencyLevel": "eventual" # Required for $filter/$orderby/$search
            }
            
            final_filter_str = None # Only used in non-search mode

            if initial_use_search_mode:
                logger.info("[QUERY-BUILD] Building $search query.")
                search_terms = [f'\"{self.sanitize_keyword(kw)}\"' for kw in keywords if kw.strip()]
                search_query = " OR ".join(search_terms)
                params["$search"] = search_query
                logger.info(f"[PARAM] Using $search: {search_query}")
            else:
                logger.info("[QUERY-BUILD] Building $filter query (no keywords).")
                filter_parts = []
                if folder_id:
                    safe_folder_id = folder_id.replace("'", "''") 
                    filter_parts.append(f"parentFolderId eq '{safe_folder_id}'")
                graph_api_start_date, graph_api_end_date = self._parse_dates_for_graph_filter(start_date, end_date)
                if graph_api_start_date:
                    filter_parts.append(f"receivedDateTime ge {graph_api_start_date}")
                if graph_api_end_date:
                    filter_parts.append(f"receivedDateTime le {graph_api_end_date}")
                final_filter_str = " and ".join(filter_parts) if filter_parts else None
                if final_filter_str:
                    params["$filter"] = final_filter_str
                    logger.info(f"[PARAM] Using $filter: {final_filter_str}")
                params["$orderby"] = "receivedDateTime desc"
                logger.info(f"[PARAM] Using $orderby: receivedDateTime desc")

            # --- Make the API Request (remains the same) --- 
            logger.info(f"[REQUEST] Making initial request to {base_url} (Mode: {'Search' if initial_use_search_mode else 'Filter'})")
            logger.info(f"[REQUEST] Params: {params}")
            response = await self.client.get(base_url, params=params, headers=headers)
            logger.info(f"[RESPONSE] URL Requested: {response.request.url}")
            response.raise_for_status()
            data = response.json()
            logger.debug(f"[RESPONSE] Data received: {data}")
            # --- End Make the API Request --- 

            # --- Process Response --- 
            items_raw = data.get("value", [])
            odata_count = data.get("@odata.count")
            next_link_from_response = data.get("@odata.nextLink")

            # --- Manual Filtering (if in initial search mode) ---
            filtered_items = []
            if initial_use_search_mode:
                logger.info("[MANUAL-FILTER] Applying manual filtering to initial search results.")
                # Use filters from the initial request
                dt_start_obj, dt_end_obj = self._parse_dates_for_filtering(start_date, end_date)
                for item in items_raw:
                     if self._passes_manual_filter(item, folder_id, dt_start_obj, dt_end_obj):
                         filtered_items.append(item)
                logger.info(f"[MANUAL-FILTER] Filtered {len(items_raw)} items down to {len(filtered_items)}.")
            else:
                filtered_items = items_raw
            # --- End Manual Filtering --- 

            # Determine Total Count based on initial mode
            total_count = 0
            if initial_use_search_mode and odata_count is None:
                total_count = -1 if bool(next_link_from_response) else len(filtered_items)
                logger.warning(f"[COUNT] Search mode & @odata.count missing. Setting total to {total_count} based on nextLink presence.")
            else:
                total_count = odata_count if odata_count is not None else len(filtered_items)
                logger.info(f"[COUNT] Using @odata.count ({odata_count}) or filtered item count ({len(filtered_items)}) for total: {total_count}")

            logger.info(f"[RESPONSE] Status Code: {response.status_code}")
            logger.info(f"[RESPONSE] Items returned (after filtering): {len(filtered_items)}")
            logger.info(f"[RESPONSE] @odata.count reported by API: {odata_count}")
            logger.info(f"[RESPONSE] Final Total Count determined: {total_count}")
            logger.info(f"[RESPONSE] Next Link present: {bool(next_link_from_response)}")

            return {
                "items": [self._format_email_preview(item) for item in filtered_items],
                "total": total_count,
                "next_link": next_link_from_response
            }

        # --- Error Handling (remains the same) --- 
        except httpx.RequestError as e:
             logger.error(f"HTTP request error to Graph API: {e}")
             raise HTTPException(status_code=503, detail=f"Error communicating with Microsoft Graph: {e}")
        except httpx.HTTPStatusError as e: 
            error_body = e.response.text
            logger.error(f"Graph API HTTP error: {e.response.status_code} - Response: {error_body}")
            detail_message = f"Error fetching emails: Status {e.response.status_code}"
            try:
                 error_data = e.response.json()
                 detail_message = error_data.get('error', {}).get('message', detail_message)
            except Exception:
                 pass 
            raise HTTPException(status_code=e.response.status_code, detail=detail_message)
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error during email preview processing: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Internal server error during email preview processing: {str(e)}")
        # --- End Error Handling --- 

    # --- Helper methods --- 
    def _parse_dates_for_graph_filter(self, start_date: str, end_date: str) -> (Optional[str], Optional[str]):
        """Parses dates into ISO format strings suitable for Graph API $filter."""
        graph_api_start_date = None
        graph_api_end_date = None
        if start_date:
            try:
                dt_start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                graph_api_start_date = dt_start.isoformat().replace("+00:00", "Z")
            except ValueError:
                logger.error(f"[DATE-PARSE] Invalid start_date format: {start_date}. Ignoring.")
        if end_date:
            try:
                dt_end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                graph_api_end_date = dt_end.isoformat().replace("+00:00", "Z")
            except ValueError:
                logger.error(f"[DATE-PARSE] Invalid end_date format: {end_date}. Ignoring.")
        return graph_api_start_date, graph_api_end_date

    def _parse_dates_for_filtering(self, start_date: str, end_date: str) -> (Optional[datetime], Optional[datetime]):
        """Parses dates into datetime objects suitable for manual comparison."""
        dt_start_obj = None
        dt_end_obj = None
        if start_date:
            try:
                dt_start_obj = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                logger.error(f"[DATE-PARSE] Invalid start_date format: {start_date}. Cannot use for manual filter.")
        if end_date:
            try:
                # Use end of day for inclusive filtering
                dt_end_obj = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            except ValueError:
                 logger.error(f"[DATE-PARSE] Invalid end_date format: {end_date}. Cannot use for manual filter.")
        return dt_start_obj, dt_end_obj

    def _passes_manual_filter(self, item: Dict, folder_id: Optional[str], dt_start: Optional[datetime], dt_end: Optional[datetime]) -> bool:
        """Checks if a single item passes manual folder and date filters."""
        # Folder Check
        if folder_id and item.get("parentFolderId") != folder_id:
            return False
        
        # Date Check
        received_date_str = item.get("receivedDateTime")
        if received_date_str:
            try:
                # Graph API returns ISO 8601 format (e.g., "2024-01-15T10:30:00Z")
                # We need to parse this and ensure it's timezone-aware (it should be UTC 'Z')
                received_dt = datetime.fromisoformat(received_date_str.replace('Z', '+00:00'))
                
                if dt_start and received_dt < dt_start:
                    return False
                if dt_end and received_dt > dt_end:
                    return False
            except Exception as e:
                logger.warning(f"[MANUAL-FILTER-DATE] Could not parse receivedDateTime '{received_date_str}': {e}. Item ID: {item.get('id')}")
                return False # Exclude if date cannot be parsed
        elif dt_start or dt_end: # If date filtering is active but item has no date
             logger.warning(f"[MANUAL-FILTER-DATE] Item missing receivedDateTime cannot be filtered. Item ID: {item.get('id')}")
             return False # Exclude if date filtering is needed but date is missing
        
        return True # Passed all checks

    def _format_email_preview(self, email: Dict) -> Dict:
        """Format email data into preview format."""
        try:
            return {
                "id": email["id"],
                "subject": email.get("subject", "(No subject)"),
                "sender": email["sender"]["emailAddress"]["address"],
                "received_date": email["receivedDateTime"],
                "has_attachments": email.get("hasAttachments", False),
                "importance": email.get("importance", "normal"),
                "snippet": email.get("bodyPreview", "")
            }
        except Exception as e:
            logger.error(f"Error formatting email preview: {str(e)}, Email data: {email}")
            raise

    async def get_email_content(self, email_id: str) -> EmailContent:
        """Get full email content by ID"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/messages/{email_id}",
                headers=self.headers
            )
            response.raise_for_status()
            email = response.json()
            
            # Get attachments if any
            attachments = []
            if email.get("hasAttachments"):
                attachments_response = await client.get(
                    f"https://graph.microsoft.com/v1.0/me/messages/{email_id}/attachments",
                    headers=self.headers
                )
                attachments_response.raise_for_status()
                attachments_data = attachments_response.json()
                
                for attachment in attachments_data.get("value", []):
                    attachments.append(EmailAttachment(
                        id=attachment["id"],
                        name=attachment["name"],
                        content_type=attachment["contentType"],
                        size=attachment["size"]
                    ))
            
            return EmailContent(
                id=email["id"],
                subject=email.get("subject", "(No subject)"),
                sender=email["sender"]["emailAddress"]["address"],
                received_date=email["receivedDateTime"],
                body=email.get("body", {}).get("content", ""),
                attachments=attachments
            )

    async def get_email_attachment(self, email_id: str, attachment_id: str) -> EmailAttachment:
        """Get email attachment by ID"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/messages/{email_id}/attachments/{attachment_id}",
                headers=self.headers
            )
            response.raise_for_status()
            attachment = response.json()
            
            return EmailAttachment(
                id=attachment["id"],
                name=attachment["name"],
                content_type=attachment["contentType"],
                size=attachment["size"],
                content=attachment.get("contentBytes")  # Base64 encoded content
            )