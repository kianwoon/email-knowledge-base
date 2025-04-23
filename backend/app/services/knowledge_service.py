import logging
import uuid
import json
import base64
from typing import List, Dict, Any, Callable, Tuple

import openai
# Remove Qdrant imports
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.models import PointStruct
# Import Milvus types if needed (MilvusClient for type hint)
from pymilvus import MilvusClient

from app.services.outlook import OutlookService
from app.models.email import EmailFilter
from app.config import settings

logger = logging.getLogger(__name__)

async def _process_and_store_emails(
    operation_id: str,
    owner_email: str,
    filter_criteria: EmailFilter,
    outlook_service: OutlookService,
    vector_db_client: MilvusClient, # Updated type hint
    target_collection_name: str,
    update_state_func: Callable = None
) -> Tuple[int, int, List[Dict[str, Any]]]: # Updated return type hint
    """
    Fetches emails, generates tags via OpenAI, and prepares dictionaries matching
    the Milvus schema with a PLACEHOLDER VECTOR for later storage.
    """
    points_to_insert: List[Dict[str, Any]] = [] # Changed from PointStruct list
    processed_email_count = 0
    failed_email_count = 0
    all_email_ids = []
    PAGE_SIZE = 100

    openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    if not settings.OPENAI_API_KEY:
        logger.warning(f"[Op:{operation_id}] OPENAI_API_KEY not set. Tag generation skipped.")

    # Create placeholder vector using DENSE_EMBEDDING_DIMENSION
    # Assuming placeholder vector should match the actual embedding dimension
    placeholder_vector = [0.0] * settings.DENSE_EMBEDDING_DIMENSION 

    if update_state_func:
        update_state_func(state='PROGRESS', meta={'progress': 25, 'status': 'Fetching email IDs...'})

    try:
        # --- Email ID Fetching Loop (unchanged) ---
        logger.info(f"[Op:{operation_id}] Fetching all email IDs via pagination using criteria: {filter_criteria.model_dump_json()}")
        current_next_link = None
        page_num = 1
        while True:
            logger.info(f"[Op:{operation_id}] Fetching page {page_num} of email previews (size: {PAGE_SIZE})...")
            params = filter_criteria.model_dump(exclude_none=True)
            params['per_page'] = PAGE_SIZE
            if current_next_link: params['next_link'] = current_next_link
            paged_result_dict = await outlook_service.get_email_preview(**params)
            items_on_page_raw = paged_result_dict.get("items", [])
            current_next_link = paged_result_dict.get("next_link")
            if items_on_page_raw:
                ids_on_page = [item['id'] for item in items_on_page_raw if item.get('id')]
                all_email_ids.extend(ids_on_page)
                logger.info(f"[Op:{operation_id}] Fetched {len(ids_on_page)} IDs page {page_num}. Total: {len(all_email_ids)}.")
            else: logger.info(f"[Op:{operation_id}] No items on page {page_num}.")
            if not current_next_link: logger.info(f"[Op:{operation_id}] Finished fetching IDs."); break
            page_num += 1

        total_emails_found = len(all_email_ids)
        logger.info(f"[Op:{operation_id}] Found {total_emails_found} email IDs. Processing content...")
        if update_state_func:
            update_state_func(state='PROGRESS', meta={'progress': 40, 'status': f'Found {total_emails_found} emails. Processing...'})

        # --- Email Content Processing Loop ---
        for i, email_id in enumerate(all_email_ids):
            progress_percent = 40 + int(60 * (i / total_emails_found)) if total_emails_found > 0 else 99
            if update_state_func:
                update_state_func(state='PROGRESS', meta={'progress': progress_percent, 'status': f'Processing email {i+1}/{total_emails_found}'})

            try:
                logger.debug(f"[Op:{operation_id}] Fetching content for email_id: {email_id}")
                email_content = await outlook_service.get_email_content(email_id)

                # --- Generate Tags (unchanged) ---
                generated_tags = []
                subject = email_content.subject or ""
                if subject and openai_client.api_key:
                    try:
                        prompt = f"Analyze the following email subject and generate 3-5 concise, descriptive tags suitable for categorization and filtering. Focus on the main topic, project names, document types, or key entities mentioned. Output as a JSON object with a single key 'tags' containing a list of lowercased strings. Subject: '{subject}'"
                        response = await openai_client.chat.completions.create(
                            model=settings.OPENAI_MODEL_NAME,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.2, max_tokens=50, response_format={"type": "json_object"}
                        )
                        if response.choices and response.choices[0].message and response.choices[0].message.content:
                            try:
                                content_json = json.loads(response.choices[0].message.content)
                                tags_list = content_json.get("tags", [])
                                if isinstance(tags_list, list) and all(isinstance(tag, str) for tag in tags_list):
                                    generated_tags = [tag.lower() for tag in tags_list] # Ensure lowercase
                                else: logger.warning(f"[Op:{operation_id}] OpenAI response for subject '{subject}' had unexpected 'tags' format: {tags_list}")
                            except json.JSONDecodeError as json_err: logger.error(f"[Op:{operation_id}] Failed to parse OpenAI JSON for subject '{subject}': {json_err}. Content: {response.choices[0].message.content}")
                            except Exception as parse_err: logger.error(f"[Op:{operation_id}] Error processing OpenAI content for subject '{subject}': {parse_err}. Content: {response.choices[0].message.content}")
                        else: logger.warning(f"[Op:{operation_id}] OpenAI response empty for subject: {subject}")
                    except openai.APIError as api_err: logger.error(f"[Op:{operation_id}] OpenAI API error for subject '{subject}': {api_err}")
                    except Exception as e: logger.error(f"[Op:{operation_id}] Unexpected OpenAI error for subject '{subject}': {e}")
                elif not subject: logger.debug(f"[Op:{operation_id}] Skip OpenAI for email {email_id}: empty subject.")
                elif not openai_client.api_key: logger.debug(f"[Op:{operation_id}] Skip OpenAI for email {email_id}: API key not set.")

                # --- Prepare Metadata & Full Text ---
                attachments_payload = []
                # Graph API uses contentBytes for attachments
                if email_content.attachments:
                    for att in email_content.attachments:
                         # Check for contentBytes attribute
                        content_base64 = att.contentBytes if hasattr(att, 'contentBytes') and att.contentBytes is not None else None
                        attachments_payload.append({
                            "filename": att.name,
                            "mimetype": att.contentType if hasattr(att, 'contentType') else 'unknown', # Use contentType
                            "size": att.size,
                            # "content_base64": content_base64 # REMOVED to avoid exceeding Milvus JSON field limit
                        })
                has_attachments_bool = bool(attachments_payload)

                raw_text_content = email_content.body or ""
                if not raw_text_content and subject:
                    logger.warning(f"[Op:{operation_id}] Email {email_id} has empty body, using subject for raw_text.")
                    raw_text_content = subject
                
                if not raw_text_content and not subject:
                     logger.warning(f"[Op:{operation_id}] Email {email_id} has empty body and subject. Skipping.")
                     failed_email_count += 1
                     continue

                # Consolidate all metadata into a single dictionary for the JSON field
                metadata_for_json = {
                    "sender": email_content.sender or "unknown@sender.com",
                    "has_attachments": has_attachments_bool,
                    "tags": generated_tags,
                    "raw_text": raw_text_content, # Use potentially truncated text
                    "attachments": attachments_payload, 
                    "attachment_count": len(attachments_payload),
                    "query_criteria": filter_criteria.model_dump(exclude={'next_link'}),
                    'original_email_id': email_id,
                    "analysis_status": "pending"
                    # Add any other relevant fields from email_content if needed
                }

                # --- Prepare Milvus data dictionary --- 
                point_pk = str(uuid.uuid4()) # Use UUID for PK

                data_dict = {
                    "pk": point_pk,
                    "vector": placeholder_vector, # Use the placeholder vector
                    # Required schema fields
                    "owner": owner_email,
                    "source": "email", 
                    "type": "email_knowledge", # Type indicating raw email data
                    "email_id": email_id,
                    "job_id": operation_id, # Use operation_id as job_id
                    "subject": subject,
                    "date": email_content.received_date or "",
                    "status": "processed", # Simplified status
                    "folder": filter_criteria.folder_id or "",
                    # Store the rest in the JSON field
                    "metadata_json": metadata_for_json
                }
                
                points_to_insert.append(data_dict)
                processed_email_count += 1
                logger.debug(f"[Op:{operation_id}] Prepared Milvus data dict PK {point_pk} with placeholder vector. Tags: {generated_tags}")

            except Exception as fetch_err: # Catch errors during individual email processing
                failed_email_count += 1
                logger.error(f"[Op:{operation_id}] Failed during processing loop for email_id {email_id}: {str(fetch_err)}", exc_info=True)
        # --- End Email Content Processing Loop ---

    except Exception as outer_loop_err:
        logger.error(f"[Op:{operation_id}] Error during main processing setup/loop: {str(outer_loop_err)}", exc_info=True)

    logger.info(f"[Op:{operation_id}] Email processing loop finished. Processed: {processed_email_count}, Failed: {failed_email_count}. Total points generated: {len(points_to_insert)}")
    # Return the list of dictionaries
    return processed_email_count, failed_email_count, points_to_insert