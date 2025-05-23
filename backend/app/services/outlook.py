import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
import asyncio
import base64
import binascii # For Base64 decoding errors
from dateutil.parser import isoparse # Added import
from pydantic import ValidationError # Added import
import json
import os

from app.models.email import EmailPreview, EmailContent, EmailAttachment, EmailFilter
from app.config import settings

# Set up logger
logger = logging.getLogger(__name__)

class OutlookService:
    def __init__(self, access_token: str):
        self.access_token = access_token
        # Get timezone from environment variable, fall back to Asia/Singapore if not set
        timezone_preference = os.getenv("TZ", "Asia/Singapore")
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "ConsistencyLevel": "eventual",
            "Prefer": f"outlook.timezone=\"{timezone_preference}\""
        }
        self.client = httpx.AsyncClient(
            base_url=settings.MS_GRAPH_BASE_URL,
            headers=self.headers,
            timeout=settings.MS_GRAPH_TIMEOUT_SECONDS  # Use the configurable timeout setting
        )

    async def get_user_info(self) -> Dict[str, Any]:
        """Get user information from Microsoft Graph API"""
        response = await self.client.get("/me")
        response.raise_for_status()
        return response.json()

    async def get_user_photo(self) -> Optional[str]:
        """Get user profile photo from Microsoft Graph API
        
        Returns:
            Optional[str]: Base64 encoded photo or None if no photo is available
        """
        try:
            response = await self.client.get("/me/photo/$value")
            response.raise_for_status()
            
            import base64
            photo_base64 = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/jpeg;base64,{photo_base64}"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"No profile photo found for user.")
                return None
            else:
                logger.error(f"HTTP error getting user photo: {e.response.status_code} - {e.response.text}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error getting user photo: {str(e)}")
            return None

    async def get_email_folders(self) -> List[Dict[str, Any]]:
        """Get list of email folders from Outlook, including hierarchy."""
        logger.info("[FOLDERS] Fetching all folders to build hierarchy...")
        try:
            response = await self.client.get(
                "/me/mailFolders",
                params={
                    "$select": "id,displayName,parentFolderId",
                    "$top": 500,
                    "$orderby": "displayName"
                }
            )
            response.raise_for_status()
            data = response.json()
            folders = data.get("value", [])
            logger.info(f"[FOLDERS] Fetched {len(folders)} total folders.")

            if not folders:
                return []
            
            folder_map = {folder["id"]: folder for folder in folders}
            
            for folder_id, folder in folder_map.items():
                folder["children"] = []
                parent_id = folder.get("parentFolderId")
                if parent_id and parent_id in folder_map:
                    folder_map[parent_id]["children"].append(folder)
                    
            root_folders = []
            for folder_id, folder in folder_map.items():
                parent_id = folder.get("parentFolderId")
                if not parent_id or parent_id not in folder_map:
                    root_folders.append(folder)
            
            def sort_folders_recursively(folder_list):
                folder_list.sort(key=lambda x: x.get("displayName", "").lower())
                for f in folder_list:
                    if f["children"]:
                        sort_folders_recursively(f["children"])
            
            sort_folders_recursively(root_folders)

            logger.info(f"[FOLDERS] Built hierarchy with {len(root_folders)} root folders.")
            return root_folders

        except httpx.HTTPStatusError as e:
            logger.error(f"[FOLDERS] Graph API HTTP error fetching folders: {e.response.status_code} - {e.response.text}", exc_info=True)
            raise HTTPException(status_code=e.response.status_code, detail=f"Error fetching folders: {e.response.text}")
        except Exception as e:
            logger.error(f"[FOLDERS] Unexpected error fetching folders: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error fetching folders")

    async def get_best_sent_folder_id(self) -> Optional[str]:
        """Find the 'Sent' folder with the most emails and return its ID."""
        logger.info("[SENT-FOLDER] Searching for best Sent Items folder...")
        try:
            # Fetch all folders with their total item counts
            response = await self.client.get(
                "/me/mailFolders",
                params={
                    "$select": "id,displayName,totalItemCount,childFolderCount",
                    "$top": 1000  # Increased to ensure we get all folders
                }
            )
            response.raise_for_status()
            data = response.json()
            folders = data.get("value", [])
            
            # Find all folders whose name contains 'sent' (case-insensitive)
            sent_folders = []
            exact_sent_items_folder = None  # Special folder for the exact "Sent Items" match
            large_sent_folder = None        # Special folder for any sent folder with significant emails
            min_significant_emails = 1000   # Threshold for considering a folder "significant"
            
            for folder in folders:
                display_name = folder.get("displayName", "").lower()
                item_count = folder.get("totalItemCount", 0)
                
                if "sent" in display_name:
                    folder_info = {
                        "id": folder.get("id"),
                        "displayName": folder.get("displayName"),
                        "totalItemCount": item_count,
                        "childFolderCount": folder.get("childFolderCount", 0)
                    }
                    sent_folders.append(folder_info)
                    
                    # Check for exact "sent items" match (standard folder name)
                    if display_name == "sent items":
                        exact_sent_items_folder = folder_info
                        logger.info(f"[SENT-FOLDER] Found exact 'Sent Items' folder: ID {folder_info['id']}, Count: {item_count}")
                    
                    # Check for any sent folder with significant emails
                    if item_count >= min_significant_emails and (large_sent_folder is None or item_count > large_sent_folder["totalItemCount"]):
                        large_sent_folder = folder_info
                        logger.info(f"[SENT-FOLDER] Found large sent folder: '{folder_info['displayName']}', ID {folder_info['id']}, Count: {item_count}")
            
            logger.info(f"[SENT-FOLDER] Found {len(sent_folders)} potential sent folders: {[f['displayName'] for f in sent_folders]}")
            
            if not sent_folders:
                logger.warning("[SENT-FOLDER] No sent folders found")
                return None
            
            # Decision logic for which sent folder to use:
            # 1. If we found a large sent folder with significant emails, use that
            if large_sent_folder and large_sent_folder["totalItemCount"] >= min_significant_emails:
                logger.info(f"[SENT-FOLDER] Selected large sent folder: '{large_sent_folder['displayName']}' with {large_sent_folder['totalItemCount']} emails")
                return large_sent_folder["id"]
                
            # 2. If we found the exact "Sent Items" folder, use that
            if exact_sent_items_folder:
                logger.info(f"[SENT-FOLDER] Selected exact 'Sent Items' folder with {exact_sent_items_folder['totalItemCount']} emails")
                return exact_sent_items_folder["id"]
                
            # 3. Otherwise, pick the one with the most emails
            sent_folders.sort(key=lambda x: x.get("totalItemCount", 0), reverse=True)
            best_folder = sent_folders[0]
            logger.info(f"[SENT-FOLDER] Selected best folder by count: {best_folder['displayName']} (ID: {best_folder['id']}, Count: {best_folder['totalItemCount']})")
            return best_folder["id"]
        
        except httpx.HTTPStatusError as e:
            logger.error(f"[SENT-FOLDER] HTTP error getting sent folder: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"[SENT-FOLDER] Unexpected error finding sent folder: {str(e)}")
            return None

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
            if next_link:
                logger.info(f"[PAGINATION] Using next_link: {next_link}")
                
                pagination_use_search = bool(keywords and any(kw.strip() for kw in keywords))
                logger.info(f"[PAGINATION] Mode check: pagination_use_search={pagination_use_search}")

                async with httpx.AsyncClient(timeout=settings.MS_GRAPH_TIMEOUT_SECONDS) as temp_client:
                    response = await temp_client.get(
                        next_link,
                        headers=self.headers
                    )
                response.raise_for_status()
                data = response.json()
                logger.info(f"[PAGINATION] Next link response data keys: {data.keys()}")

                items_raw = data.get("value", [])
                next_link_from_response = data.get("@odata.nextLink")
                odata_count = data.get("@odata.count")

                filtered_items = []
                if pagination_use_search:
                    logger.info("[PAGINATION-FILTER] Applying manual filtering based on pagination request parameters.")
                    dt_start_obj, dt_end_obj = self._parse_dates_for_filtering(start_date, end_date)
                    for item in items_raw:
                        if self._passes_manual_filter(item, folder_id, dt_start_obj, dt_end_obj):
                            filtered_items.append(item)
                    logger.info(f"[PAGINATION-FILTER] Filtered {len(items_raw)} items down to {len(filtered_items)}.")
                else:
                    filtered_items = items_raw

                total_count_paginated = 0
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

            initial_use_search_mode = bool(keywords and any(kw.strip() for kw in keywords))
            logger.info(f"[MODE-INITIAL] initial_use_search_mode={initial_use_search_mode}")
            
            select_fields = "id,subject,sender,receivedDateTime,hasAttachments,importance,bodyPreview,parentFolderId"
            base_path = "/me/messages"
            params = {
                "$select": select_fields,
                "$count": "true",
                "$top": per_page 
            }
            
            final_filter_str = None

            if initial_use_search_mode:
                logger.info("[QUERY-BUILD] Building $search query.")
                search_terms = [f'\"{self.sanitize_keyword(kw)}\"' for kw in keywords if kw.strip()]
                search_query = " OR ".join(search_terms)
                params["$search"] = search_query
                logger.info(f"[PARAM] Using $search: {search_query}")
            else:
                logger.info("[QUERY-BUILD] Building $filter query (no keywords).")
                filter_parts = []
                if folder_id and folder_id.strip():
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

            logger.info(f"[REQUEST] Making initial request to {base_path} (Mode: {'Search' if initial_use_search_mode else 'Filter'})")
            logger.info(f"[REQUEST] Params: {params}")
            response = await self.client.get(base_path, params=params)
            logger.info(f"[RESPONSE] URL Requested: {response.request.url}")
            response.raise_for_status()
            data = response.json()
            logger.debug(f"[RESPONSE] Data received: {data}")

            # Process items and potentially filter
            items_raw = data.get("value", [])
            filtered_items = []

            if initial_use_search_mode:
                logger.info("[RESPONSE-FILTER] Applying manual filtering after $search.")
                dt_start_obj, dt_end_obj = self._parse_dates_for_filtering(start_date, end_date)
                for item in items_raw:
                    if self._passes_manual_filter(item, folder_id, dt_start_obj, dt_end_obj):
                        filtered_items.append(item)
                logger.info(f"[RESPONSE-FILTER] Filtered {len(items_raw)} items down to {len(filtered_items)}.")
            else:
                filtered_items = items_raw

            next_link_from_response = data.get("@odata.nextLink")
            odata_count = data.get("@odata.count")

            total_count = 0
            if initial_use_search_mode and odata_count is None:
                total_count = -1 if bool(next_link_from_response) else len(filtered_items)
                logger.warning(f"[TOTAL-COUNT] $search mode: Total count estimated as {total_count} based on nextLink presence.")
            else:
                total_count = odata_count if odata_count is not None else len(filtered_items)
                logger.info(f"[TOTAL-COUNT] $filter mode or count available: Total count set to {total_count}.")
            
            logger.info(f"[RESPONSE-FINAL] Items: {len(filtered_items)}, Total: {total_count}, Has Next: {bool(next_link_from_response)}")

            return_dict = {
                "items": [self._format_email_preview(email) for email in filtered_items],
                "total": total_count,
                "next_link": next_link_from_response
            }
            logger.info(f"[SERVICE DICT CHECK] Service is returning dict with next_link: {return_dict.get('next_link')}")

            return return_dict

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
                dt_end_obj = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            except ValueError:
                 logger.error(f"[DATE-PARSE] Invalid end_date format: {end_date}. Cannot use for manual filter.")
        return dt_start_obj, dt_end_obj

    def _passes_manual_filter(self, item: Dict, folder_id: Optional[str], dt_start: Optional[datetime], dt_end: Optional[datetime]) -> bool:
        """Checks if a single item passes manual folder and date filters."""
        if folder_id and folder_id.strip() and item.get("parentFolderId") != folder_id:
            return False
        
        received_date_str = item.get("receivedDateTime")
        if received_date_str:
            try:
                received_dt = datetime.fromisoformat(received_date_str.replace('Z', '+00:00'))
                
                if dt_start and received_dt < dt_start:
                    return False
                if dt_end and received_dt > dt_end:
                    return False
            except Exception as e:
                logger.warning(f"[MANUAL-FILTER-DATE] Could not parse receivedDateTime '{received_date_str}': {e}. Item ID: {item.get('id')}")
                return False
        elif dt_start or dt_end:
             logger.warning(f"[MANUAL-FILTER-DATE] Item missing receivedDateTime cannot be filtered. Item ID: {item.get('id')}")
             return False
        
        return True

    def _format_email_preview(self, email: Dict) -> Dict:
        """Helper to format a single email dictionary into the desired preview structure."""
        try:
            # --- Validate/Format Date --- 
            received_date_str = email.get("receivedDateTime")
            formatted_date = None
            if received_date_str:
                try:
                    # Attempt to parse to ensure it's valid ISO format
                    # datetime.fromisoformat handles Z for UTC correctly
                    dt_obj = datetime.fromisoformat(received_date_str.replace('Z', '+00:00')) 
                    # Return the original string if valid, as JS can parse ISO 8601
                    formatted_date = received_date_str 
                except ValueError:
                    logger.warning(f"Could not parse receivedDateTime '{received_date_str}' for email ID {email.get('id')}. Sending null.")
                    formatted_date = None # Send null if invalid
            # --- End Validate/Format Date ---

            # --- FIXED: Preserve the original sender structure ---
            # Pass the entire sender object directly through to the frontend
            # This ensures we keep the expected nested structure: { emailAddress: { name, address } }
            sender = email.get("sender")
            
            preview = {
                "id": email["id"],
                # Preserve the complete sender object structure
                "sender": sender,
                "subject": email.get("subject", "No Subject"),
                # Fix field name to match frontend expectations
                "bodyPreview": email.get("bodyPreview", ""),
                # Fix field name to match frontend expectations
                "receivedDateTime": formatted_date,
                "hasAttachments": email.get("hasAttachments", False),
                "importance": email.get("importance", "normal"),
                "isRead": email.get("isRead", True)
            }
            # --- END FIXED ---

            # Add optional fields if they exist
            # Directly preserve the original structure for recipients
            if "toRecipients" in email:
                preview["toRecipients"] = email["toRecipients"]
            if "ccRecipients" in email:
                preview["ccRecipients"] = email["ccRecipients"]
            
            return preview
        except KeyError as e:
            logger.error(f"KeyError formatting email preview: Missing key {e}, Email ID: {email.get('id')}")
            # Return a partial preview or skip this email
            return {
                 "id": email.get("id", "Unknown ID"), 
                 "error": f"Missing key: {e}"
            }
        except Exception as e:
            logger.error(f"Unexpected error formatting email preview for ID {email.get('id')}: {e}", exc_info=True)
            return {
                 "id": email.get("id", "Unknown ID"), 
                 "error": "Formatting error"
            }

    async def get_email_content(self, email_id: str) -> EmailContent:
        """Fetches full email content including body and attachments."""
        logger.info(f"[EMAIL-CONTENT] Fetching content for email ID: {email_id}")
        if not email_id:
            raise HTTPException(status_code=400, detail="Email ID cannot be empty")

        select_fields = "id,subject,sender,toRecipients,ccRecipients,bccRecipients,receivedDateTime,sentDateTime,body,hasAttachments,importance,parentFolderId,attachments,conversationId"
        expand_attachments = "attachments" # Expand attachments to get their details
        
        # Add retry logic for handling timeouts
        max_retries = 2
        retry_count = 0
        backoff_time = 1  # Start with 1 second

        while True:
            try:
                response = await self.client.get(
                    f"/me/messages/{email_id}",
                    params={"$select": select_fields, "$expand": expand_attachments}
                )
                logger.info(f"[EMAIL-CONTENT] Request URL: {response.request.url}")
                response.raise_for_status()
                data = response.json()
                logger.debug(f"[EMAIL-CONTENT] Raw data received for {email_id}: {data}") # Log raw data for debugging

                # Log the raw attachments data received
                raw_attachments = data.get('attachments', [])
                # logger.info(f"[EMAIL-CONTENT] Raw attachments data received for email {email_id}: {raw_attachments}") # OLD LOGGING
                # NEW: Log only metadata
                attachments_metadata = [
                    {k: v for k, v in att.items() if k != 'contentBytes'}
                    for att in raw_attachments
                ]
                # logger.info(f"[EMAIL-CONTENT] Attachments metadata received for email {email_id}: {attachments_metadata}") # Commented out to reduce verbosity
                
                # --- Helper function for extracting recipients ---
                def get_recipient_info(recipient_list):
                    if not recipient_list:
                        return []
                    return [{"name": r.get("emailAddress", {}).get("name"), 
                            "email": r.get("emailAddress", {}).get("address")} 
                            for r in recipient_list]

                # --- Helper function for parsing datetime ---
                def parse_datetime_to_utc(dt_str: Optional[str]) -> Optional[str]:
                    if not dt_str:
                        return None
                    try:
                        # Attempt to parse with different possible formats from Graph API
                        dt_obj = isoparse(dt_str)
                        # Ensure timezone is UTC
                        if dt_obj.tzinfo is None:
                            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                        else:
                            dt_obj = dt_obj.astimezone(timezone.utc)
                        # Format consistently
                        return dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z%z')
                    except ValueError as e:
                        logger.warning(f"[DATE-PARSE] Failed to parse datetime string '{dt_str}': {e}")
                        return None # Return None if parsing fails

                # --- Default value handling ---
                sender_info = data.get("sender", {}).get("emailAddress", {})
                sender_email = sender_info.get("address", "")
                sender_name = sender_info.get("name", "")

                recipients_raw = data.get("toRecipients", [])
                cc_recipients_raw = data.get("ccRecipients", [])
                attachments_raw = data.get("attachments", [])

                # --- Attachment processing ---
                attachments_list = []
                if data.get("hasAttachments"):
                    # logger.info(f"[EMAIL-CONTENT] Raw attachments data received for email {email_id}: {attachments_raw}") # <<< Commenting out this line
                    pass # Add pass to avoid syntax error after commenting
                if data.get("hasAttachments") and attachments_raw:
                    # logger.debug(f"[EMAIL-CONTENT] Processing {len(attachments_raw)} attachments found in raw data for email {email_id}.") # Commented out debug log
                    for att in attachments_raw:
                        # Skip inline attachments based on common indicators
                        if att.get('isInline'): 
                            # logger.debug(f"[ATTACHMENT-SKIP] Skipping inline attachment based on isInline flag: {att.get('name')} (ID: {att.get('id')})") # Commented out debug log
                            continue

                        # Handle potential missing contentBytes or other fields gracefully
                        content_type = att.get("contentType")
                        if not content_type:
                            logger.warning(f"[ATTACHMENT-WARN] Attachment '{att.get('name')}' for email '{email_id}' is missing 'contentType'. Setting to 'application/octet-stream'.")
                            content_type = "application/octet-stream" # Default if missing

                        # Check for contentBytes explicitly if it's expected but might be missing
                        # Note: Graph API sometimes doesn't return contentBytes in the initial message fetch even with $expand
                        # It often requires a separate call to get the attachment content itself.
                        # Here, we are creating the model based on metadata. Actual bytes are fetched later if needed.
                        has_content_bytes = 'contentBytes' in att

                        try:
                            attachment_obj = EmailAttachment(
                                id=att.get("id", ""), # Provide default empty string if id is missing
                                name=att.get("name", "Unnamed Attachment"), # Default name
                                content_type=content_type, # Use defaulted content_type
                                size=att.get("size", 0), # Default size 0
                                is_inline=att.get("isInline", False),
                                # content_bytes might not be present here; handle appropriately later
                                # content_bytes=att.get("contentBytes") # This line likely causes errors if not present
                            )
                            attachments_list.append(attachment_obj)
                            # logger.debug(f"[ATTACHMENT-ADD] Added attachment metadata: {attachment_obj.name} (ID: {attachment_obj.id})") # Commented out debug log
                        except ValidationError as ve:
                            logger.error(f"[ATTACHMENT-ERROR] Pydantic validation error for attachment in email {email_id}: {ve}. Attachment data: {att}")
                            # Decide how to handle validation errors: skip attachment, log and continue, etc.
                            # For now, we log and skip this attachment.
                        except Exception as ex:
                            logger.error(f"[ATTACHMENT-ERROR] Unexpected error processing attachment in email {email_id}: {ex}. Attachment data: {att}")
                            # Log and skip


                # --- Helper function to extract email addresses ---
                def get_email_address(recipient: Dict) -> Optional[str]:
                    return recipient.get("emailAddress", {}).get("address")

                # --- Prepare data for EmailContent ---
                recipients_list = [addr for r in recipients_raw if (addr := get_email_address(r))]
                cc_recipients_list = [addr for r in cc_recipients_raw if (addr := get_email_address(r))]
                
                # Determine if body is HTML
                body_content_type = data.get("body", {}).get("contentType", "html").lower()
                is_html_body = body_content_type == "html"

                # --- Final EmailContent Creation with Defaults ---
                try:
                    email_content = EmailContent(
                        id=data.get("id", ""), # Use 'id' field name
                        internet_message_id=data.get("internetMessageId"), # Add if needed, matches model field
                        subject=data.get("subject", ""), 
                        sender=sender_name, # Using sender_name for now
                        sender_email=sender_email, # Adding sender_email field
                        recipients=recipients_list, # Pass list of email strings
                        cc_recipients=cc_recipients_list, # Pass list of email strings
                        received_date=data.get("receivedDateTime"), # Pass raw string, let Pydantic handle if possible
                        sent_date=data.get("sentDateTime"), # Pass raw string, let Pydantic handle
                        body=data.get("body", {}).get("content", ""), # Use 'body' field name
                        is_html=is_html_body, # Set based on contentType
                        folder_id=data.get("parentFolderId", ""), 
                        # folder_name needs separate lookup if essential
                        attachments=attachments_list, 
                        importance=data.get("importance", "normal"), 
                    )
                    logger.info(f"[EMAIL-CONTENT] Successfully created EmailContent for {email_id}. Attachments processed: {len(attachments_list)}")
                    return email_content
                except ValidationError as ve:
                    logger.error(f"[EMAIL-CONTENT-ERROR] Pydantic validation error creating EmailContent for {email_id}: {ve}. Processed data snippet: sender={sender_email}, subject='{data.get('subject', '')[:50]}...'")
                    # Re-raise or handle as appropriate
                    raise HTTPException(status_code=500, detail=f"Data validation error processing email {email_id}: {ve}")
                except Exception as ex:
                    logger.error(f"[EMAIL-CONTENT-ERROR] Unexpected error creating EmailContent for {email_id}: {ex}")
                    raise HTTPException(status_code=500, detail=f"Unexpected error processing email {email_id}: {ex}")

                # Break out of the retry loop if successful
                break

            except httpx.ReadTimeout as e:
                # Specific handling for ReadTimeout
                retry_count += 1
                if retry_count <= max_retries:
                    logger.warning(f"[EMAIL-CONTENT] Read timeout fetching email {email_id}. Retrying ({retry_count}/{max_retries}) after {backoff_time}s delay...")
                    await asyncio.sleep(backoff_time)
                    backoff_time *= 2  # Progressive backoff
                else:
                    logger.error(f"[EMAIL-CONTENT] Read timeout fetching email {email_id} after {max_retries} retries.", exc_info=True)
                    raise HTTPException(status_code=500, detail=f"Internal server error fetching email content for {email_id}")

            except httpx.HTTPStatusError as e:
                error_body = e.response.text
                logger.error(f"[EMAIL-CONTENT] Graph API HTTP error fetching email {email_id}: {e.response.status_code} - {error_body}", exc_info=True)
                detail_message = f"Error fetching email content for ID {email_id}: Status {e.response.status_code}"
                raise HTTPException(status_code=e.response.status_code, detail=detail_message)
                
            except Exception as e:
                logger.error(f"[EMAIL-CONTENT] Unexpected error fetching email {email_id}: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Internal server error fetching email content for {email_id}")

    async def get_attachment_content(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """Fetches the raw content (bytes) of a specific attachment."""
        logger.info(f"[ATTACHMENT-CONTENT] Fetching content for message {message_id}, attachment {attachment_id}")
        if not message_id or not attachment_id:
            raise HTTPException(status_code=400, detail="Message ID and Attachment ID cannot be empty")

        endpoint = f"/me/messages/{message_id}/attachments/{attachment_id}"
        logger.info(f"Fetching attachment content from endpoint: {endpoint}")
        
        # Add retry logic for handling timeouts
        max_retries = 2
        retry_count = 0
        backoff_time = 1  # Start with 1 second
        
        while True:
            try:
                response = await self.client.get(endpoint)
                response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses
                
                data = response.json()
                
                content_bytes_b64 = data.get('contentBytes')
                
                if not content_bytes_b64:
                    logger.warning(f"No 'contentBytes' found in response for attachment {attachment_id} in message {message_id}.")
                    return None
                    
                if not isinstance(content_bytes_b64, str):
                     logger.warning(f"'contentBytes' is not a string for attachment {attachment_id} in message {message_id}. Type: {type(content_bytes_b64)}")
                     return None

                # Decode the Base64 string
                try:
                    decoded_bytes = base64.b64decode(content_bytes_b64)
                    logger.info(f"Successfully decoded {len(decoded_bytes)} bytes for attachment {attachment_id}.")
                    return decoded_bytes
                except binascii.Error as decode_error:
                    logger.error(f"Failed to decode Base64 contentBytes for attachment {attachment_id}: {decode_error}")
                    return None
                except Exception as e:
                     logger.error(f"Unexpected error decoding Base64 for attachment {attachment_id}: {e}", exc_info=True)
                     return None

            except httpx.ReadTimeout as e:
                # Specific handling for ReadTimeout
                retry_count += 1
                if retry_count <= max_retries:
                    logger.warning(f"[ATTACHMENT-CONTENT] Read timeout fetching attachment {attachment_id} for message {message_id}. Retrying ({retry_count}/{max_retries}) after {backoff_time}s delay...")
                    await asyncio.sleep(backoff_time)
                    backoff_time *= 2  # Progressive backoff
                else:
                    logger.error(f"[ATTACHMENT-CONTENT] Read timeout fetching attachment {attachment_id} for message {message_id} after {max_retries} retries.", exc_info=True)
                    return None  # Return None instead of raising exception to allow processing other attachments

            except httpx.HTTPStatusError as e:
                # Log specific HTTP errors
                logger.error(f"[ATTACHMENT-CONTENT] HTTP error fetching attachment {attachment_id} for message {message_id}: Status {e.response.status_code}, Response: {e.response.text}")
                if e.response.status_code == 404:
                    logger.warning(f"[ATTACHMENT-CONTENT] Attachment {attachment_id} not found for message {message_id}.")
                    return None
                return None
            except Exception as e:
                logger.error(f"[ATTACHMENT-CONTENT] Unexpected error fetching attachment {attachment_id} for message {message_id}: {e}", exc_info=True)
                return None

    async def get_email_attachment(self, email_id: str, attachment_id: str) -> EmailAttachment:
        """Get email attachment by ID"""
        response = await self.client.get(
            f"/me/messages/{email_id}/attachments/{attachment_id}",
            headers=self.headers
        )
        response.raise_for_status()
        attachment = response.json()
        
        return EmailAttachment(
            id=attachment["id"],
            name=attachment["name"],
            content_type=attachment["contentType"],
            size=attachment["size"],
            content=attachment.get("contentBytes")
        )

    async def get_all_subjects_for_filter(self, filter_criteria: EmailFilter) -> List[str]:
        """
        Fetches subjects of ALL emails matching the filter criteria using pagination.
        Currently supports folder_id, start_date, end_date. Keywords are ignored.
        """
        logger.info(f"[ALL_SUBJECTS] Starting fetch for filter: {filter_criteria.model_dump_json()}")
        
        all_subjects: List[str] = []
        max_emails_to_fetch = 10000
        request_url = "/me/messages"
        page_size = 100

        filter_parts = []
        if filter_criteria.folder_id:
            safe_folder_id = filter_criteria.folder_id.replace("'", "''") 
            filter_parts.append(f"parentFolderId eq '{safe_folder_id}'")
        graph_api_start_date, graph_api_end_date = self._parse_dates_for_graph_filter(
            filter_criteria.start_date, filter_criteria.end_date
        )
        if graph_api_start_date:
            filter_parts.append(f"receivedDateTime ge {graph_api_start_date}")
        if graph_api_end_date:
            filter_parts.append(f"receivedDateTime le {graph_api_end_date}")
        
        final_filter_str = " and ".join(filter_parts) if filter_parts else None
        
        params = {
            "$select": "subject",
            "$top": page_size
        }
        if final_filter_str:
            params["$filter"] = final_filter_str
            logger.info(f"[ALL_SUBJECTS] Using $filter: {final_filter_str}")
        else:
             logger.info("[ALL_SUBJECTS] No filter applied (fetching from all folders/dates).")
             
        page_count = 0
        while request_url and len(all_subjects) < max_emails_to_fetch:
            page_count += 1
            logger.info(f"[ALL_SUBJECTS] Fetching page {page_count}. Current count: {len(all_subjects)}. URL: {request_url}")
            
            try:
                if "@odata.nextLink" in request_url: 
                     async with httpx.AsyncClient(timeout=120.0) as next_link_client:
                        response = await next_link_client.get(request_url, headers=self.headers)
                else:
                    response = await self.client.get(request_url, params=params)
                
                response.raise_for_status()
                data = response.json()
                
                messages = data.get("value", [])
                for message in messages:
                    if message.get("subject"):
                        all_subjects.append(message["subject"])
                    else:
                        logger.debug(f"[ALL_SUBJECTS] Email found with no subject (ID: {message.get('id', 'N/A')}). Skipping.")
                
                request_url = data.get("@odata.nextLink")
                # Clear params after the first request, as they are included in the nextLink
                if page_count == 1:
                     params = {}

                logger.info(f"[ALL_SUBJECTS] Page {page_count} fetched {len(messages)} items. Total subjects now: {len(all_subjects)}. Next link exists: {bool(request_url)}")

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", "10"))
                    logger.warning(f"[ALL_SUBJECTS] Rate limit hit (429). Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                else:
                    logger.error(f"[ALL_SUBJECTS] Graph API HTTP error fetching page {page_count}: {e.response.status_code} - {e.response.text}", exc_info=True)
                    break
            except Exception as e:
                logger.error(f"[ALL_SUBJECTS] Unexpected error fetching page {page_count}: {e}", exc_info=True)
                break

        if len(all_subjects) >= max_emails_to_fetch:
             logger.warning(f"[ALL_SUBJECTS] Reached safety limit ({max_emails_to_fetch}). Returning {len(all_subjects)} subjects.")
             
        logger.info(f"[ALL_SUBJECTS] Finished fetching. Total subjects collected: {len(all_subjects)}")
        return all_subjects

    # --- NEW METHOD for Calendar Events ---
    async def get_upcoming_events(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        Fetches upcoming calendar events for the user using /me/calendarView.
        
        Args:
            days_ahead: How many days into the future to query events for.
            
        Returns:
            A list of dictionaries, each representing an upcoming event.
        """
        logger.info(f"Fetching upcoming calendar events for the next {days_ahead} days.")
        
        # Get timezone from environment variable, fall back to UTC+8 (Singapore) if not set
        timezone_preference = os.getenv("TZ", "Asia/Singapore")
        
        # For Asia/Singapore, use UTC+8, otherwise try to determine the timezone offset
        if timezone_preference == "Asia/Singapore":
            singapore_tz = timezone(timedelta(hours=8))  # UTC+8 for Singapore
        else:
            # Default to UTC+8 if timezone parsing fails
            try:
                # This is a simplification - in a production environment,
                # you would use the pytz or dateutil libraries to properly handle timezone parsing
                if timezone_preference == "UTC":
                    singapore_tz = timezone.utc
                else:
                    # Simplified fallback - assumes format like "UTC+8" or just numerical offset
                    hours_offset = 8  # Default to Singapore offset
                    if "+" in timezone_preference:
                        try:
                            hours_offset = int(timezone_preference.split("+")[1])
                        except (ValueError, IndexError):
                            logger.warning(f"Could not parse timezone offset from {timezone_preference}, using default UTC+8")
                    singapore_tz = timezone(timedelta(hours=hours_offset))
            except Exception as e:
                logger.warning(f"Error parsing timezone {timezone_preference}: {e}. Using default UTC+8")
                singapore_tz = timezone(timedelta(hours=8))
        
        now_sg = datetime.now(singapore_tz)
        end_sg = now_sg + timedelta(days=days_ahead)
        
        # Format dates for Graph API query (ISO 8601)
        start_dt_str = now_sg.isoformat()
        end_dt_str = end_sg.isoformat()
        
        # Construct the API endpoint and parameters
        # calendarView automatically filters by start/end time
        calendar_view_url = f"/me/calendarView"
        params = {
            "startDateTime": start_dt_str,
            "endDateTime": end_dt_str,
            "$select": "id,subject,start,end,location,attendees,bodyPreview,isCancelled,onlineMeeting", # Added onlineMeeting
            "$filter": "isCancelled eq false", # Exclude cancelled events
            "$orderby": "start/dateTime asc", # Order by start time
            "$top": 50 # Limit the number of results (adjust as needed)
        }
        
        events_list = []
        try:
            response = await self.client.get(calendar_view_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            raw_events = data.get("value", [])
            logger.info(f"Found {len(raw_events)} raw calendar events in the specified window.")
            
            # Format the events (extracting relevant info)
            for event in raw_events:
                # Ensure start/end times and timezones are handled correctly
                start_info = event.get("start", {})
                end_info = event.get("end", {})
                
                # Get online meeting URL if available
                online_meeting_url = ""
                if event.get("onlineMeeting"):
                    online_meeting_url = event.get("onlineMeeting", {}).get("joinUrl", "")
                
                # Get location with more detail
                location = event.get("location", {}).get("displayName", "No Location")
                if online_meeting_url and not location:
                    location = f"Online Meeting: {online_meeting_url}"
                elif online_meeting_url:
                    location = f"{location} ({online_meeting_url})"
                
                formatted_event = {
                    "id": event.get("id"),
                    "subject": event.get("subject", "No Subject"),
                    "start_time": start_info.get("dateTime"),
                    "start_timezone": timezone_preference,  # Use the environment timezone instead of hardcoding
                    "end_time": end_info.get("dateTime"),
                    "end_timezone": timezone_preference,  # Use the environment timezone instead of hardcoding
                    "location": location,
                    "attendees": [att.get("emailAddress", {}).get("name", att.get("emailAddress", {}).get("address")) 
                                  for att in event.get("attendees", [])],
                    "preview": event.get("bodyPreview", ""),
                    "online_meeting_url": online_meeting_url
                }
                events_list.append(formatted_event)
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Graph API HTTP error fetching calendar events: {e.response.status_code} - {e.response.text}", exc_info=True)
            # Depending on requirements, could raise HTTPException or return empty/error indicator
        except Exception as e:
            logger.error(f"Unexpected error fetching calendar events: {e}", exc_info=True)
            # Depending on requirements, could raise or return empty/error indicator

        logger.info(f"Returning {len(events_list)} formatted upcoming events.")
        return events_list
    # --- END NEW METHOD ---

    async def get_folder_details(self, folder_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific folder."""
        try:
            response = await self.client.get(f"/me/mailFolders/{folder_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting folder details: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Error getting folder details: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Unexpected error getting folder details: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error getting folder details: {str(e)}"
            )
    
    async def list_messages(self, folder_id: str, top: int = 50, skip: int = 0, filter: str = None, **kwargs) -> List[Dict[str, Any]]:
        """List messages in a folder with pagination support."""
        try:
            params = {
                "$select": "id,subject,sender,receivedDateTime,hasAttachments,importance,bodyPreview",
                "$orderby": "receivedDateTime desc",
                "$top": top,
                "$skip": skip
            }
            
            # Add filter if provided
            if filter:
                params["$filter"] = filter
            
            response = await self.client.get(
                f"/me/mailFolders/{folder_id}/messages",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return data.get("value", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error listing messages: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Error listing messages: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Unexpected error listing messages: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error listing messages: {str(e)}"
            )
    
    async def create_delta_link(self, folder_id: str) -> str:
        """Create a delta link for tracking changes in a folder."""
        try:
            response = await self.client.get(
                f"/me/mailFolders/{folder_id}/messages/delta",
                params={"$select": "id,subject,receivedDateTime"}
            )
            response.raise_for_status()
            data = response.json()
            
            # The delta link is in the @odata.deltaLink property of the response
            delta_link = data.get("@odata.deltaLink", "")
            if not delta_link:
                raise ValueError("Delta link not found in response")
                
            return delta_link
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating delta link: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Error creating delta link: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Unexpected error creating delta link: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error creating delta link: {str(e)}"
            )
    
    async def get_changes(self, delta_link: str) -> Dict[str, Any]:
        """Get changes using a delta link."""
        try:
            # The delta link already contains all necessary parameters
            async with httpx.AsyncClient(timeout=settings.MS_GRAPH_TIMEOUT_SECONDS) as temp_client:
                response = await temp_client.get(
                    delta_link,
                    headers=self.headers
                )
            response.raise_for_status()
            data = response.json()
            
            return {
                "changes": data.get("value", []),
                "delta_link": data.get("@odata.deltaLink", "")
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting changes: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=f"Error getting changes: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Unexpected error getting changes: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error getting changes: {str(e)}"
            )
    
    @classmethod
    async def create(cls, user_email: str) -> 'OutlookService':
        """Factory method to create an OutlookService instance with fresh tokens for a user."""
        from app.dependencies.auth import get_user_with_refresh_token
        from app.db.session import get_db
        from app.services.auth_service import AuthService
        
        # Get a database session
        db = next(get_db())
        
        try:
            # Get the user from the database
            user_db = get_user_with_refresh_token(db, user_email)
            if not user_db:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
                
            # Get a fresh access token using AuthService
            ms_token = await AuthService.refresh_ms_token(db, user_email)
            if not ms_token or not ms_token.get("access_token"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to get Microsoft access token"
                )
                
            # Create an OutlookService instance with the fresh token
            return cls(ms_token["access_token"])
        finally:
            db.close()