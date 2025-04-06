import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, BackgroundTasks
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
from ..db.qdrant_client import get_qdrant_client

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


@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_emails(
    filter_criteria: EmailFilter,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    qdrant: QdrantClient = Depends(get_qdrant_client)
):
    """
    Initiates the email analysis process:
    1. Fetches email subjects based on filter criteria.
    2. Stores the criteria and owner in Qdrant with a unique job ID.
    3. Submits the subjects to an external analysis service with a webhook URL.
    4. Stores a mapping between the external service's job ID and our internal job ID.
    """
    owner = current_user.email
    logger.info(f"Received analysis request from owner: {owner}")
    logger.debug(f"Filter criteria: {filter_criteria}")

    # --- Microsoft Token Check ---
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        logger.warning(f"Analysis request failed for {owner}: Microsoft access token not available.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    # --- End Token Check ---

    # --- Instantiate Outlook Service ---
    try:
        outlook = OutlookService(current_user.ms_token_data.access_token)
    except Exception as e:
        logger.error(f"Failed to instantiate OutlookService for {owner}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize connection to email service."
        )
    # --- End Instantiate ---

    job_id = str(uuid.uuid4())

    # Convert Pydantic model to dict for Qdrant payload
    filter_criteria_obj = filter_criteria.model_dump(mode='json')

    # Store the original query criteria in Qdrant associated with the job_id and owner
    query_point_id = str(uuid.uuid4())
    query_payload = {
        "type": "query_criteria",
        "job_id": job_id,
        "owner": owner,
        "criteria": filter_criteria_obj,
        "status": "submitted"
    }
    query_point = PointStruct(
        id=query_point_id,
        payload=query_payload,
        vector=[0.0] * settings.EMBEDDING_DIMENSION
    )

    try:
        qdrant.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[query_point],
            wait=True
        )
        logger.info(f"Stored query criteria for job_id {job_id} with owner {owner}")
    except Exception as e:
        logger.error(f"Failed to store query criteria in Qdrant for job_id {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize analysis job storage.")

    # Fetch email subjects (using pagination if necessary)
    subjects = []
    next_link = None
    max_subjects = 200
    try:
        while len(subjects) < max_subjects:
            logger.debug(f"Fetching email previews. Current count: {len(subjects)}. Max: {max_subjects}")
            preview_result = await outlook.get_email_preview(
                folder_id=filter_criteria.folder_id,
                keywords=filter_criteria.keywords,
                start_date=filter_criteria.start_date,
                end_date=filter_criteria.end_date,
                per_page=50,
                next_link=next_link
            )
            batch_subjects = [item['subject'] for item in preview_result.get('items', []) if item.get('subject')]
            subjects.extend(batch_subjects)
            next_link = preview_result.get('next_link')
            logger.debug(f"Fetched {len(batch_subjects)} subjects. Total now: {len(subjects)}. Next link: {'Yes' if next_link else 'No'}")
            if not next_link or not batch_subjects:
                break
        subjects = subjects[:max_subjects]
        logger.info(f"Collected {len(subjects)} subjects for analysis for job {job_id}.")

    except Exception as e:
        logger.error(f"Failed to fetch email subjects for analysis for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve email subjects for analysis.")

    if not subjects:
         logger.warning(f"No subjects found matching criteria for job {job_id}. Aborting analysis submission.")
         return {"message": "No emails found matching the criteria. Analysis not submitted.", "job_id": job_id}

    # Construct webhook URL - Use the environment-specific base URL
    webhook_callback_path = "/analysis"
    webhook_url = f"{settings.EXTERNAL_WEBHOOK_BASE_URL.rstrip('/')}/{settings.WEBHOOK_PREFIX.strip('/')}/{webhook_callback_path.strip('/')}"

    if not settings.EXTERNAL_ANALYSIS_URL:
        logger.error(f"Analysis service URL is not configured.")
        raise HTTPException(status_code=500, detail="Analysis service URL is not configured.")

    # --- Get API Key for External Service ---
    api_key = settings.EXTERNAL_ANALYSIS_API_KEY
    if not api_key:
        logger.error(f"EXTERNAL_ANALYSIS_API_KEY is not set for job {job_id}.")
        raise HTTPException(status_code=500, detail="Analysis service API key is not configured.")
    # --- End Get API Key ---

    # Prepare headers for the external service
    request_headers = {
        "X-API-Key": api_key, # CORRECTED: Use the retrieved api_key
        "Content-Type": "application/json"
    }

    # Payload for the external service
    external_payload = {
        "subjects": subjects,
        "webhook_url": webhook_url,
        "job_id": job_id
    }

    logger.info(f"Submitting job {job_id} for owner {owner} with {len(subjects)} subjects to external service at {settings.EXTERNAL_ANALYSIS_URL}")
    logger.info(f"Webhook URL for callback: {webhook_url}")

    # Use background task to submit to external service and store mapping
    background_tasks.add_task(
        submit_and_map_analysis,
        url=settings.EXTERNAL_ANALYSIS_URL,
        payload=external_payload,
        headers=request_headers, # Pass the correct headers
        qdrant=qdrant,
        internal_job_id=job_id,
        owner=owner
    )

    # Return immediately to the user
    return {"message": "Analysis job submission initiated.", "job_id": job_id}


async def submit_and_map_analysis(url: str, payload: dict, headers: dict, qdrant: QdrantClient, internal_job_id: str, owner: str):
    """
    Runs in the background to:
    1. Submit the analysis request to the external service using the provided headers.
    2. Store the mapping between the external service's job ID and our internal job ID.
    """
    # The 'headers' dict received already contains the correct 'X-API-Key'
    # No need to re-fetch or reconstruct headers here.

    logger.info(f" [TASK: {internal_job_id}] Submitting analysis request with headers: {headers}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers, # Use the headers dictionary passed directly as argument
            )
            logger.info(f" [TASK: {internal_job_id}] HTTP Request: POST {url} \"HTTP/{response.http_version} {response.status_code} {response.reason_phrase}\"")
            response.raise_for_status()

            # Store External Job ID Mapping
            try:
                response_data = response.json()
                external_job_id = response_data.get("job_id")

                if external_job_id:
                    external_job_id_str = str(external_job_id)
                    logger.info(f" [TASK: {internal_job_id}] External service returned its job_id: {external_job_id_str}")
                    
                    # Revert to using a UUID for the mapping point ID
                    mapping_point_id = str(uuid.uuid4()) 
                    
                    mapping_payload = {
                        "type": "external_job_mapping",
                        "external_job_id": external_job_id_str, # Add field back to payload
                        "internal_job_id": internal_job_id,
                        "owner": owner
                    }
                    # Log the exact payload being stored
                    logger.info(f" [TASK: {internal_job_id}] Storing mapping point payload: {mapping_payload} with Qdrant ID: {mapping_point_id}") 

                    mapping_point = PointStruct(
                        id=mapping_point_id, # Use generated UUID as Qdrant point ID
                        payload=mapping_payload,
                        vector=[0.0] * settings.EMBEDDING_DIMENSION
                    )

                    try:
                        qdrant.upsert(
                            collection_name=settings.QDRANT_COLLECTION_NAME,
                            points=[mapping_point],
                            wait=True
                        )
                        logger.info(f" [TASK: {internal_job_id}] Successfully stored external->internal job mapping for external_id {external_job_id_str} with Qdrant ID {mapping_point_id}.")
                        
                        # --- Add immediate retrieve check --- 
                        try:
                            logger.info(f" [TASK: {internal_job_id}] Attempting immediate retrieval of mapping point ID: {mapping_point_id}")
                            retrieved = qdrant.retrieve(
                                collection_name=settings.QDRANT_COLLECTION_NAME,
                                ids=[mapping_point_id],
                                with_payload=True
                            )
                            if retrieved and len(retrieved) == 1:
                                logger.info(f" [TASK: {internal_job_id}] IMMEDIATE RETRIEVAL CONFIRMED for mapping point ID: {mapping_point_id}")
                            else:
                                logger.warning(f" [TASK: {internal_job_id}] IMMEDIATE RETRIEVAL FAILED for mapping point ID: {mapping_point_id}. Count: {len(retrieved) if retrieved else 0}")
                        except Exception as r_err:
                            logger.error(f" [TASK: {internal_job_id}] Error during immediate retrieval check for mapping point ID {mapping_point_id}: {r_err}")
                        # --- End immediate retrieve check --- 
                            
                    except Exception as q_err:
                        logger.error(f" [TASK: {internal_job_id}] Failed to store external job ID mapping in Qdrant for external_id {external_job_id}: {q_err}")
                else:
                    logger.warning(f" [TASK: {internal_job_id}] External analysis service response did not contain the expected 'job_id' field in its response.")

            except Exception as json_err:
                logger.error(f" [TASK: {internal_job_id}] Failed to parse JSON response or get external job_id from external service: {json_err}. Response text: {response.text}")

            logger.info(f" [TASK: {internal_job_id}] POST request completed. Status Code: {response.status_code}")

        except httpx.RequestError as exc:
            logger.error(f" [TASK: {internal_job_id}] Error submitting job to external service: {exc}")
        except httpx.HTTPStatusError as exc:
             logger.error(f" [TASK: {internal_job_id}] External service returned error: Status {exc.response.status_code} - {exc.response.text}")