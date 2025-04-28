import logging
import uuid
import json
import base64
import pathlib
import uuid # Ensure uuid is imported
from typing import List, Dict, Any, Callable, Tuple, Optional
from datetime import datetime, timezone
import asyncio
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
import os

import openai
# Remove Qdrant imports
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.models import PointStruct
# Import Milvus types if needed (MilvusClient for type hint)
# from pymilvus import MilvusClient # Commented out from diff

from app.services.outlook import OutlookService
from app.services import s3 as s3_service
from app.services import r2_service
from app.models.email import EmailFilter
from app.config import settings
from app.crud import crud_processed_file
from app.db.models.processed_file import ProcessedFile

logger = logging.getLogger(__name__)

# --- Define a static UUID namespace for generating deterministic R2 keys --- 
# This specific UUID was generated once and should remain constant.
EMAIL_ATTACHMENT_NAMESPACE_UUID = uuid.UUID('f5a1e3a7-5c4e-4b1e-8a8f-3c9e1b7e4a5d')

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
    # REMOVED vector_db_client and target_collection_name parameters from diff
    # vector_db_client: MilvusClient,
    # target_collection_name: str,
    update_state_func: Callable = None,
    db_session: Session = None, # Added db_session parameter
    ingestion_job_id: int = None, # Added ingestion_job_id parameter
    r2_client: Any = None # Added r2_client parameter
) -> Tuple[int, int, int, int, List[Dict[str, Any]]]: # CHANGED: Return type changed for Iceberg list
    """
    Fetches emails, generates tags via OpenAI, extracts structured facts,
    and prepares a list of dictionaries matching the Iceberg 'email_facts' table schema.
    (TODO: Also needs to process attachments: downloads, uploads to R2, creates processed_files records)
    """
    # CHANGED: Initialize list for Iceberg records from diff
    facts_for_iceberg: List[Dict[str, Any]] = [] 
    processed_email_count = 0
    failed_email_count = 0
    # Keep attachment counters for combined logic later
    processed_attachment_count = 0 # Added counter
    failed_attachment_count = 0    # Added counter
    all_email_ids = []
    PAGE_SIZE = 100

    openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    if not settings.OPENAI_API_KEY:
        logger.warning(f"[Op:{operation_id}] OPENAI_API_KEY not set. Tag generation skipped.")

    # REMOVED placeholder vector from diff
    # placeholder_vector = [0.0] * settings.DENSE_EMBEDDING_DIMENSION 

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
                # ASSUMPTION from diff: email_content object has necessary fields 
                # like sender, subject, body, receivedDateTime, sentDateTime, 
                # toRecipients, ccRecipients, bccRecipients, attachments etc.
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

                # --- Prepare Attachment Details (for Iceberg) ---
                attachments_payload = []
                # Graph API uses contentBytes for attachments
                if email_content.attachments:
                    # logger.debug(f"[Op:{operation_id}] Starting attachment processing loop for email {email_id}. Found {len(email_content.attachments)} potential attachments.") # Commented out debug log
                    for att_index, att in enumerate(email_content.attachments):
                        # Initialize flags for success tracking within the loop
                        upload_success = False
                        db_record_success = False
                        filename = getattr(att, 'name', 'unknown_filename')
                        att_id = getattr(att, 'id', str(uuid.uuid4())) # Use uuid.uuid4() for fallback ID
                        # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}/{len(email_content.attachments)}] Processing: ID={att_id}, Name='{filename}'") # Commented out debug log

                        try:
                            # content_bytes_b64 = getattr(att, 'contentBytes', None) # Check for contentBytes specifically -> Content fetched later
                            
                            # --- NEW: Check for existing ProcessedFile record FIRST ---
                            source_uri = f"email://{email_id}/attachment/{att_id}"
                            existing_record = None
                            if db_session and att_id:
                                try:
                                    # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}] Checking DB for existing record with source_uri: {source_uri}") # Commented out debug log
                                    existing_record = crud_processed_file.get_processed_file_by_source_id(db=db_session, source_identifier=source_uri)
                                    if existing_record:
                                         # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}] Found existing record: DB ID {existing_record.id}, R2 Key {existing_record.r2_object_key}") # Commented out debug log
                                         pass # Keep pass here to maintain structure
                                    else:
                                         # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}] No existing record found in DB.") # Commented out debug log
                                         pass # Keep pass here
                                except Exception as db_check_err:
                                    logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Error checking DB for existing ProcessedFile for {source_uri}: {db_check_err}", exc_info=True)
                                    # Decide if we should proceed or fail this attachment - let's proceed cautiously but log the error
                            else:
                                logger.warning(f"[Op:{operation_id}] [Attach {att_index+1}] Skipping DB check for {att_id} due to missing DB session or attachment ID.")

                            
                            if existing_record:
                                logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Attachment {att_id} ('{filename}') already processed (DB ID: {existing_record.id}, R2 Key: {existing_record.r2_object_key}). Skipping re-processing.")
                                # IMPORTANT: Count previously processed as success for metrics
                                processed_attachment_count += 1 
                                continue # Skip to the next attachment

                            # --- END Check ---

                            # --- Skip Inline/Images/Specific Extensions (No R2 Upload/DB Record) ---
                            is_inline = getattr(att, 'isInline', False)
                            filename_lower = filename.lower()
                            # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}] Details: isInline={is_inline}, filename='{filename}'") # Commented out debug log
                            
                            # --- Define allowed extensions --- 
                            allowed_extensions = ['.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.pdf']
                            # MODIFIED: Use os.path.splitext for robust extension extraction
                            attachment_extension = os.path.splitext(filename)[1].lower()
                            # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}] Detected extension: '{attachment_extension}'") # Commented out debug log
                            
                            # --- NEW: Skip if inline OR not an allowed extension --- 
                            if is_inline:
                                logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Skipping attachment: {att_id} ('{filename}'). Reason: Inline ({is_inline}).")
                                continue # Skip to next attachment
                            if not attachment_extension in allowed_extensions:
                                logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Skipping attachment: {att_id} ('{filename}'). Reason: Disallowed Extension ('{attachment_extension}'). Allowed: {allowed_extensions}")
                                continue # Skip to next attachment
                            # --- End Skip Logic ---
                            
                            # --- Fetch contentBytes separately --- 
                            attachment_content_bytes = None
                            if r2_client and db_session:
                                # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}] Attachment not skipped. Checking R2/DB client availability: R2 OK={bool(r2_client)}, DB OK={bool(db_session)}") # Commented out debug log
                                try:
                                    # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}] Fetching contentBytes for attachment {att_id} ('{filename}')...") # Commented out debug log
                                    # Use the existing service method designed for this
                                    attachment_content_bytes = await outlook_service.get_attachment_content(
                                        message_id=email_id, 
                                        attachment_id=att_id
                                    )
                                    if attachment_content_bytes:
                                        logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Successfully fetched {len(attachment_content_bytes)} bytes for attachment {att_id}.")
                                    else:
                                        logger.warning(f"[Op:{operation_id}] [Attach {att_index+1}] Fetched attachment {att_id} but contentBytes was missing or empty.")
                                        # This attachment cannot be processed further
                                except Exception as content_fetch_err:
                                    logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Failed to fetch contentBytes for attachment {att_id}: {content_fetch_err}", exc_info=True)
                                    # Count as failed if content fetch fails
                                    failed_attachment_count += 1
                                    continue # Skip to next attachment
                            else:
                                logger.warning(f"[Op:{operation_id}] [Attach {att_index+1}] Skipping contentBytes fetch for {att_id} due to missing R2 client or DB session.")
                                failed_attachment_count += 1
                                continue # Skip to next attachment

                            # Proceed only if we have contentBytes AND an R2 client/DB session
                            if attachment_content_bytes:
                                content_type = getattr(att, 'contentType', 'application/octet-stream') # Get content type from original metadata
                                r2_key = generate_email_attachment_r2_key(email_id, att_id, filename)
                                logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Preparing to upload attachment '{filename}' as '{r2_key}' to R2 (Size: {len(attachment_content_bytes)} bytes).")

                                # +++ ADDED LOG BEFORE UPLOAD +++
                                # logger.debug(f"[Op:{operation_id}] [Attach {att_index+1}] Calling r2_service.upload_bytes_to_r2 for key: {r2_key}") # Commented out debug log
                                
                                # MODIFIED: Corrected parameter names and added bucket_name
                                upload_successful = await r2_service.upload_bytes_to_r2(
                                    r2_client=r2_client,
                                    bucket_name=settings.R2_BUCKET_NAME, # Added bucket name from settings
                                    object_key=r2_key, # Corrected parameter name
                                    data_bytes=attachment_content_bytes, # Corrected parameter name
                                    content_type=content_type
                                )
                                
                                # Check the boolean return value from the upload function
                                if upload_successful:
                                    # +++ ADDED LOG AFTER UPLOAD SUCCESS +++
                                    logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Successfully uploaded to R2 as '{r2_key}'.")
                                    upload_success = True # Mark upload as successful
                                else:
                                    logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Call to r2_service.upload_bytes_to_r2 failed for key '{r2_key}'. Check previous logs for ClientError.")
                                    # Do not proceed to create DB record if upload failed
                                    failed_attachment_count += 1 # Increment failure count
                                    continue # Skip to the next attachment
                                
                                # Create processed_file record only AFTER successful upload
                                try:
                                    file_metadata = {
                                        "r2_object_key": r2_key,
                                        "original_filename": filename,
                                        "source_type": "email_attachment",
                                        "source_identifier": source_uri, # MODIFIED: Corrected key name
                                        "content_type": content_type,
                                        "size_bytes": getattr(att, 'size', 0),
                                        "status": "pending_analysis" # Initial status
                                    }
                                    # MODIFIED: Use the correct function name create_processed_file_entry
                                    created_record = crud_processed_file.create_processed_file_entry(
                                        db=db_session,
                                        # Assuming create_processed_file_entry takes the dictionary directly
                                        # or expects a ProcessedFile object constructed from it.
                                        # If it expects an object, we need to create it first.
                                        # Let's assume it takes the dict for now, based on typical CRUD patterns.
                                        file_data=ProcessedFile(**file_metadata, 
                                                              ingestion_job_id=ingestion_job_id, 
                                                              owner_email=owner_email)
                                        # file_info=file_metadata,
                                        # ingestion_job_id=ingestion_job_id,
                                        # owner_email=owner_email # Pass owner email
                                    )
                                    if created_record:
                                        logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Saved ProcessedFile {created_record.id} for attachment {att_id} ('{filename}').")
                                        db_record_success = True # Mark DB record as successful
                                    else:
                                         logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] CRUD function failed to return ProcessedFile record for attachment {att_id} ('{filename}').")
                                
                                except Exception as db_err:
                                    logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Failed to save ProcessedFile record for attachment {att_id} ('{filename}') after R2 upload: {db_err}", exc_info=True)
                                
                                if upload_success and db_record_success:
                                    processed_attachment_count += 1
                                else:
                                    failed_attachment_count += 1

                        except Exception as att_error:
                            # General catch-all for errors during the attachment loop iteration
                            failed_attachment_count += 1
                            logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Unhandled error processing attachment {att_id} ('{filename}'): {att_error}", exc_info=True)
                            # Attempt to save a failure record? (Optional, similar to above)

                has_attachments_bool = bool(attachments_payload)

                raw_text_content = email_content.body or ""
                if not raw_text_content and subject:
                    logger.warning(f"[Op:{operation_id}] Email {email_id} has empty body, using subject for raw_text.")
                    raw_text_content = subject
                
                if not raw_text_content and not subject:
                     logger.warning(f"[Op:{operation_id}] Email {email_id} has empty body and subject. Skipping.")
                     failed_email_count += 1
                     continue

                # --- Extract and Format Data for Iceberg --- 
                # Use helper function to safely get email address from recipient object
                def get_email_address(recipient_obj) -> str | None:
                    if recipient_obj and hasattr(recipient_obj, 'emailAddress') and recipient_obj.emailAddress:
                        return getattr(recipient_obj.emailAddress, 'address', None)
                    return None

                # --- Extract recipients and sender CORRECTLY ---
                # Sender: Directly use the pre-extracted sender_email
                sender_address = email_content.sender_email or "unknown@sender.com"
                
                # Recipients/CC: Directly use the pre-extracted lists of strings
                # Ensure they are lists, default to empty list if attribute doesn't exist or is None
                to_recipients = getattr(email_content, 'recipients', None) or []
                cc_recipients = getattr(email_content, 'cc_recipients', None) or []
                # BCC is not currently fetched by outlook.py, so it will remain empty
                bcc_recipients = [] 

                # Handle Timestamps - Ensure they are timezone-aware (UTC preferably)
                def ensure_utc(dt_obj: datetime | None) -> datetime | None:
                    if dt_obj is None: return None
                    # Ensure input is actually a datetime object
                    if not isinstance(dt_obj, datetime):
                         logger.error(f"[Op:{operation_id}] ensure_utc received non-datetime object: {type(dt_obj)}. Cannot process.")
                         return None # Or raise an error? Returning None for now.

                    if dt_obj.tzinfo is None:
                        logger.warning(f"[Op:{operation_id}] Email {email_id}: Making naive datetime {dt_obj} UTC-aware.")
                        return dt_obj.replace(tzinfo=timezone.utc)
                    return dt_obj.astimezone(timezone.utc)

                # --- START: Parse string dates before calling ensure_utc ---
                parsed_received_dt = None
                received_dt_str = getattr(email_content, 'received_date', None)
                if received_dt_str and isinstance(received_dt_str, str):
                    try:
                        # Parse the ISO 8601 string (potentially replacing 'Z')
                        parsed_received_dt = datetime.fromisoformat(received_dt_str.replace('Z', '+00:00'))
                    except ValueError:
                        logger.error(f"[Op:{operation_id}] Failed to parse received_date string: '{received_dt_str}'")
                    except Exception as parse_err:
                        logger.error(f"[Op:{operation_id}] Unexpected error parsing received_date string '{received_dt_str}': {parse_err}", exc_info=True)
                
                # sent_date should already be a datetime object from outlook.py, but we can add a check
                sent_dt_obj = getattr(email_content, 'sent_date', None)
                if sent_dt_obj and not isinstance(sent_dt_obj, datetime):
                     logger.warning(f"[Op:{operation_id}] sent_date was not a datetime object: {type(sent_dt_obj)}. Will attempt ensure_utc.")
                     # Handle unexpected type if necessary, maybe try parsing if it's a string?
                     # For now, we'll let ensure_utc handle it (which might return None).

                received_dt_utc = ensure_utc(parsed_received_dt) # Pass the parsed datetime object
                sent_dt_utc = ensure_utc(sent_dt_obj) # Pass the datetime object directly
                # --- END: Parse string dates ---

                ingested_dt_utc = datetime.now(timezone.utc)

                # Prepare the record dictionary matching the assumed Iceberg schema
                email_fact_record = {
                    "message_id": email_id,
                    "job_id": str(ingestion_job_id) if ingestion_job_id else operation_id, # Use Job ID if available
                    "owner_email": owner_email,
                    "sender": sender_address, # Use CORRECTED sender address (email)
                    "sender_name": email_content.sender, # ADDED: Use sender display name from EmailContent
                    # Convert lists to JSON strings for Iceberg compatibility with string columns
                    "recipients": json.dumps(to_recipients), # Use CORRECTED recipient list
                    "cc_recipients": json.dumps(cc_recipients), # Use CORRECTED cc_recipient list
                    "bcc_recipients": json.dumps(bcc_recipients), # Use empty BCC list
                    "subject": email_content.subject or "",
                    "body_text": email_content.body or "", # Use plain text body
                    "received_datetime_utc": received_dt_utc,
                    "sent_datetime_utc": sent_dt_utc,
                    "folder": filter_criteria.folder_id or "",
                     "has_attachments": has_attachments_bool,
                    "attachment_count": len(attachments_payload),
                    "attachment_details": json.dumps(attachments_payload),
                    "generated_tags": json.dumps(generated_tags),
                    "ingested_at_utc": ingested_dt_utc
                }
                
                # MODIFIED: Append Iceberg record
                facts_for_iceberg.append(email_fact_record)
                processed_email_count += 1
                logger.debug(f"[Op:{operation_id}] Prepared Iceberg record for email_id: {email_id}. Sender: {sender_address}")

            except Exception as fetch_err: # Catch errors during individual email processing
                failed_email_count += 1
                logger.error(f"[Op:{operation_id}] Failed during processing loop for email_id {email_id}: {str(fetch_err)}", exc_info=True)
        # --- End Email Content Processing Loop ---

    except Exception as outer_loop_err:
        logger.error(f"[Op:{operation_id}] Error during main processing setup/loop: {str(outer_loop_err)}", exc_info=True)

    logger.info(f"[Op:{operation_id}] Email processing loop finished. Processed: {processed_email_count}, Failed: {failed_email_count}. Attachments Processed: {processed_attachment_count}, Attachments Failed: {failed_attachment_count}. Records for Iceberg: {len(facts_for_iceberg)}")
    # MODIFIED: Return the list of fact dictionaries for Iceberg, plus attachment counts
    return processed_email_count, failed_email_count, processed_attachment_count, failed_attachment_count, facts_for_iceberg