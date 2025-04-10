from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging

# Qdrant imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct, Filter, FieldCondition, MatchValue
from qdrant_client.http.exceptions import UnexpectedResponse

# Import EmailFilter model
from app.models.email import EmailVectorData, ReviewStatus, EmailFilter
from app.models.user import User, UserDB
from app.dependencies.auth import get_current_active_user
# Import only create_embedding, as search_similar was removed/renamed
from app.services.embedder import create_embedding 
from app.config import settings
# Import Qdrant client functions
from app.db.qdrant_client import get_qdrant_client, ensure_collection_exists
from app.services.outlook import OutlookService # Ensure this is imported
# +++ Import DB Session Dependency +++
from app.db.session import get_db as get_sql_db # Rename to avoid conflict
from sqlalchemy.orm import Session
# --- End Import ---

# --- Import Celery Task --- 
from app.tasks import process_user_emails
# --- End Import --- 

router = APIRouter()
logger = logging.getLogger("app")

# Dependency to get Qdrant client 
# The collection check is now handled by the startup event in main.py
async def get_db() -> QdrantClient:
    client = get_qdrant_client()
    return client

@router.post("/embed", response_model=Dict[str, Any])
async def embed_email(
    email_id: str,
    content: str,
    metadata: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    client: QdrantClient = Depends(get_db)
):
    """Create embedding for approved email content and store in the user's embedding collection"""
    logger.info(f"Received request to embed email ID: {email_id} for owner: {current_user.email}")

    # Validate required metadata (as per schema doc)
    required_meta = [
        'owner', 'sender', 'subject', 'date', 'has_attachments', 'folder',
        'tags', 'analysis_status', 'status', 'source', 'raw_text',
        'attachments', 'query_criteria', # Added new fields from v3 schema
        'attachment_count' # Added count field
    ]
    if not all(key in metadata for key in required_meta):
        missing_keys = [key for key in required_meta if key not in metadata]
        logger.error(f"Missing required metadata keys: {missing_keys}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required metadata keys: {missing_keys}"
        )

    # Ensure owner matches current user for security
    if metadata.get('owner') != current_user.email:
         logger.error(f"Metadata owner '{metadata.get('owner')}' does not match authenticated user '{current_user.email}'")
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Cannot embed email for a different owner."
         )

    # Generate embedding
    try:
        embedding = await create_embedding(content)
    except Exception as e:
        logger.error(f"Failed to create embedding for email ID {email_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create embedding: {str(e)}"
        )

    # Calculate attachment count and add to metadata
    metadata['attachment_count'] = len(metadata.get('attachments', []))

    # Prepare point for Qdrant
    point_id = str(uuid.uuid4()) 
    point = PointStruct(
        id=point_id,
        vector=embedding,
        payload=metadata
    )

    # Determine user-specific collection name for embeddings
    sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
    target_collection_name = f"{sanitized_email}_email_knowledge" # Use correct embedding pattern
    
    # Ensure the user-specific collection exists
    try:
        ensure_collection_exists(client, target_collection_name, settings.EMBEDDING_DIMENSION)
        logger.info(f"Ensured collection '{target_collection_name}' exists.")
    except Exception as e:
        logger.error(f"Failed to ensure collection '{target_collection_name}' exists: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to access vector collection: {str(e)}")

    # Upsert into user-specific embedding Qdrant collection
    try:
        logger.info(f"Upserting point ID {point_id} into collection '{target_collection_name}'")
        client.upsert(
            collection_name=target_collection_name, # Use correct user-specific name
            points=[point],
            wait=True
        )
        logger.info(f"Successfully upserted point ID {point_id} into {target_collection_name}")
        return {"status": "success", "vector_id": point_id, "email_id": email_id}
    except Exception as e:
        logger.error(f"Failed to upsert point ID {point_id} into Qdrant collection {target_collection_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store vector in database: {str(e)}"
        )

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_vectors(
    query: str,
    limit: int = Query(10, ge=1, le=100),
    folder: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    client: QdrantClient = Depends(get_db)
):
    """Search for similar vectors within the user's specific RAG knowledge base collection."""
    logger.info(f"Received search request: '{query}' for owner: {current_user.email}")
    try:
        # *** CORRECTED: Target the knowledge_base collection for RAG search ***
        sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
        target_collection_name = f"{sanitized_email}_knowledge_base" # Use knowledge_base pattern
        logger.info(f"Targeting search in RAG collection: {target_collection_name}")

        # Generate embedding for the query
        query_embedding = await create_embedding(query)

        # Build Qdrant filters (logic remains the same)
        # Ensure the filter keys (folder, tags, status, date) exist in the _knowledge_base payload
        qdrant_filter = models.Filter(must=[])
        if folder:
            qdrant_filter.must.append(models.FieldCondition(key="folder", match=models.MatchValue(value=folder)))
        if tags:
            for tag in tags:
                 qdrant_filter.must.append(models.FieldCondition(key="tags", match=models.MatchValue(value=tag)))
        if status_filter:
             qdrant_filter.must.append(models.FieldCondition(key="status", match=models.MatchValue(value=status_filter)))
        range_conditions = {}
        if start_date:
             range_conditions['gte'] = start_date 
        if end_date:
             range_conditions['lte'] = end_date
        if range_conditions:
             qdrant_filter.must.append(models.FieldCondition(key="date", range=models.Range(**range_conditions)))

        # Search Qdrant using the RAG user-specific collection name
        search_result = client.search(
            collection_name=target_collection_name, # Use RAG name
            query_vector=query_embedding,
            query_filter=qdrant_filter if qdrant_filter.must else None,
            limit=limit,
            with_payload=True
        )

        # Format results (logic remains the same)
        formatted_results = [
            {
                "id": hit.id,
                "score": hit.score,
                "metadata": hit.payload
            }
            for hit in search_result
        ]
        logger.info(f"Search completed in {target_collection_name}. Found {len(formatted_results)} results.")
        return formatted_results

    except Exception as e:
        # Include target collection name in error logging
        target_collection_name_on_error = f"{current_user.email.replace('@', '_').replace('.', '_')}_knowledge_base"
        logger.error(f"Search failed in collection {target_collection_name_on_error}: {str(e)}", exc_info=True)
        # Check if collection not found specifically
        if isinstance(e, UnexpectedResponse) and e.status_code == 404:
             logger.warning(f"Collection '{target_collection_name_on_error}' not found during search.")
             return [] # Return empty list if collection doesn't exist for the user
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

@router.delete("/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vector(
    point_id: str, # Use the Qdrant point ID
    current_user: User = Depends(get_current_active_user),
    client: QdrantClient = Depends(get_db)
):
    """Delete a vector point from Qdrant, ensuring owner match."""
    logger.info(f"Received request to delete point ID: {point_id} for owner: {current_user.email}")
    try:
        # Optional but recommended: Retrieve the point first to verify owner
        retrieve_result = client.retrieve(collection_name=settings.QDRANT_COLLECTION_NAME, ids=[point_id], with_payload=True)
        if not retrieve_result:
            logger.warning(f"Point ID {point_id} not found for deletion.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vector point not found.")
        
        point_payload = retrieve_result[0].payload
        if point_payload.get("owner") != current_user.email:
            logger.error(f"Attempt to delete point {point_id} belonging to owner {point_payload.get('owner')} by user {current_user.email}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete vector point belonging to another user.")
        
        # Delete the point
        client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=models.PointIdsList(points=[point_id]),
            wait=True
        )
        logger.info(f"Successfully deleted point ID: {point_id}")
        return None # Return None for 204 No Content response

    except HTTPException as http_exc: # Re-raise specific HTTP exceptions
        raise http_exc
    except Exception as e:
        logger.error(f"Failed to delete point ID {point_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete vector: {str(e)}"
        )

@router.post("/save_job/{job_id}", status_code=status.HTTP_200_OK)
async def save_job_to_knowledge_base(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    qdrant_client: QdrantClient = Depends(get_db) 
):
    """Fetches emails based on stored criteria for a job_id and stores them in Qdrant."""
    logger.info(f"Received request to save emails for job_id: {job_id} to knowledge base by owner: {current_user.email}")

    # --- 1. Retrieve Query Criteria and Analysis Results from Qdrant ---
    query_point_id = f"query_{job_id}"
    chart_point_id = f"chart_{job_id}"
    filter_criteria_obj = None
    analysis_results_map = {}

    try:
        logger.info(f"Retrieving job metadata for job_id: {job_id}")
        # Search for the query_criteria point based on payload.job_id
        search_filter=Filter(
            must=[
                FieldCondition(key="payload.type", match=MatchValue(value="query_criteria")),
                FieldCondition(key="payload.job_id", match=MatchValue(value=job_id))
            ]
        )
        logger.info(f"[SAVE_JOB] Searching Qdrant for query_criteria with filter: {search_filter.model_dump_json(indent=2)}")
        
        search_result = qdrant_client.search(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query_vector=[0.0] * settings.EMBEDDING_DIMENSION, # Dummy vector
            query_filter=search_filter,
            limit=1,
            with_payload=True
        )
        
        # search returns a list of ScoredPoint
        if not search_result:
            logger.error(f"Job metadata point (query_criteria) not found in Qdrant for job_id: {job_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job metadata point not found.")
        
        # Since limit=1, we expect only one point
        point = search_result[0] # Get the first ScoredPoint
        payload = point.payload
        
        # Check owner (already verified type via filter)
        if payload.get("owner") != current_user.email:
             logger.error(f"User {current_user.email} attempted to save job {job_id} owned by {payload.get('owner')}")
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot save job belonging to another user.")
        
        # Attempt to parse the filter criteria
        # Renamed key check from 'filter' to 'criteria' to match email.py storage
        criteria_data = payload.get("criteria") 
        if not criteria_data or not isinstance(criteria_data, dict):
             logger.error(f"'criteria' key missing or not a dictionary in query_criteria payload for job {job_id}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid query criteria payload found.")
        
        try:
             filter_criteria_obj = EmailFilter(**criteria_data)
             logger.info(f"Retrieved and parsed query criteria for job {job_id}")
        except Exception as parse_error:
             logger.error(f"Failed to parse 'criteria' data into EmailFilter model for job {job_id}: {parse_error}", exc_info=True)
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to parse stored query criteria.")
        else:
            # If the retrieved point is not type 'query_criteria'
            logger.error(f"Retrieved point for job_id {job_id} has unexpected type: {payload.get('type')}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job metadata point has incorrect type.")
        
        # NOTE: Analysis results (chart data) are not directly used in this simplified flow 
        # where we save emails without waiting for analysis. We proceed using only filter_criteria_obj.
        logger.info(f"Proceeding to fetch emails for job {job_id} using filter criteria.")

    except HTTPException as http_exc:
        raise http_exc # Re-raise permission errors etc.
    except Exception as e:
        logger.error(f"Failed to retrieve job metadata from Qdrant for job_id {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve job metadata.")

    # --- 2. Fetch Full Email Details using Outlook Service --- 
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        # This check might be redundant due to Depends(get_current_active_user), but good practice
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Microsoft access token not available")

    outlook = OutlookService(current_user.ms_token_data.access_token)
    points_to_upsert: List[PointStruct] = []
    processed_email_count = 0
    failed_email_count = 0
    all_email_ids = [] # Initialize list to store all IDs
    PAGE_SIZE = 100 # How many previews to fetch per page

    try:
        logger.info(f"Fetching all email IDs via pagination for job {job_id} using criteria: {filter_criteria_obj.model_dump_json()}")
        current_next_link = None
        page_num = 1
        
        while True:
            logger.info(f"Fetching page {page_num} of email previews (size: {PAGE_SIZE})...")
            params = filter_criteria_obj.model_dump(exclude_none=True) # Start with filter criteria
            params['per_page'] = PAGE_SIZE
            if current_next_link:
                params['next_link'] = current_next_link # Add next_link if available
            
            # Call the correct paginated service method
            paged_result_dict = await outlook.get_email_preview(**params)
            
            # Convert the dictionary result back into an object if needed, or use directly
            # Assuming the return type includes items and next_link directly in the dict
            items_on_page_raw = paged_result_dict.get("items", [])
            current_next_link = paged_result_dict.get("next_link")

            if items_on_page_raw:
                 # Assuming items are dictionaries that conform to EmailPreview or have an 'id'
                 ids_on_page = [item['id'] for item in items_on_page_raw if item.get('id')]
                 all_email_ids.extend(ids_on_page)
                 logger.info(f"Fetched {len(ids_on_page)} IDs from page {page_num}. Total IDs so far: {len(all_email_ids)}.")
            else:
                logger.info(f"No items found on page {page_num}.")

            if not current_next_link:
                logger.info(f"No more pages found. Finished fetching IDs.")
                break # Exit loop if no more pages
            
            page_num += 1
            # Optional: Add a small delay or check loop limits to prevent infinite loops

        logger.info(f"Found {len(all_email_ids)} total email IDs matching criteria for job {job_id}. Fetching content...")

        # Now loop through the collected IDs
        for email_id in all_email_ids:
            try:
                logger.debug(f"Fetching content for email_id: {email_id}")
                email_content = await outlook.get_email_content(email_id)
                
                logger.debug(f"Processing email subject: {email_content.subject}")
                
                # --- 3. Prepare Metadata and Vector for Each Email --- 
                analysis_tags = analysis_results_map.get(email_content.subject, {}).get("tag", "untagged") # Get tag or default
                # Ensure tags is always a list
                if isinstance(analysis_tags, str):
                    tags_list = [analysis_tags]
                elif isinstance(analysis_tags, list):
                    tags_list = analysis_tags
                else:
                    tags_list = ["untagged"] # Default if unexpected type

                # Prepare attachments (Base64 encode here? Or assume already done?)
                # Assuming get_email_content includes attachments with Base64 for now (DEMO)
                attachments_payload = []
                if email_content.attachments:
                    for att in email_content.attachments:
                        # Check if 'content' field exists and is not None
                        content_base64 = att.content if hasattr(att, 'content') and att.content is not None else None 
                        if content_base64 is None:
                            logger.warning(f"Attachment {att.name} for email {email_id} is missing base64 content in the 'content' field.")
                        attachments_payload.append({
                            "filename": att.name,
                            "mimetype": att.content_type, # Corrected: content_type
                            "size": att.size,
                            "content_base64": content_base64 # Corrected: content
                        })

                # Determine has_attachments based on the list
                has_attachments_bool = len(email_content.attachments) > 0 if email_content.attachments else False

                email_metadata = {
                    "type": "email",
                    "job_id": job_id,
                    "owner": current_user.email,
                    "sender": email_content.sender if email_content.sender else "unknown@sender.com", 
                    "subject": email_content.subject or "",
                    "date": email_content.received_date or "", # Corrected: received_date (already string)
                    "has_attachments": has_attachments_bool, # Corrected: derived from attachments list
                    "folder": filter_criteria_obj.folder_id, 
                    "tags": tags_list,
                    "analysis_status": "pending",
                    "status": "reviewed", 
                    "source": "email",
                    "raw_text": email_content.body or "", # Corrected: body (already string)
                    "attachments": attachments_payload,
                    "attachment_count": len(attachments_payload),
                    "query_criteria": filter_criteria_obj.model_dump()
                }

                # Generate embedding for the email body
                email_body = email_metadata["raw_text"]
                if not email_body:
                    logger.warning(f"Email ID {email_id} has empty body, using subject for embedding.")
                    email_body = email_metadata["subject"]
                
                embedding = await create_embedding(email_body)

                # Create Qdrant point
                # Generate a new UUID for the Qdrant point ID
                qdrant_point_uuid = str(uuid.uuid4()) 
                # Add original email_id to metadata for reference
                email_metadata['original_email_id'] = email_id 

                point = PointStruct(
                    id=qdrant_point_uuid, # Use the newly generated UUID
                    vector=embedding,
                    payload=email_metadata
                )
                points_to_upsert.append(point)
                processed_email_count += 1
                logger.debug(f"Prepared point {qdrant_point_uuid} (original email: {email_id}) for upsert.")

            except Exception as fetch_err:
                failed_email_count += 1
                logger.error(f"Failed to fetch or process email_id {email_id} for job {job_id}: {str(fetch_err)}", exc_info=True)
                # Continue processing other emails

    except Exception as outer_err:
         logger.error(f"Error during email fetching loop for job {job_id}: {str(outer_err)}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error occurred while fetching email details.")

    # --- 4. Batch Upsert Email Points to Qdrant --- 
    if points_to_upsert:
        try:
            logger.info(f"Upserting {len(points_to_upsert)} email points to Qdrant for job {job_id}...")
            qdrant_client.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=points_to_upsert,
                wait=True
            )
            logger.info(f"Successfully upserted {len(points_to_upsert)} email points for job {job_id}.")
        except Exception as e:
            logger.error(f"Failed to batch upsert email points for job {job_id} into Qdrant: {str(e)}", exc_info=True)
            # Don't raise error here, just report partial success/failure
            return {
                "job_id": job_id,
                "message": f"Attempted to save job. Processed: {processed_email_count}, Failed Fetch/Process: {failed_email_count}, Failed Qdrant Upsert: {len(points_to_upsert)}",
                "status": "partial_failure"
            }
    else:
        logger.warning(f"No email points were prepared for upsert for job {job_id} (fetch/process errors: {failed_email_count})")

    return {
        "job_id": job_id,
        "message": f"Job save completed. Emails Processed: {processed_email_count}, Fetch/Process Errors: {failed_email_count}",
        "status": "success" if failed_email_count == 0 else "partial_success"
    }

# --- New Endpoint for Saving Filtered Emails --- 

@router.post("/save_filtered_emails", status_code=status.HTTP_202_ACCEPTED, response_model=Dict[str, str])
async def save_filtered_emails_to_knowledge_base(
    filter_input: EmailFilter, # Accept filter directly in request body
    current_user: User = Depends(get_current_active_user),
    # +++ Add DB session dependency +++
    db: Session = Depends(get_sql_db)
    # --- End Add ---
    # qdrant_client: QdrantClient = Depends(get_db) # Qdrant client not needed directly here anymore
):
    """Accepts email filter criteria and dispatches a background task to process and store emails."""
    operation_id = str(uuid.uuid4())
    owner_email = current_user.email
    logger.info(f"[Op:{operation_id}] Received request to save emails to knowledge base by owner: {owner_email} using filter: {filter_input.model_dump_json()}")

    # Basic validation (token check might be implicitly handled by dependency)
    # We rely on the task to handle token refresh and validation internally

    # Dispatch the Celery task
    try:
        # Convert filter model to dict for Celery serialization
        filter_dict = filter_input.model_dump(mode='json')
        
        logger.info(f"[Op:{operation_id}] Dispatching Celery task 'process_user_emails' for user {owner_email}.")
        task = process_user_emails.delay(user_id=owner_email, filter_criteria_dict=filter_dict)
        logger.info(f"[Op:{operation_id}] Task dispatched with ID: {task.id}")
        
        # +++ Store task ID on user record +++
        try:
            # Re-fetch the DB user to update them using the injected session 'db'
            # Make sure UserDB model is imported at the top of the file
            db_user = db.query(UserDB).filter(UserDB.email == owner_email).first()
            if db_user:
                db_user.last_kb_task_id = task.id
                db.commit()
                logger.info(f"[Op:{operation_id}] Stored task ID {task.id} for user {owner_email}.")
            else:
                logger.error(f"[Op:{operation_id}] Could not find user {owner_email} in DB to store task ID.")
        except Exception as db_error:
            db.rollback() # Rollback on error
            logger.error(f"[Op:{operation_id}] Failed to store task ID for user {owner_email}: {db_error}", exc_info=True)
        # --- End Store task ID ---

        # Return the task ID to the client
        return {"task_id": task.id, "message": "Email processing task accepted."}

    except Exception as e:
        logger.error(f"[Op:{operation_id}] Failed to dispatch Celery task for user {owner_email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate email processing task."
        )
