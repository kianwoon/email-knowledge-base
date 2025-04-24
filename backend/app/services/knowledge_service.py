import logging
import uuid
import json
import base64
import pathlib
from typing import List, Dict, Any, Callable, Tuple, Optional
import asyncio
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

import openai
# Remove Qdrant imports
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.models import PointStruct
# Import Milvus types if needed (MilvusClient for type hint)
from pymilvus import MilvusClient

from app.services.outlook import OutlookService
from app.services import s3 as s3_service
from app.models.email import EmailFilter
from app.config import settings
from app.crud import crud_processed_file
from app.db.models.processed_file import ProcessedFile

logger = logging.getLogger(__name__)

# NEW: Define a namespace for generating UUIDs based on Email Attachments
EMAIL_ATTACHMENT_NAMESPACE_UUID = uuid.UUID('c7e4a9b3-9e6f-5d2c-af8e-5f5e2b1e6d0c') # Example random namespace

# NEW: Helper function to generate deterministic Milvus PK for Email Attachments
def generate_email_attachment_milvus_pk(email_id: str, attachment_id: str) -> str:
    """Generates a deterministic Milvus UUID PK from the email ID and attachment ID."""
    unique_id_string = f"email://{email_id}/attachment/{attachment_id}"
    return str(uuid.uuid5(EMAIL_ATTACHMENT_NAMESPACE_UUID, unique_id_string))

# NEW: R2 key generator for attachments
def generate_email_attachment_r2_key(email_id: str, attachment_id: str, attachment_name: str) -> str:
    """Generates a unique R2 object key for an email attachment."""
    unique_id_string = f"email://{email_id}/attachment/{attachment_id}"
    deterministic_id = str(uuid.uuid5(EMAIL_ATTACHMENT_NAMESPACE_UUID, unique_id_string))
    original_extension = "".join(pathlib.Path(attachment_name).suffixes)
    # Structure: provider/deterministic_id/filename.ext
    return f"email_attachment/{deterministic_id}{original_extension}"

async def _process_and_store_emails(
    operation_id: str,
    owner_email: str,
    filter_criteria: EmailFilter,
    outlook_service: OutlookService,
    vector_db_client: MilvusClient, # Updated type hint
    target_collection_name: str,
    update_state_func: Callable = None,
    db_session: Session = None, # Added db_session parameter
    ingestion_job_id: int = None # Added ingestion_job_id parameter
) -> Tuple[int, int, int, int, List[Dict[str, Any]]]: # Return email_proc, email_fail, att_proc, att_fail, email_data_for_milvus
    """
    Fetches emails, generates tags via OpenAI, and prepares dictionaries matching
    the Milvus schema with a PLACEHOLDER VECTOR for later storage.
    Also processes attachments: downloads, uploads to R2, creates separate Milvus records.
    """
    email_data_for_milvus: List[Dict[str, Any]] = [] # Changed from PointStruct list
    processed_email_count = 0
    failed_email_count = 0
    processed_attachment_count = 0 # Added counter
    failed_attachment_count = 0    # Added counter
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
                    "has_attachments": has_attachments_bool, # Indicates if attachments *were* present
                    "tags": generated_tags,
                    "raw_text": raw_text_content, # Email body text
                    "attachments": attachments_payload, # List of attachment METADATA
                    "attachment_count": len(attachments_payload),
                    "query_criteria": filter_criteria.model_dump(exclude={'next_link'}),
                    'original_email_id': email_id,
                    "analysis_status": "pending" # Status for the EMAIL body analysis
                    # Add any other relevant fields from email_content if needed
                }

                # --- Prepare Milvus data dictionary FOR EMAIL --- 
                point_pk = str(uuid.uuid4()) # Use UUID for EMAIL PK (non-deterministic for main email)

                data_dict = {
                    "pk": point_pk,
                    "vector": placeholder_vector, # Use the placeholder vector
                    # Required schema fields
                    "owner": owner_email,
                    "source": "email", 
                    "type": "email_knowledge", # Type indicating raw email data
                    "email_id": email_id,
                    "job_id": str(ingestion_job_id) if ingestion_job_id else operation_id, # Use Job ID if available
                    "subject": subject,
                    "date": email_content.received_date or "",
                    "status": "processed", # Email body processed, attachments handled separately
                    "folder": filter_criteria.folder_id or "",
                    # Add fields if schema requires them at top level, otherwise rely on JSON
                    "analysis_status": "pending", # Status for EMAIL analysis
                    "r2_object_key": "", # Use empty string instead of None for VARCHAR field
                    # Store the rest in the JSON field
                    "metadata_json": metadata_for_json
                }
                
                email_data_for_milvus.append(data_dict)
                processed_email_count += 1
                logger.debug(f"[Op:{operation_id}] Prepared Milvus data dict for EMAIL PK {point_pk}. Tags: {generated_tags}")

                # --- Process Attachments -> R2 + PostgreSQL --- 
                if email_content.attachments:
                    logger.info(f"[Op:{operation_id}] Processing {len(email_content.attachments)} attachments for email {email_id}.")
                    for attachment in email_content.attachments:
                        attachment_id = attachment.id
                        attachment_name = attachment.name
                        if not attachment_id or not attachment_name:
                             logger.warning(f"[Op:{operation_id}] Skipping attachment with missing ID or name for email {email_id}.")
                             failed_attachment_count += 1
                             continue

                        # --- Skip images --- 
                        attachment_content_type = attachment.contentType.lower() if hasattr(attachment, 'contentType') and attachment.contentType else 'unknown'
                        filename_lower = attachment_name.lower()
                        # Check content type OR file extension
                        if attachment_content_type.startswith('image/') or \
                           filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')):
                            logger.info(f"[Op:{operation_id}] Skipping image attachment: {attachment_id} ('{attachment_name}'), Type: {attachment_content_type}.")
                            continue
                        # --- End Skip --- 

                        r2_object_key: Optional[str] = None
                        attachment_save_succeeded = False
                        try:
                            # 1. Download attachment content
                            logger.debug(f"[Op:{operation_id}] Downloading content for attachment {attachment_id} ('{attachment_name}')")
                            attachment_content_bytes = await outlook_service.get_attachment_content(email_id, attachment_id)
                            if not attachment_content_bytes:
                                logger.warning(f"[Op:{operation_id}] No content downloaded for attachment {attachment_id}. Skipping.")
                                continue
                            logger.debug(f"[Op:{operation_id}] Downloaded {len(attachment_content_bytes)} bytes for attachment {attachment_id}.")

                            # 2. Upload content to R2
                            logger.debug(f"[Op:{operation_id}] Attempting upload to R2 for attachment {attachment_id}.")
                            # --- Use new R2 key generator --- 
                            generated_r2_key = generate_email_attachment_r2_key(email_id, attachment_id, attachment_name)
                            target_r2_bucket = settings.R2_BUCKET_NAME
                            logger.info(f"[Op:{operation_id}] Uploading attachment copy as '{generated_r2_key}' to R2 Bucket '{target_r2_bucket}'")
                            upload_successful = await run_in_threadpool(
                                s3_service.upload_bytes_to_r2,
                                bucket_name=target_r2_bucket,
                                object_key=generated_r2_key,
                                data_bytes=attachment_content_bytes
                            )
                            if not upload_successful:
                                raise Exception(f"R2 upload failed for attachment {attachment_id}")
                            r2_object_key = generated_r2_key # Store the key on success
                            logger.info(f"[Op:{operation_id}] Upload attachment to R2 successful. Object Key: {r2_object_key}")
                            # --- End R2 Upload --- 

                            # --- ADD ProcessedFile Saving --- 
                            logger.debug(f"[Op:{operation_id}] Preparing ProcessedFile data for attachment {attachment_id}")
                            source_identifier = f"email://{email_id}/attachment/{attachment_id}"
                            additional_metadata = {
                                "email_id": email_id,
                                "email_subject": email_content.subject or "",
                                "email_sender": email_content.sender or "",
                                "attachment_id": attachment_id,
                                "attachment_filename": attachment_name,
                                "attachment_contentType": attachment_content_type,
                                "attachment_size": attachment.size
                            }
                            processed_file_dict = {
                                "ingestion_job_id": ingestion_job_id,
                                "source_type": 'email_attachment',
                                "source_identifier": source_identifier,
                                "additional_data": additional_metadata,
                                "r2_object_key": r2_object_key,
                                "owner_email": owner_email,
                                "status": 'pending_analysis',
                                "original_filename": attachment_name,
                                "content_type": attachment_content_type,
                                "size_bytes": attachment.size
                            }
                            processed_file_dict_cleaned = {k: v for k, v in processed_file_dict.items() if v is not None}
                            
                            processed_file_model = ProcessedFile(**processed_file_dict_cleaned)
                            created_record = crud_processed_file.create_processed_file_entry(db=db_session, file_data=processed_file_model)
                            if not created_record:
                                raise Exception(f"CRUD function failed to save ProcessedFile record for attachment {attachment_id}")
                            logger.info(f"[Op:{operation_id}] Saved ProcessedFile {created_record.id} for attachment {attachment_id}")
                            attachment_save_succeeded = True # Mark success only after DB save
                            processed_attachment_count += 1 # Increment count here
                            # --- End ADD --- 

                        except Exception as att_err:
                            logger.error(f"[Op:{operation_id}] Failed processing attachment {attachment_id} ('{attachment_name}'): {att_err}", exc_info=True)
                            failed_attachment_count += 1
                            # No need to increment failed_attachment_count again in outer handler if this fails
                            # Continue processing other attachments for this email

            except Exception as fetch_err: # Catch errors during individual email processing
                failed_email_count += 1
                logger.error(f"[Op:{operation_id}] Failed during processing loop for email_id {email_id}: {str(fetch_err)}", exc_info=True)
        # --- End Email Content Processing Loop ---

    except Exception as outer_loop_err:
        logger.error(f"[Op:{operation_id}] Error during main processing setup/loop: {str(outer_loop_err)}", exc_info=True)

    logger.info(f"[Op:{operation_id}] Email processing loop finished. Emails: {processed_email_count} processed, {failed_email_count} failed. Attachments: {processed_attachment_count} processed, {failed_attachment_count} failed. Total points generated: {len(email_data_for_milvus)}")
    # Return the list of dictionaries
    return processed_email_count, failed_email_count, processed_attachment_count, failed_attachment_count, email_data_for_milvus