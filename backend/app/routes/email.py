import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from typing import List, Optional
from datetime import datetime
import uuid
import httpx
from pydantic import BaseModel

# Qdrant imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct

from app.models.email import EmailPreview, EmailFilter, EmailContent
from app.services.outlook import OutlookService
from app.routes.auth import get_current_user
from app.models.user import User
from app.config import settings
from app.routes.vector import get_db

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
    current_user: User = Depends(get_current_user),
    qdrant_client: QdrantClient = Depends(get_db)
):
    """
    Starts an analysis job: stores query criteria, triggers external analysis, 
    and returns a job ID.
    """
    logger.info(f"Received request to analyze emails matching filter: {filter_criteria.model_dump_json(indent=2)}")
    
    # --- Generate Job ID ---
    job_id = str(uuid.uuid4())
    logger.info(f"Generated Job ID: {job_id}")

    # --- Store Query Criteria in Qdrant ---
    try:
        criteria_payload = {
            "type": "query_criteria",
            "owner": current_user.email,
            "filter": filter_criteria.model_dump()
        }
        logger.info(f"Storing query criteria for job {job_id} with payload: {criteria_payload}")
        qdrant_client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[
                PointStruct(
                    id=job_id, 
                    vector=[0.0] * settings.EMBEDDING_DIMENSION,
                    payload=criteria_payload
                )
            ],
            wait=True
        )
        logger.info(f"Successfully stored query criteria for job {job_id}")
    except Exception as e:
        logger.error(f"Failed to store query criteria for job {job_id} in Qdrant: {str(e)}", exc_info=True)
        # Decide if we should halt the process or just log the error
        # For now, let's raise an error as storing criteria is important
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store query criteria in knowledge base: {str(e)}"
        )
    # --- End Store Query Criteria ---

    # --- Microsoft Token Check ---
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        logger.warning("Analysis request failed: Microsoft access token not available.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    # --- End Token Check ---

    outlook = OutlookService(current_user.ms_token_data.access_token)
    
    # --- Fetch ALL Subjects using the new service method ---
    logger.info("Fetching ALL subjects based on filter...")
    try:
        subjects = await outlook.get_all_subjects_for_filter(filter_criteria)
    except HTTPException as e:
        logger.error(f"HTTP error during subject fetching: {e.status_code} - {e.detail}")
        raise e 
    except Exception as e:
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
    external_analysis_url = settings.EXTERNAL_ANALYSIS_URL
    if not external_analysis_url:
        logger.error("External analysis service URL (EXTERNAL_ANALYSIS_URL) is not configured in settings/environment.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="External analysis service URL is not configured."
        )

    # Construct webhook URL - Explicitly add /api prefix for external access
    # Assumes WEBHOOK_PREFIX defines the path *after* /api (e.g., /webhooks)
    # Assumes BACKEND_URL is the base domain (no /api suffix)
    webhook_callback_path = "/analysis" 
    webhook_url = f"{settings.BACKEND_URL.rstrip('/')}{settings.API_PREFIX}{settings.WEBHOOK_PREFIX.rstrip('/')}{webhook_callback_path}" 
    
    # Get API Key
    api_key = settings.EXTERNAL_ANALYSIS_API_KEY
    if not api_key:
        logger.error("External analysis API key (EXTERNAL_ANALYSIS_API_KEY) is not configured in settings/environment.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="External analysis service API key is not configured."
        )

    payload_to_external = {
        "job_id": job_id,
        "subjects": subjects,
        "webhook_url": webhook_url,
        "owner": current_user.email
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key 
    }

    logger.info(f"Submitting job {job_id} for owner {current_user.email} with {len(subjects)} subjects to external service at {external_analysis_url}")
    logger.info(f"Webhook URL for callback: {webhook_url}")

    # --- Make POST Request to External Service --- 
    try:
        logger.info(f" --- Attempting POST request to external service: {external_analysis_url} --- ")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(external_analysis_url, json=payload_to_external, headers=headers)
            logger.info(f" --- POST request completed. Status Code: {response.status_code} --- ")
            response.raise_for_status() 
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
    # --- End POST Request --- 

    # Return the job ID to the frontend
    return AnalysisJob(job_id=job_id)