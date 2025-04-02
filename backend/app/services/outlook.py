import httpx
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

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


async def get_user_photo(access_token: str) -> Optional[str]:
    """Get user profile photo from Microsoft Graph API
    
    Returns:
        Optional[str]: Base64 encoded photo or None if no photo is available
    """
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        try:
            # Try to get the photo
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me/photo/$value",
                headers=headers
            )
            response.raise_for_status()
            
            # Convert photo to base64
            import base64
            photo_base64 = base64.b64encode(response.content).decode('utf-8')
            return f"data:image/jpeg;base64,{photo_base64}"
        except Exception as e:
            print(f"Error getting user photo: {str(e)}")
            return None


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


def sanitize_keyword(keyword: str) -> str:
    # Remove any quotes and escape special characters
    return keyword.replace("'", "").replace('"', "")


async def get_email_preview(
    access_token: str,
    folder_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    keywords: Optional[List[str]] = None,
    sender: Optional[str] = None,
    page: int = 1,
    per_page: int = 10
) -> Dict[str, Any]:
    """Get email preview with optional filtering."""
    try:
        # Base headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        # Initialize parameters with basic settings
        params = {
            "$top": per_page,
            "$skip": (page - 1) * per_page,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,sender,receivedDateTime,bodyPreview",
            "$count": True
        }

        # Build filter conditions
        filter_conditions = []
        
        if start_date:
            filter_conditions.append(f"receivedDateTime ge {start_date.isoformat()}Z")
        if end_date:
            filter_conditions.append(f"receivedDateTime le {end_date.isoformat()}Z")
        if sender:
            filter_conditions.append(f"from/emailAddress/address eq '{sender}'")

        # Handle keywords if provided
        if keywords and isinstance(keywords, list) and len(keywords) > 0:
            valid_keywords = [k.strip() for k in keywords if k and isinstance(k, str) and k.strip()]
            if valid_keywords:
                # Add ConsistencyLevel header which is required for $search
                headers["ConsistencyLevel"] = "eventual"
                params["$search"] = f'"{" ".join(valid_keywords)}"'

        # Add filter conditions if any exist
        if filter_conditions:
            params["$filter"] = " and ".join(filter_conditions)

        # Determine folder endpoint
        folder_path = f"/{folder_id}" if folder_id else "/inbox"
        
        # Construct final URL
        base_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
        final_url = f"{base_url}{folder_path}/messages"

        # Log request details for debugging
        print("\n=== Graph API Request Details ===")
        print(f"➡ Base URL: {base_url}")
        print(f"➡ Folder Path: {folder_path}")
        print(f"➡ Final URL: {final_url}")
        print(f"➡ Headers: {headers}")
        print(f"➡ Parameters: {params}")
        print("==============================\n")

        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.get(
                final_url,
                headers=headers,
                params=params,
                timeout=30.0  # Set a longer timeout
            )
            
            # Log response details
            print("\n=== Graph API Response Details ===")
            print(f"➡ Status Code: {response.status_code}")
            print(f"➡ Response Headers: {dict(response.headers)}")
            if response.status_code >= 400:
                print(f"➡ Error Response: {response.text}")
            else:
                print(f"➡ Response Preview: {response.text[:500]}...")
            print("==============================\n")

            response.raise_for_status()
            data = response.json()

            # Log the data structure
            print("\n=== Response Data Structure ===")
            print(f"➡ Keys in response: {data.keys()}")
            if "value" in data:
                print(f"➡ Number of emails: {len(data['value'])}")
                if len(data['value']) > 0:
                    print(f"➡ Sample email keys: {data['value'][0].keys()}")
            print("==============================\n")

            # Convert to EmailPreview objects
            emails = []
            for email in data.get("value", []):
                try:
                    preview = EmailPreview(
                        id=email["id"],
                        subject=email.get("subject", "(No subject)"),
                        sender=email["sender"]["emailAddress"]["address"],
                        received_date=email["receivedDateTime"],
                        snippet=email.get("bodyPreview", "")
                    )
                    emails.append(preview)
                except Exception as e:
                    print(f"Error processing email: {str(e)}")
                    print(f"Email data: {email}")
                    continue

            return {
                "emails": emails,
                "total": data.get("@odata.count", 0)
            }

    except httpx.HTTPError as e:
        print(f"HTTP Error: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response Status: {e.response.status_code}")
            print(f"Response Headers: {dict(e.response.headers)}")
            print(f"Response Text: {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch emails: {str(e)}"
        )
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


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
