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

from app.models.email import EmailPreview, EmailFilter, EmailContent, PaginatedEmailPreviewResponse
from app.services.outlook import OutlookService
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.config import settings
from app.routes.vector import get_db
from ..db.qdrant_client import get_qdrant_client

router = APIRouter()

logger = logging.getLogger("app")

class AnalysisJob(BaseModel):
    job_id: str


@router.get("/folders", response_model=List[dict])
async def list_folders(current_user: User = Depends(get_current_active_user)):
    """Get list of email folders from Outlook"""
    if not current_user.ms_access_token:
        logger.error(f"User {current_user.email} has no ms_access_token attached. Cannot call MS Graph.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available or expired in session"
        )
    
    try:
        outlook = OutlookService(current_user.ms_access_token)
        folders = await outlook.get_email_folders()
        return folders
    except Exception as e:
        logger.error(f"Error fetching folders for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch folders: {str(e)}"
        )


@router.post("/preview", response_model=PaginatedEmailPreviewResponse)
async def preview_emails(
    filter_params: EmailFilter,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user)
):
    """Get preview of emails based on filter criteria"""
    try:
        if not current_user.ms_access_token:
            raise HTTPException(
                status_code=401,
                detail="Microsoft access token not available"
            )

        outlook = OutlookService(current_user.ms_access_token)
        
        next_link = filter_params.next_link 
        # Directly use filter_params.keywords if provided
        keywords_from_filter = filter_params.keywords or []
        keywords_list = [kw for kw in keywords_from_filter if kw and kw.strip()]
        
        logger.debug(f"Fetching email previews with filter: {filter_params.dict(exclude={'next_link'})}, Page: {page}, Per Page: {per_page}, Next Link: {next_link}, Processed Keywords: {keywords_list}")

        # Call the correct method with adjusted parameters
        preview_data = await outlook.get_email_preview(
            folder_id=filter_params.folder_id,
            keywords=keywords_list if keywords_list else None, # Use the processed list
            start_date=filter_params.start_date,
            end_date=filter_params.end_date,
            next_link=next_link, 
            per_page=per_page, 
            # Use sender directly from filter_params
            sender=filter_params.sender,
            # Pass other params that get_email_preview might expect via kwargs, 
            # if they were part of the old EmailFilter or are needed.
            # has_attachments=filter_params.has_attachments, # Example if needed
            # from_address=filter_params.from_address, # Example if needed
            # to_address=filter_params.to_address, # Example if needed
        )
        
        # +++ ADD LOG IMMEDIATELY AFTER SERVICE CALL +++
        service_next_link = preview_data.get('next_link')
        logger.info(f"[SERVICE RETURN CHECK] Service returned preview_data with next_link: {service_next_link}")
        # --- END LOG ---

        logger.debug(f"Received preview data structure: keys={preview_data.keys()}")
        
        response_data = PaginatedEmailPreviewResponse(
            items=preview_data.get('items', []),
            total=preview_data.get('total'),
            next_link=service_next_link # Use the variable we just logged
        )

        logger.info(f"[RETURN CHECK] Returning response_data with next_link: {response_data.next_link}")

        return response_data

    except AttributeError as ae:
        # This specific error should be resolved now, but keep the handler
        logger.error(f"AttributeError calling OutlookService or processing filters: {ae}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error processing email request (AttributeError).")
    except Exception as e:
        logger.error(f"Error fetching email previews: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{email_id}", response_model=EmailContent)
async def get_email(
    email_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get full content of a specific email"""
    if not current_user.ms_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    
    try:
        outlook = OutlookService(current_user.ms_access_token)
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
    current_user: User = Depends(get_current_active_user)
):
    """Get email attachment by ID"""
    if not current_user.ms_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    
    try:
        outlook = OutlookService(current_user.ms_access_token)
        attachment = await outlook.get_email_attachment(email_id, attachment_id)
        return attachment
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch attachment: {str(e)}"
        )


@router.post("/analyze", status_code=202)
async def analyze_emails(
    filter_criteria: EmailFilter,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_active_user),
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
    if not current_user.ms_access_token:
        logger.warning(f"Analysis request failed for {owner}: Microsoft access token not available.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft access token not available"
        )
    # --- End Token Check ---

    # --- Instantiate Outlook Service ---
    try:
        outlook = OutlookService(current_user.ms_access_token)
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
        logger.info(f"Stored query criteria for job_id {job_id} with owner {owner} (Qdrant Point ID: {query_point_id})")

        # Immediate retrieval check for the query_criteria point RIGHT AFTER initial upsert
        try:
            retrieved_query = qdrant.retrieve(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                ids=[query_point_id],
                with_payload=True
            )
            if retrieved_query and retrieved_query[0].id == query_point_id:
                logger.info(f"[IMMEDIATE QUERY CRITERIA RETRIEVAL CONFIRMED IN MAIN] Query criteria point {query_point_id} found immediately after initial upsert.")
            else:
                 logger.error(f"[FAILED IMMEDIATE QUERY CRITERIA RETRIEVAL IN MAIN] Query criteria point {query_point_id} NOT found immediately after initial upsert.")
                 # Optionally raise an error here if this is critical
                 raise HTTPException(status_code=500, detail="Failed critical step: Could not verify query criteria storage.")
        except Exception as query_retrieval_err:
            logger.error(f"[FAILED IMMEDIATE QUERY CRITERIA RETRIEVAL IN MAIN] Error retrieving query criteria point {query_point_id}: {query_retrieval_err}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed critical step: Error verifying query criteria storage.")

    except Exception as e:
        logger.error(f"Failed to store query criteria in Qdrant for job_id {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize analysis job storage.")

    # Fetch email subjects using the CORRECT preview method and keywords
    subjects = []
    next_link_page = None # Use a different var name to avoid confusion
    max_subjects = 200 
    try:
        # --- Prepare keywords --- 
        keywords_from_filter = filter_criteria.keywords or []
        analysis_keywords = [kw for kw in keywords_from_filter if kw and kw.strip()]
        # --- End Keywords --- 

        while len(subjects) < max_subjects:
            logger.debug(f"Analysis: Fetching email previews. Current count: {len(subjects)}. Max: {max_subjects}")
            preview_result = await outlook.get_email_preview( # Use get_email_preview
                folder_id=filter_criteria.folder_id,
                keywords=analysis_keywords if analysis_keywords else None, # Pass keywords
                start_date=filter_criteria.start_date,
                end_date=filter_criteria.end_date,
                sender=filter_criteria.sender, # Pass sender
                per_page=50, # Fetch larger batches for analysis
                next_link=next_link_page # Pass the pagination link
                # Add other filters if needed (has_attachments etc.)
            )
            batch_items = preview_result.get('items', [])
            batch_subjects = [item['subject'] for item in batch_items if item.get('subject')]
            subjects.extend(batch_subjects)
            next_link_page = preview_result.get('next_link') # Update pagination link
            logger.debug(f"Analysis: Fetched {len(batch_subjects)} subjects. Total now: {len(subjects)}. Next link: {'Yes' if next_link_page else 'No'}")
            if not next_link_page or not batch_items: # Stop if no next link OR no items were returned in batch
                break
        subjects = subjects[:max_subjects]
        logger.info(f"Collected {len(subjects)} subjects for analysis for job {job_id}.")

    except Exception as e:
        logger.error(f"Failed to fetch email subjects for analysis for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve email subjects for analysis.")

    if not subjects:
         logger.warning(f"No subjects found matching criteria for job {job_id}. Aborting analysis submission.")
         return {"message": "No emails found matching the criteria. Analysis not submitted.", "job_id": job_id}

    # Construct webhook URL - Use the environment-specific base URL
    webhook_base = settings.EXTERNAL_WEBHOOK_BASE_URL.rstrip('/')
    webhook_path = settings.WEBHOOK_PREFIX.strip('/') # From .env
    webhook_url = f"{webhook_base}/{webhook_path}/analysis?job_id={job_id}"
    logger.info(f"Webhook URL for callback: {webhook_url}")

    # --- Adjust Payload and Headers for External API --- 
    analysis_payload = {
        "subjects": subjects, # Use "subjects" key
        "callback_url": webhook_url
    }
    headers = {
        "X-API-Key": settings.EXTERNAL_ANALYSIS_API_KEY, # Use "X-API-Key" header
        "Content-Type": "application/json"
    }
    # --- End Adjustment --- 

    external_job_id = None
    try:
        logger.info(f"Submitting {len(subjects)} subjects to external analysis service: {settings.EXTERNAL_ANALYSIS_URL}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.EXTERNAL_ANALYSIS_URL,
                json=analysis_payload, # Send corrected payload
                headers=headers, # Send corrected headers
                timeout=60.0
            )
            response.raise_for_status() # Raise exception for non-2xx responses
            response_data = response.json()
            
            # --- Use the correct field name from the API response --- 
            external_job_id = response_data.get("job_id") # Changed from "request_id"
            # --- End Correction ---

            if not external_job_id:
                 # Update error message to reflect the field we looked for
                 logger.error(f"External analysis API response missing 'job_id' (or expected ID field). Response: {response_data}") 
                 raise HTTPException(status_code=500, detail="Failed to get job ID from external analysis service.")
            
            logger.info(f"External analysis service accepted request. External Job ID: {external_job_id}")
            
            # --- Store external_job_id in Qdrant ---
            try:
                logger.info(f"Updating Qdrant point {query_point_id} with external_job_id: {external_job_id}")
                qdrant.set_payload(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    payload={"external_job_id": external_job_id},
                    points=[query_point_id], # Use the ID of the point we created earlier
                    wait=True # Ensure payload is updated before proceeding
                )
                logger.info(f"Successfully updated Qdrant point {query_point_id} for internal job {job_id}")
            except Exception as e:
                 logger.error(f"Failed to update Qdrant point {query_point_id} with external_job_id for internal job {job_id}: {e}", exc_info=True)
                 # Decide if this is critical - maybe raise an error?
                 # For now, log and continue, but webhook correlation will fail later.
                 raise HTTPException(status_code=500, detail="Failed to store external job ID mapping.")
            # --- End Qdrant Update ---
            
    except httpx.RequestError as e:
        logger.error(f"HTTP request error submitting to external analysis service: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to communicate with analysis service: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"External analysis service returned error {e.response.status_code}: {e.response.text}", exc_info=True)
        # Re-raise the specific error from the external service
        raise HTTPException(status_code=e.response.status_code, detail=f"Analysis service error: {e.response.text}")
    except Exception as e:
         logger.error(f"Unexpected error during external analysis submission for job {job_id}: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail="Failed to submit job for external analysis.")

    return {"message": "Analysis job submission initiated.", "job_id": job_id}