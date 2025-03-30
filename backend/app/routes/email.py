from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Optional
from datetime import datetime

from app.models.email import EmailPreview, EmailFilter, EmailContent
from app.services.outlook import get_email_folders, get_email_preview, get_email_content
from app.routes.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/folders", response_model=List[dict])
async def list_folders(current_user: User = Depends(get_current_user)):
    """Get list of email folders from Outlook"""
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    
    try:
        folders = await get_email_folders(current_user.ms_token_data.access_token)
        return folders
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch folders: {str(e)}"
        )


@router.post("/preview", response_model=List[EmailPreview])
async def preview_emails(
    filter_params: EmailFilter,
    current_user: User = Depends(get_current_user)
):
    """Preview emails based on filter criteria"""
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    
    try:
        previews = await get_email_preview(
            access_token=current_user.ms_token_data.access_token,
            folder_id=filter_params.folder_id,
            start_date=filter_params.start_date,
            end_date=filter_params.end_date,
            keywords=filter_params.keywords,
            sender=filter_params.sender
        )
        return previews
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch email previews: {str(e)}"
        )


@router.get("/content/{email_id}", response_model=EmailContent)
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
        content = await get_email_content(
            access_token=current_user.ms_token_data.access_token,
            email_id=email_id
        )
        return content
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch email content: {str(e)}"
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
