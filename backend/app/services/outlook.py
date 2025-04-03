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
        # Base headers - ConsistencyLevel: eventual is required for $search and $count
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "ConsistencyLevel": "eventual"
        }

        # Initialize parameters with basic settings
        params = {
            "$select": "id,subject,sender,receivedDateTime,bodyPreview,importance,hasAttachments"
        }

        # Determine if we need to use search
        has_search = keywords and isinstance(keywords, list) and len([k for k in keywords if k and isinstance(k, str) and k.strip()])

        # Construct base URL and handle folder selection
        base_url = "https://graph.microsoft.com/v1.0/me"
        folder_path = f"/mailFolders/{folder_id}" if folder_id else "/mailFolders/inbox"
        final_url = f"{base_url}{folder_path}/messages"

        # If using search, we'll need to fetch more results to account for post-filtering
        if has_search:
            # Simple search query without complex expressions
            valid_keywords = [k.strip() for k in keywords if k and isinstance(k, str) and k.strip()]
            params["$search"] = f'"{" ".join(valid_keywords)}"'
            
            # When using search, fetch enough results for the current page
            # We multiply by 3 to account for filtering
            params["$top"] = page * per_page * 3
        else:
            # If no search, use OData filters and sorting
            params["$orderby"] = "receivedDateTime desc"
            params["$count"] = "true"
            
            filter_conditions = []
            
            # Date filters
            if start_date:
                start_str = start_date.astimezone().replace(microsecond=0).isoformat()
                if start_str.endswith('+00:00'):
                    start_str = start_str[:-6] + 'Z'
                filter_conditions.append(f"receivedDateTime ge {start_str}")
            
            if end_date:
                end_str = end_date.astimezone().replace(microsecond=0).isoformat()
                if end_str.endswith('+00:00'):
                    end_str = end_str[:-6] + 'Z'
                filter_conditions.append(f"receivedDateTime le {end_str}")
            
            # Sender filter
            if sender:
                filter_conditions.append(f"from/emailAddress/address eq '{sender}'")

            if filter_conditions:
                params["$filter"] = " and ".join(filter_conditions)

            # Standard pagination for non-search queries
            params["$top"] = per_page
            params["$skip"] = (page - 1) * per_page

        # Log request details for debugging
        print("\n=== Graph API Request Details ===")
        print(f"➡ Base URL: {base_url}")
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
                timeout=30.0
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

            data = response.json()

            # Process emails and apply filters if needed
            all_emails = []
            for email in data.get("value", []):
                try:
                    # Apply date and sender filters for search queries
                    if has_search:
                        email_date = datetime.fromisoformat(email["receivedDateTime"].replace('Z', '+00:00'))
                        
                        # Skip if outside date range
                        if start_date and email_date < start_date:
                            continue
                        if end_date and email_date > end_date:
                            continue
                        
                        # Skip if sender doesn't match
                        if sender and email["sender"]["emailAddress"]["address"].lower() != sender.lower():
                            continue

                    preview = EmailPreview(
                        id=email["id"],
                        subject=email.get("subject", "(No subject)"),
                        sender=email["sender"]["emailAddress"]["address"],
                        received_date=email["receivedDateTime"],
                        snippet=email.get("bodyPreview", ""),
                        importance=email.get("importance", "normal"),
                        has_attachments=email.get("hasAttachments", False)
                    )
                    all_emails.append(preview)
                except Exception as e:
                    print(f"Error processing email: {str(e)}")
                    print(f"Email data: {email}")
                    continue

            # Handle pagination and sorting for search results
            if has_search:
                # Sort emails by received date in descending order
                all_emails.sort(key=lambda x: x.received_date, reverse=True)
                
                # Calculate total after date filtering
                total_filtered = len(all_emails)
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                emails = all_emails[start_idx:end_idx]
                
                return {
                    "emails": emails,
                    "total": total_filtered
                }
            else:
                return {
                    "emails": all_emails,
                    "total": data.get("@odata.count", len(all_emails))
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
