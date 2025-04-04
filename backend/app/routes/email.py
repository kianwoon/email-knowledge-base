import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from typing import List, Optional
from datetime import datetime
import uuid
import httpx
from pydantic import BaseModel

from app.models.email import EmailPreview, EmailFilter, EmailContent
from app.services.outlook import OutlookService
from app.routes.auth import get_current_user
from app.models.user import User
from app.config import settings

router = APIRouter()

logger = logging.getLogger("app")

class AnalysisJob(BaseModel):
    job_id: str


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


@router.post("/analyze", response_model=AnalysisJob)
async def analyze_emails(
    filter_criteria: EmailFilter,
    current_user: User = Depends(get_current_user)
):
    """
    Fetch subjects for ALL emails matching the filter criteria, 
    trigger external analysis via POST request, and return a job ID.
    """
    logger.info(f"Received request to analyze emails matching filter: {filter_criteria.model_dump_json(indent=2)}")
    
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        logger.warning("Analysis request failed: Microsoft access token not available.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )

    outlook = OutlookService(current_user.ms_token_data.access_token)
    
    # --- Fetch ALL Subjects using the new service method ---
    logger.info("Fetching ALL subjects based on filter...")
    try:
        subjects = await outlook.get_all_subjects_for_filter(filter_criteria)
    except HTTPException as e:
        # Re-raise HTTP exceptions from the service layer
        logger.error(f"HTTP error during subject fetching: {e.status_code} - {e.detail}")
        raise e 
    except Exception as e:
        # Catch unexpected errors during fetching
        logger.error(f"Unexpected error fetching all subjects: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching subjects: {str(e)}"
        )
    # --- End Fetch ALL Subjects ---

    if not subjects:
        logger.error("Analysis request failed: No subjects could be fetched for the given filter.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not fetch subjects for the provided filter criteria."
        )
    
    logger.info(f"Collected {len(subjects)} subjects for analysis.")

    # --- Call External Service (Logic remains similar) ---
    external_analysis_url = settings.EXTERNAL_ANALYSIS_URL # Use URL from settings
    if not external_analysis_url:
        logger.error("External analysis service URL (EXTERNAL_ANALYSIS_URL) is not configured in settings/environment.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="External analysis service URL is not configured."
        )

    # Construct webhook URL using base backend URL, manually adding /api, then webhook prefix + path
    # We add /api manually because internal API_PREFIX is now empty due to Koyeb routing
    webhook_callback_path = "/analysis" # Path defined in webhooks.py @router.post
    webhook_url = f"{settings.BACKEND_URL}/api{settings.WEBHOOK_PREFIX}{webhook_callback_path}" 
    job_id = str(uuid.uuid4())

    # --- Get API Key from settings --- 
    api_key = settings.EXTERNAL_ANALYSIS_API_KEY 
    if not api_key:
        logger.error("External analysis API key (EXTERNAL_ANALYSIS_API_KEY) is not configured in settings/environment.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="External analysis service API key is not configured."
        )
    # --- End Get API Key --- 

    payload = {
        "job_id": job_id,
        "subjects": subjects, # Send the list of all fetched subjects
        "webhook_url": webhook_url
    }
    
    # --- Prepare Headers --- 
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key 
    }
    # --- End Prepare Headers --- 

    logger.info(f"Submitting job {job_id} with {len(subjects)} subjects to external analysis service at {external_analysis_url}")
    logger.info(f"Webhook URL for callback: {webhook_url}")
    # Avoid logging full payload if subjects list is very large or sensitive
    # logger.debug(f"Payload: {payload}") 

    try:
        logger.info(f" --- Attempting POST request to external service: {external_analysis_url} --- ")
        async with httpx.AsyncClient(timeout=60.0) as client: # Increased timeout slightly
            # Include headers in the POST request
            response = await client.post(external_analysis_url, json=payload, headers=headers)
            logger.info(f" --- POST request completed. Status Code: {response.status_code} --- ")
            response.raise_for_status() # Raise exception for 4xx/5xx responses
            logger.info(f"Successfully submitted job {job_id} to external service. Status after raise_for_status: {response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"Could not connect to external analysis service at {external_analysis_url}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not connect to the external analysis service: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"External analysis service returned error status {e.response.status_code}: {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"External analysis service returned an error: {e.response.status_code}"
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred while submitting to external service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during analysis submission."
        )

    # Return the job ID to the frontend
    return AnalysisJob(job_id=job_id)