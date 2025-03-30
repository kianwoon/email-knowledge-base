import httpx
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.models.email import EmailPreview, EmailContent, EmailAttachment
from app.config import settings


async def get_user_info(access_token: str) -> Dict[str, Any]:
    """Get user information from Microsoft Graph API"""
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers=headers
        )
        response.raise_for_status()
        return response.json()


async def get_email_folders(access_token: str) -> List[Dict[str, Any]]:
    """Get list of email folders from Outlook"""
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me/mailFolders",
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data.get("value", [])


async def get_email_preview(
    access_token: str,
    folder_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    keywords: Optional[List[str]] = None,
    sender: Optional[str] = None
) -> List[EmailPreview]:
    """Get preview of emails based on filter criteria"""
    # Build filter query
    filter_parts = []
    
    if start_date:
        filter_parts.append(f"receivedDateTime ge {start_date.isoformat()}")
    
    if end_date:
        filter_parts.append(f"receivedDateTime le {end_date.isoformat()}")
    
    if sender:
        filter_parts.append(f"from/emailAddress/address eq '{sender}'")
    
    # Build search query for keywords
    search_query = ""
    if keywords and len(keywords) > 0:
        search_query = " OR ".join(keywords)
    
    # Determine folder endpoint
    folder_path = f"/{folder_id}" if folder_id else ""
    
    # Build query parameters
    params = {
        "$top": settings.MAX_PREVIEW_EMAILS,
        "$select": "id,subject,from,receivedDateTime,bodyPreview",
        "$orderby": "receivedDateTime desc"
    }
    
    if filter_parts:
        params["$filter"] = " and ".join(filter_parts)
    
    if search_query:
        params["$search"] = f'"{search_query}"'
    
    # Make API request
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        response = await client.get(
            f"https://graph.microsoft.com/v1.0/me/mailFolders{folder_path}/messages",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        data = response.json()
        
        # Convert to EmailPreview objects
        previews = []
        for item in data.get("value", []):
            preview = EmailPreview(
                id=item.get("id"),
                subject=item.get("subject", "(No subject)"),
                sender=item.get("from", {}).get("emailAddress", {}).get("name", "Unknown"),
                received_date=datetime.fromisoformat(item.get("receivedDateTime").replace("Z", "+00:00")),
                snippet=item.get("bodyPreview", "")
            )
            previews.append(preview)
        
        return previews


async def get_email_content(
    access_token: str,
    email_id: str
) -> EmailContent:
    """Get full content of a specific email including attachments"""
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Get email details
        response = await client.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{email_id}",
            headers=headers,
            params={
                "$expand": "attachments"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract attachment information
        attachments = []
        for attachment in data.get("attachments", []):
            # Only process file attachments
            if attachment.get("@odata.type") == "#microsoft.graph.fileAttachment":
                attachment_obj = EmailAttachment(
                    id=attachment.get("id"),
                    name=attachment.get("name"),
                    content_type=attachment.get("contentType"),
                    size=attachment.get("size", 0),
                    # Base64 content is available in attachment.get("contentBytes")
                    # We'll process this separately in the parser service
                )
                attachments.append(attachment_obj)
        
        # Create EmailContent object
        content = EmailContent(
            id=data.get("id"),
            internet_message_id=data.get("internetMessageId"),
            subject=data.get("subject", "(No subject)"),
            sender=data.get("from", {}).get("emailAddress", {}).get("name", "Unknown"),
            sender_email=data.get("from", {}).get("emailAddress", {}).get("address", ""),
            recipients=[
                recipient.get("emailAddress", {}).get("address", "")
                for recipient in data.get("toRecipients", [])
            ],
            cc_recipients=[
                recipient.get("emailAddress", {}).get("address", "")
                for recipient in data.get("ccRecipients", [])
            ],
            received_date=datetime.fromisoformat(data.get("receivedDateTime").replace("Z", "+00:00")),
            body=data.get("body", {}).get("content", ""),
            is_html=data.get("body", {}).get("contentType", "") == "html",
            folder_id=data.get("parentFolderId", ""),
            folder_name="",  # We would need another API call to get the folder name
            attachments=attachments,
            importance=data.get("importance", "normal")
        )
        
        return content
