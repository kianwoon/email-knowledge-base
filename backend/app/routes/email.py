import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from typing import List, Optional
from datetime import datetime

from app.models.email import EmailPreview, EmailFilter, EmailContent
from app.services.outlook import OutlookService
from app.routes.auth import get_current_user
from app.models.user import User

router = APIRouter()

logger = logging.getLogger("app")


@router.get("/folders", response_model=List[dict])
async def list_folders(current_user: User = Depends(get_current_user)):
    """Get list of email folders from Outlook"""
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    
    try:
        outlook = OutlookService(current_user.ms_token_data.access_token)
        folders = await outlook.get_email_folders()
        return folders
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch folders: {str(e)}"
        )


@router.post("/preview", response_model=dict)
async def preview_emails(
    filter_params: EmailFilter,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user)
):
    """Get preview of emails based on filter criteria"""
    try:
        if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
            raise HTTPException(
                status_code=401,
                detail="Microsoft access token not available"
            )

        # Get email previews
        outlook = OutlookService(current_user.ms_token_data.access_token)
        result = await outlook.get_email_preview(
            folder_id=filter_params.folder_id,
            start_date=filter_params.start_date,
            end_date=filter_params.end_date,
            keywords=filter_params.keywords,
            sender=filter_params.sender,
            page=page,
            per_page=per_page,
            next_link=filter_params.next_link
        )

        # Calculate current page based on total and per_page
        current_page = page
        if filter_params.next_link:
            # If next_link was used, increment the page
            current_page = page + 1

        # Format response to match frontend expectations
        return {
            "items": result.get("items", []),
            "total": result.get("total", 0),
            "next_link": result.get("next_link"),
            "current_page": current_page,
            "total_pages": (result.get("total", 0) + per_page - 1) // per_page,
            "per_page": per_page
        }

    except Exception as e:
        logger.error(f"Error getting email previews: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting email previews: {str(e)}"
        )


@router.get("/{email_id}", response_model=EmailContent)
async def get_email(
    email_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get full content of a specific email"""
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    
    try:
        outlook = OutlookService(current_user.ms_token_data.access_token)
        content = await outlook.get_email_content(email_id)
        return content
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch email content: {str(e)}"
        )


@router.get("/{email_id}/attachments/{attachment_id}")
async def get_email_attachment(
    email_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get email attachment by ID"""
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    
    try:
        outlook = OutlookService(current_user.ms_token_data.access_token)
        attachment = await outlook.get_email_attachment(email_id, attachment_id)
        return attachment
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch attachment: {str(e)}"
        )


@router.post("/analyze", response_model=List[str])
async def analyze_emails(
    email_ids: List[str],
    current_user: User = Depends(get_current_user)
):
    """Queue emails for LLM analysis"""
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    
    # In a real implementation, this would add emails to a processing queue
    # For now, we'll just return the IDs that were submitted for analysis
    return email_ids