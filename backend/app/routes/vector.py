from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging

# Milvus imports (replacing Qdrant)
from pymilvus import MilvusClient
# Keep models/exceptions for now, will replace as needed
# from qdrant_client import models # Comment out Qdrant models
# from qdrant_client.http.models import PointStruct, Filter, FieldCondition, MatchValue # Comment out Qdrant HTTP models
# from qdrant_client.http.exceptions import UnexpectedResponse # Comment out Qdrant exceptions

# Import EmailFilter model
from app.models.email import EmailVectorData, ReviewStatus, EmailFilter
from app.models.user import User, UserDB
from app.dependencies.auth import get_current_active_user
# Import only create_embedding, as search_similar was removed/renamed
from app.services.embedder import create_embedding
from app.config import settings
# Import Milvus client functions (replacing Qdrant)
from app.db.milvus_client import get_milvus_client, ensure_collection_exists
# from app.db.qdrant_client import get_qdrant_client, ensure_collection_exists # Comment out Qdrant client import
from app.services.outlook import OutlookService # Ensure this is imported
# +++ Import DB Session Dependency +++
from app.db.session import get_db as get_sql_db # Rename to avoid conflict
from sqlalchemy.orm import Session
# --- End Import ---

# --- Import Celery Task --- 
# from app.tasks import process_user_emails # OLD Import
from app.tasks.email_tasks import process_user_emails # NEW Import from correct module
# --- End Import --- 

router = APIRouter()
logger = logging.getLogger("app")

# Dependency to get Milvus client (updated from Qdrant)
async def get_db() -> MilvusClient:
    client = get_milvus_client()
    return client

@router.post("/embed", response_model=Dict[str, Any])
async def embed_email(
    email_id: str,
    content: str,
    metadata: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    client: MilvusClient = Depends(get_db) # Updated type hint
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

    # Prepare data for Milvus, matching the defined schema
    point_id = str(uuid.uuid4()) 
    data_to_insert = {
        "pk": point_id, # Primary key
        "vector": embedding, # Vector field
        # Map known metadata fields to schema fields
        "owner": metadata.get('owner', current_user.email), # Use metadata owner or current user
        "source": metadata.get('source', 'unknown'), # e.g., 'email', 'manual_text', etc.
        "type": metadata.get('type', 'email'), # e.g., 'email', 'snippet', 'query_criteria'
        "email_id": email_id, # Original email ID if applicable
        "job_id": metadata.get('job_id', ''), # Job ID if associated
        "subject": metadata.get('subject', ''),
        "date": metadata.get('date', ''),
        "status": metadata.get('status', ''),
        "folder": metadata.get('folder', ''),
        # Store the rest of the metadata in the JSON field
        "metadata_json": metadata 
    }

    # Determine user-specific collection name for embeddings
    sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
    target_collection_name = f"{sanitized_email}_email_knowledge" # Use correct embedding pattern
    
    # Ensure the user-specific collection exists using the correct dimension
    try:
        # Use DENSE_EMBEDDING_DIMENSION which is likely the one used by create_embedding
        embedding_dimension = settings.DENSE_EMBEDDING_DIMENSION 
        ensure_collection_exists(client, target_collection_name, embedding_dimension)
        logger.info(f"Ensured collection '{target_collection_name}' exists.")
    except Exception as e:
        logger.error(f"Failed to ensure collection '{target_collection_name}' exists: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to access vector collection: {str(e)}")

    # Insert into user-specific embedding Milvus collection
    try:
        logger.info(f"Inserting point ID {point_id} into collection '{target_collection_name}'")
        # MilvusClient.insert expects a list of dictionaries
        insert_result = client.insert(collection_name=target_collection_name, data=[data_to_insert])
        logger.info(f"Successfully inserted point ID {point_id} into {target_collection_name}. Result: {insert_result}")
        # Return the Milvus PK (which we set as point_id)
        return {"status": "success", "vector_id": point_id, "email_id": email_id}
    except Exception as e:
        logger.error(f"Failed to insert point ID {point_id} into Milvus collection {target_collection_name}: {str(e)}", exc_info=True)
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
    client: MilvusClient = Depends(get_db) # Updated type hint
):
    """Search for similar vectors within the user's specific RAG knowledge base collection."""
    logger.info(f"Received search request: '{query}' for owner: {current_user.email}")
    try:
        # Determine target collection name (RAG collection)
        sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
        target_collection_name = f"{sanitized_email}_knowledge_base"
        logger.info(f"Targeting search in RAG collection: {target_collection_name}")

        # Ensure the collection exists (important for search)
        try:
            embedding_dimension = settings.DENSE_EMBEDDING_DIMENSION
            ensure_collection_exists(client, target_collection_name, embedding_dimension)
            logger.info(f"Ensured collection '{target_collection_name}' exists for search.")
        except Exception as e:
            # If ensuring collection fails (e.g., connection issue), re-raise
            logger.error(f"Failed to ensure collection '{target_collection_name}' exists before search: {str(e)}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to prepare vector collection for search: {str(e)}")

        # Generate embedding for the query
        query_embedding = await create_embedding(query)

        # Build Milvus Boolean Filter Expression
        filter_parts = []
        # Always filter by owner for security/tenancy
        filter_parts.append(f'owner == "{current_user.email}"')
        
        if folder:
            # Escape quotes within the folder name if necessary, though unlikely for folder IDs
            filter_parts.append(f'folder == "{folder}"') 
        if status_filter:
            filter_parts.append(f'status == "{status_filter}"')
        if start_date:
            filter_parts.append(f'date >= "{start_date}"') # Assuming date is stored as string YYYY-MM-DD
        if end_date:
            filter_parts.append(f'date <= "{end_date}"')
        if tags:
            # Filter using JSON_CONTAINS on the metadata_json field
            # Note: Performance depends on Milvus version and JSON indexing capabilities
            for tag in tags:
                 # Escape double quotes inside the tag string if they can occur
                 escaped_tag = tag.replace('"', '\"')
                 filter_parts.append(f'json_contains(metadata_json[\"tags\"], \"{escaped_tag}\")')

        # Combine filter parts with "and"
        filter_expression = " and ".join(filter_parts) if filter_parts else ""
        logger.info(f"Constructed Milvus filter expression: {filter_expression}")

        # Define search parameters
        search_params = {
            "metric_type": "COSINE", 
            "params": {"nprobe": 10} # Example search param, adjust as needed
        }

        # Execute search using MilvusClient
        logger.debug(f"Executing Milvus search in '{target_collection_name}' with limit {limit}")
        search_result = client.search(
            collection_name=target_collection_name,
            data=[query_embedding], # Query vector(s)
            anns_field="vector",    # Field name of the vector
            param=search_params,    # Search parameters
            limit=limit,            # Number of results to return
            filter=filter_expression, # Boolean expression for filtering
            output_fields=["pk", "metadata_json"] # Fields to retrieve
        )
        logger.debug(f"Milvus search completed. Raw result count: {len(search_result[0]) if search_result else 0}")

        # Format results
        formatted_results = []
        if search_result:
            hits = search_result[0] # Results for the first (and only) query vector
            for hit in hits:
                formatted_results.append({
                    "id": hit.id, # This is the 'pk' field value
                    "score": hit.distance, # Milvus returns distance (lower is better for COSINE/L2)
                    "metadata": hit.entity.get('metadata_json', {}) # Get the payload from metadata_json
                })
        
        logger.info(f"Search completed in {target_collection_name}. Found {len(formatted_results)} formatted results.")
        return formatted_results

    except Exception as e:
        target_collection_name_on_error = f"{current_user.email.replace('@', '_').replace('.', '_')}_knowledge_base"
        logger.error(f"Search failed in collection {target_collection_name_on_error}: {str(e)}", exc_info=True)
        # Check for collection not found specifically (adjust error message check if needed)
        if "collection not found" in str(e).lower() or "doesn't exist" in str(e).lower():
             logger.warning(f"Collection '{target_collection_name_on_error}' not found during search.")
             return [] # Return empty list if collection doesn't exist
        # Handle other potential Milvus errors (e.g., invalid filter expression)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

@router.delete("/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vector(
    point_id: str, # This is the PK (UUID) stored in Milvus
    current_user: User = Depends(get_current_active_user),
    client: MilvusClient = Depends(get_db) # Updated type hint
):
    """Delete a vector point from Milvus using its PK, ensuring owner match."""
    logger.info(f"Received request to delete point with PK: {point_id} for owner: {current_user.email}")
    
    # Determine target collection name (RAG collection)
    sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
    target_collection_name = f"{sanitized_email}_knowledge_base"
    logger.info(f"Targeting delete in RAG collection: {target_collection_name}")

    try:
        # Optional but recommended: Retrieve the point first to verify owner
        logger.debug(f"Retrieving point with PK {point_id} from {target_collection_name} to verify owner.")
        # Use Milvus query with corrected collection name, expression, and output fields
        query_result = client.query(
            collection_name=target_collection_name, 
            filter=f'pk == "{point_id}"', # Use pk field
            output_fields=["owner"] # Only need owner field
        )
        
        if not query_result:
            logger.warning(f"Point with PK {point_id} not found in {target_collection_name} for deletion.")
            # Raise 404 if the point doesn't exist
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vector point not found.")
        
        # Milvus query returns a list of dictionaries
        point_data = query_result[0] 
        retrieved_owner = point_data.get("owner")

        if retrieved_owner != current_user.email:
            logger.error(f"Attempt to delete point {point_id} belonging to owner '{retrieved_owner}' by user '{current_user.email}'")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete vector point belonging to another user.")
        
        # Delete the point using the primary key
        logger.debug(f"Owner verified. Deleting point with PK {point_id} from {target_collection_name}.")
        delete_result = client.delete(
            collection_name=target_collection_name, 
            filter=f'pk == "{point_id}"' # Use pk field
        )
        logger.info(f"Successfully deleted point with PK: {point_id} from {target_collection_name}. Result: {delete_result}")
        return None # Return None for 204 No Content response

    except HTTPException as http_exc: # Re-raise specific HTTP exceptions
        raise http_exc
    except Exception as e:
        # Handle potential Milvus client errors during query or delete
        logger.error(f"Failed to delete point PK {point_id} from {target_collection_name}: {str(e)}", exc_info=True)
        # Check if it was a collection not found error during query/delete
        if "collection not found" in str(e).lower() or "doesn't exist" in str(e).lower():
             logger.warning(f"Collection '{target_collection_name}' not found during delete operation for PK {point_id}.")
             # Technically the point doesn't exist, so maybe 404 is still appropriate?
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vector collection not found.") 
        # Otherwise, return a generic 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete vector: {str(e)}"
        )

@router.post("/save_job/{job_id}", status_code=status.HTTP_200_OK)
async def save_job_to_knowledge_base(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    client: MilvusClient = Depends(get_db) # Renamed variable to client
):
    """Fetches emails based on stored criteria for a job_id and stores them in Milvus knowledge base collection."""
    logger.info(f"Received request to save emails for job_id: {job_id} to knowledge base by owner: {current_user.email}")

    # --- 1. Retrieve Query Criteria --- 
    filter_criteria_obj = None
    sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
    # Assume criteria are stored in the primary email collection
    criteria_collection_name = f"{sanitized_email}_email_knowledge"

    try:
        logger.info(f"Retrieving job metadata for job_id: {job_id} from {criteria_collection_name}")
        # Use Milvus query to find the criteria point by type and job_id
        query_expression = f'type == "query_criteria" and job_id == "{job_id}"'
        logger.info(f"[SAVE_JOB] Querying Milvus ({criteria_collection_name}) with filter: {query_expression}")
        
        query_result = client.query(
            collection_name=criteria_collection_name, 
            filter=query_expression,
            limit=1, # Expect only one match
            output_fields=["owner", "metadata_json"] 
        )
                
        if not query_result:
            logger.error(f"Job metadata point (type='query_criteria') not found in Milvus for job_id: {job_id} in collection {criteria_collection_name}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job metadata point not found.")
        
        # Milvus query returns list of dicts
        point_data = query_result[0]
        retrieved_owner = point_data.get("owner")
        metadata_json = point_data.get("metadata_json", {})
        
        # Check owner 
        if retrieved_owner != current_user.email:
             logger.error(f"User {current_user.email} attempted to save job {job_id} owned by {retrieved_owner}")
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot save job belonging to another user.")
        
        # Attempt to parse the filter criteria from the metadata_json
        criteria_data = metadata_json.get("criteria") 
        if not criteria_data or not isinstance(criteria_data, dict):
             logger.error(f"'criteria' key missing or not a dictionary in metadata_json for job {job_id}")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid query criteria payload found.")
        
        try:
             filter_criteria_obj = EmailFilter(**criteria_data)
             logger.info(f"Retrieved and parsed query criteria for job {job_id}")
        except Exception as parse_error:
             logger.error(f"Failed to parse 'criteria' data from metadata_json for job {job_id}: {parse_error}", exc_info=True)
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to parse stored query criteria.")

    except HTTPException as http_exc:
        raise http_exc # Re-raise known HTTP errors
    except Exception as e:
        logger.error(f"Failed to retrieve job metadata from Milvus for job_id {job_id}: {str(e)}", exc_info=True)
        # Check for collection not found specifically
        if "collection not found" in str(e).lower() or "doesn't exist" in str(e).lower():
             logger.warning(f"Collection '{criteria_collection_name}' not found while retrieving job metadata for job {job_id}.")
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metadata collection not found.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve job metadata.")

    # --- 2. Fetch Full Email Details using Outlook Service --- 
    if not current_user.ms_token_data or not current_user.ms_token_data.access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Microsoft access token not available")

    outlook = OutlookService(current_user.ms_token_data.access_token)
    emails_to_insert = [] # Rename list for clarity
    processed_email_count = 0
    failed_email_count = 0
    all_email_ids = [] 
    PAGE_SIZE = 100
    target_kb_collection_name = f"{sanitized_email}_knowledge_base" # Target KB collection for insertion

    try:
        # Ensure the target KB collection exists before fetching emails
        embedding_dimension = settings.DENSE_EMBEDDING_DIMENSION
        ensure_collection_exists(client, target_kb_collection_name, embedding_dimension)
        logger.info(f"Ensured target knowledge base collection '{target_kb_collection_name}' exists.")
        
        # Fetch all email IDs (pagination logic seems okay)
        logger.info(f"Fetching all email IDs via pagination for job {job_id} using criteria: {filter_criteria_obj.model_dump_json()}")
        current_next_link = None
        page_num = 1
        while True:
            logger.info(f"Fetching page {page_num} of email previews (size: {PAGE_SIZE})...")
            params = filter_criteria_obj.model_dump(exclude_none=True)
            params['per_page'] = PAGE_SIZE
            if current_next_link:
                params['next_link'] = current_next_link
            paged_result_dict = await outlook.get_email_preview(**params)
            items_on_page_raw = paged_result_dict.get("items", [])
            current_next_link = paged_result_dict.get("next_link")
            if items_on_page_raw:
                 ids_on_page = [item['id'] for item in items_on_page_raw if item.get('id')]
                 all_email_ids.extend(ids_on_page)
                 logger.info(f"Fetched {len(ids_on_page)} IDs from page {page_num}. Total IDs so far: {len(all_email_ids)}.")
            else:
                logger.info(f"No items found on page {page_num}.")
            if not current_next_link:
                logger.info(f"No more pages found. Finished fetching IDs.")
                break
            page_num += 1
        logger.info(f"Found {len(all_email_ids)} total email IDs matching criteria for job {job_id}. Fetching content...")

        # Loop through IDs and prepare data for Milvus insertion
        for email_id in all_email_ids:
            try:
                logger.debug(f"Fetching content for email_id: {email_id}")
                email_content = await outlook.get_email_content(email_id)
                logger.debug(f"Processing email subject: {email_content.subject}")
                
                # Prepare metadata payload
                tags_list = [] # Tags might come from analysis later, start empty
                attachments_payload = []
                if email_content.attachments:
                    for att in email_content.attachments:
                        content_base64 = att.content if hasattr(att, 'content') and att.content is not None else None
                        attachments_payload.append({"filename": att.name, "mimetype": att.content_type, "size": att.size, "content_base64": content_base64})
                has_attachments_bool = len(attachments_payload) > 0

                # Combine all metadata that might go into the JSON field
                full_metadata = {
                    "sender": email_content.sender if email_content.sender else "unknown@sender.com",
                    "has_attachments": has_attachments_bool,
                    "tags": tags_list, # Store tags here
                    "analysis_status": "pending",
                    "raw_text": email_content.body or "",
                    "attachments": attachments_payload,
                    "attachment_count": len(attachments_payload),
                    "query_criteria": filter_criteria_obj.model_dump() # Store the criteria used
                    # Add any other relevant fields from email_content if needed
                }

                # Generate embedding
                email_body = full_metadata["raw_text"]
                if not email_body:
                    logger.warning(f"Email ID {email_id} has empty body, using subject for embedding.")
                    email_body = email_content.subject or ""
                embedding = await create_embedding(email_body)

                # Create data dictionary matching Milvus schema
                point_pk = str(uuid.uuid4()) 
                data_dict = {
                    "pk": point_pk,
                    "vector": embedding,
                    "owner": current_user.email,
                    "source": "email",
                    "type": "email_kb_entry", # Indicate this is for the knowledge base
                    "email_id": email_id, # Original email ID
                    "job_id": job_id,
                    "subject": email_content.subject or "",
                    "date": email_content.received_date or "",
                    "status": "reviewed", # Default status for saved emails
                    "folder": filter_criteria_obj.folder_id or "",
                    "metadata_json": full_metadata # Store remaining details
                }
                
                emails_to_insert.append(data_dict)
                processed_email_count += 1
                logger.debug(f"Prepared point PK {point_pk} (original email: {email_id}) for insertion into {target_kb_collection_name}.")

            except Exception as fetch_err:
                failed_email_count += 1
                logger.error(f"Failed to fetch or process email_id {email_id} for job {job_id}: {str(fetch_err)}", exc_info=True)
                # Continue processing other emails

    except Exception as outer_err:
         logger.error(f"Error during email fetching loop for job {job_id}: {str(outer_err)}", exc_info=True)
         # Ensure collection check failure is also caught if it happens before loop
         if "collection not found" in str(outer_err).lower() or "doesn't exist" in str(outer_err).lower():
             logger.warning(f"Target KB collection '{target_kb_collection_name}' not found before processing emails for job {job_id}.")
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base collection not found.")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error occurred while fetching email details.")

    # --- 3. Batch Insert Email Points to Milvus KB Collection --- 
    if emails_to_insert:
        try:
            logger.info(f"Inserting {len(emails_to_insert)} email points into Milvus collection '{target_kb_collection_name}' for job {job_id}...")
            # Use client.insert for batch insertion
            insert_result = client.insert(
                collection_name=target_kb_collection_name, 
                data=emails_to_insert
            )
            logger.info(f"Successfully inserted {len(emails_to_insert)} email points for job {job_id}. Result PKs: {insert_result.primary_keys}")
        except Exception as e:
            logger.error(f"Failed to batch insert email points for job {job_id} into Milvus collection '{target_kb_collection_name}': {str(e)}", exc_info=True)
            # Don't raise error here, just report partial success/failure
            return {
                "job_id": job_id,
                "message": f"Attempted to save job. Processed: {processed_email_count}, Failed Fetch/Process: {failed_email_count}, Failed Milvus Insert: {len(emails_to_insert)}",
                "status": "partial_failure"
            }
    else:
        logger.warning(f"No email points were prepared for insertion for job {job_id} (fetch/process errors: {failed_email_count})")

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
        filter_dict = filter_input.model_dump(mode='json') # Keep this for logging/job details

        logger.info(f"[Op:{operation_id}] Received filter: {filter_dict}") # Log the received filter

        # Extract required arguments for the task
        user_id_for_task = owner_email # Or maybe use current_user.id if that's intended
        user_email_for_task = owner_email
        folder_id_for_task = filter_input.folder_id
        # Ensure from_date is a datetime object or None
        from_date_for_task = None
        if filter_input.start_date:
            try:
                from_date_for_task = datetime.fromisoformat(filter_input.start_date)
            except ValueError:
                logger.error(f"[Op:{operation_id}] Invalid start_date format: {filter_input.start_date}. Cannot parse.")
                # Optionally raise an error or proceed without a start date
                # raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")
                pass # Or handle as needed
        
        # Ensure end_date is a datetime object or None
        end_date_for_task = None
        if filter_input.end_date:
            try:
                end_date_for_task = datetime.fromisoformat(filter_input.end_date)
            except ValueError:
                logger.error(f"[Op:{operation_id}] Invalid end_date format: {filter_input.end_date}. Cannot parse.")
                # Optionally raise error or proceed without end date
                pass

        logger.info(f"[Op:{operation_id}] Dispatching Celery task 'process_user_emails' for user {owner_email}.")
        # Call the task with individual arguments, explicitly checking from_date
        task = process_user_emails.delay(
            user_id=user_id_for_task,
            user_email=user_email_for_task,
            folder_id=folder_id_for_task,
            from_date=from_date_for_task, # Keep as is, task likely handles None
            end_date=end_date_for_task # ADD: Pass the end_date
        )
        logger.info(f"[Op:{operation_id}] Task dispatched with ID: {task.id}")

        # +++ Store task ID on user record +++
        try:
            # Re-fetch the DB user to update them using the injected session 'db'
            # Make sure UserDB model is imported at the top of the file
            db_user = db.query(UserDB).filter(UserDB.email == owner_email).first()
            if db_user:
                # Ensure task.id is stored as a string to avoid UUID type issues
                db_user.last_kb_task_id = str(task.id)
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
