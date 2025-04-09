import logging
import uuid
from typing import List, Dict, Any, Callable, Tuple

from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct

from app.services.outlook import OutlookService
from app.services.embedder import create_embedding
from app.models.email import EmailFilter
from app.config import settings

logger = logging.getLogger(__name__)

async def _process_and_store_emails(
    operation_id: str,
    owner_email: str,
    filter_criteria: EmailFilter,
    outlook_service: OutlookService,
    qdrant_client: QdrantClient, # Keep client for potential direct use if needed
    target_collection_name: str, # Pass the specific collection name
    update_state_func: Callable = None # Callback for Celery progress
) -> Tuple[int, int, List[PointStruct]]:
    """
    Fetches emails based on filter, processes content, creates embeddings,
    and prepares Qdrant points for storage.

    Args:
        operation_id: A unique ID for logging/tracking this operation.
        owner_email: The email of the user initiating the process.
        filter_criteria: The criteria to filter emails.
        outlook_service: An initialized OutlookService instance.
        qdrant_client: An initialized QdrantClient instance.
        target_collection_name: The specific Qdrant collection to target.
        update_state_func: An optional callback function (like task.update_state) 
                           to report progress.

    Returns:
        A tuple containing:
        - processed_email_count (int): Number of emails successfully processed.
        - failed_email_count (int): Number of emails that failed during fetch/process.
        - points_to_upsert (List[PointStruct]): List of Qdrant points ready for upsert.
    """
    points_to_upsert: List[PointStruct] = []
    processed_email_count = 0
    failed_email_count = 0
    all_email_ids = []
    PAGE_SIZE = 100 # Consider making this configurable?

    if update_state_func:
        update_state_func(state='PROGRESS', meta={'progress': 25, 'status': 'Fetching email IDs...'})

    try:
        logger.info(f"[Op:{operation_id}] Fetching all email IDs via pagination using criteria: {filter_criteria.model_dump_json()}")
        current_next_link = None
        page_num = 1
        
        while True:
            logger.info(f"[Op:{operation_id}] Fetching page {page_num} of email previews (size: {PAGE_SIZE})...")
            params = filter_criteria.model_dump(exclude_none=True)
            params['per_page'] = PAGE_SIZE
            if current_next_link:
                params['next_link'] = current_next_link
            
            # Assuming get_email_preview is async
            paged_result_dict = await outlook_service.get_email_preview(**params)
            
            items_on_page_raw = paged_result_dict.get("items", [])
            current_next_link = paged_result_dict.get("next_link")

            if items_on_page_raw:
                 ids_on_page = [item['id'] for item in items_on_page_raw if item.get('id')]
                 all_email_ids.extend(ids_on_page)
                 logger.info(f"[Op:{operation_id}] Fetched {len(ids_on_page)} IDs from page {page_num}. Total IDs so far: {len(all_email_ids)}.")
            else:
                logger.info(f"[Op:{operation_id}] No items found on page {page_num}.")

            if not current_next_link:
                logger.info(f"[Op:{operation_id}] No more pages found. Finished fetching IDs.")
                break 
            
            page_num += 1
            # Consider adding a safety break for too many pages?

        total_emails_found = len(all_email_ids)
        logger.info(f"[Op:{operation_id}] Found {total_emails_found} total email IDs matching criteria. Fetching content...")
        if update_state_func:
             update_state_func(state='PROGRESS', meta={'progress': 40, 'status': f'Found {total_emails_found} emails. Fetching content...'})

        for i, email_id in enumerate(all_email_ids):
            progress_percent = 40 + int(60 * (i / total_emails_found)) if total_emails_found > 0 else 99
            if update_state_func:
                update_state_func(state='PROGRESS', meta={'progress': progress_percent, 'status': f'Processing email {i+1}/{total_emails_found}'})            
            try:
                logger.debug(f"[Op:{operation_id}] Fetching content for email_id: {email_id}")
                email_content = await outlook_service.get_email_content(email_id)
                
                # --- Prepare Metadata --- 
                attachments_payload = []
                if email_content.attachments:
                    for att in email_content.attachments:
                        content_base64 = att.contentBytes if hasattr(att, 'contentBytes') and att.contentBytes is not None else None 
                        attachments_payload.append({
                            "filename": att.name, "mimetype": att.content_type, 
                            "size": att.size, "content_base64": content_base64
                        })
                has_attachments_bool = len(email_content.attachments) > 0 if email_content.attachments else False

                email_metadata = {
                    "type": "email_knowledge", # Standardized type
                    "owner": owner_email,
                    "sender": email_content.sender if email_content.sender else "unknown@sender.com", 
                    "subject": email_content.subject or "",
                    "date": email_content.received_date or "", 
                    "has_attachments": has_attachments_bool,
                    "folder": filter_criteria.folder_id, 
                    "tags": [], # Analysis/tags to be handled separately later if needed
                    "analysis_status": "vectorized", # Status indicates embedding is done
                    "status": "processed", 
                    "source": "email",
                    "raw_text": email_content.body or "",
                    "attachments": attachments_payload,
                    "attachment_count": len(attachments_payload),
                    "query_criteria": filter_criteria.model_dump(),
                    'original_email_id': email_id
                }

                # --- Create Embedding (Replacing Dummy Vector) --- 
                text_to_embed = email_metadata["raw_text"]
                if not text_to_embed:
                    logger.warning(f"[Op:{operation_id}] Email ID {email_id} has empty body, using subject for embedding.")
                    text_to_embed = email_metadata["subject"]
                if not text_to_embed:
                    logger.warning(f"[Op:{operation_id}] Email ID {email_id} has empty body and subject. Skipping embedding.")
                    # Decide how to handle - skip or use a zero vector?
                    # For now, skip this email
                    failed_email_count += 1
                    continue 
                
                # <<< Embedding call REMOVED based on user requirement >>>
                # embedding = await create_embedding(text_to_embed)
                # Use a placeholder zero vector instead
                placeholder_vector = [0.0] * settings.QDRANT_VECTOR_SIZE

                # --- Prepare Point --- 
                qdrant_point_uuid = str(uuid.uuid4()) 
                point = PointStruct(
                    id=qdrant_point_uuid, 
                    vector=placeholder_vector, # <<< Store the placeholder vector >>> 
                    payload=email_metadata
                )
                points_to_upsert.append(point)
                processed_email_count += 1
                logger.debug(f"[Op:{operation_id}] Prepared point {qdrant_point_uuid} (email: {email_id}).")

            except Exception as fetch_err:
                failed_email_count += 1
                logger.error(f"[Op:{operation_id}] Failed to fetch/process email_id {email_id}: {str(fetch_err)}", exc_info=True)

    except Exception as outer_err:
         # Log error during the fetching loop, but return the counts/points gathered so far
         logger.error(f"[Op:{operation_id}] Error during email fetching/processing loop: {str(outer_err)}", exc_info=True)
         # We don't raise here, allowing partial results to be returned

    logger.info(f"[Op:{operation_id}] Email processing loop finished. Processed: {processed_email_count}, Failed: {failed_email_count}")
    return processed_email_count, failed_email_count, points_to_upsert 