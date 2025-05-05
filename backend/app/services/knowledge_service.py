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
import re # Import regex module

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
from app.models.user import UserDB as User
from app.config import settings
from app.crud import crud_processed_file, user_crud
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

# Helper function to extract domain from email
def _extract_domain(email_address: str) -> Optional[str]:
    if not email_address or '@' not in email_address:
        return None
    try:
        # Basic split, lowercased for comparison
        return email_address.split('@')[1].lower()
    except IndexError:
        # Handle cases like 'user@' which are invalid but might occur
        return None

# Helper function to find sender email within quoted text
# This is a best-effort extraction using regex
def _extract_sender_from_quote(quoted_text: str) -> Optional[str]:
    if not quoted_text:
        return None
    
    # Look for "From:" line, capturing content after it. Limited lines for performance/accuracy.
    lines_to_check = quoted_text.splitlines()[:10] # Check first 10 lines reasonably likely to contain headers
    from_line_content = None
    # Regex specifically looking for "From:" at the start of a line (ignoring leading whitespace)
    from_pattern = re.compile(r"^\s*From:\s*(.*)", re.IGNORECASE) 
    
    for line in lines_to_check:
        match = from_pattern.match(line)
        if match:
            from_line_content = match.group(1)
            logger.debug(f"Found 'From:' line content in quote: {from_line_content}")
            break # Found the first From line, assume it's the relevant one

    if not from_line_content:
        logger.debug("No 'From:' line found in the first 10 lines of the quote.")
        return None

    # Look for an email address within the "From:" line content using a robust regex
    # Handles common formats like <email@domain.com> or just email@domain.com
    email_pattern = re.compile(r'[\w\.\-+%]+@[\w\.-]+\.[a-zA-Z]{2,}') 
    email_match = email_pattern.search(from_line_content)
    
    if email_match:
        extracted_email = email_match.group(0)
        logger.debug(f"Extracted email from 'From:' line: {extracted_email}")
        return extracted_email
    else:
        logger.debug(f"Could not extract email address from 'From:' line content: {from_line_content}")
        
    return None # Email address not found in the From line

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
    Fetches emails, generates tags via OpenAI, extracts structured facts (flattened),
    uploads attachments to R2, and prepares a list of dictionaries matching the 
    flattened Iceberg 'email_facts' table schema.
    
    MODIFIED: Now only saves quote rows if the quote sender is an "outsider" 
    based on user's outlook_sync_config.
    """
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

    # --- Get User and Sync Config for Outsider Detection ---
    db_user: Optional[User] = None
    primary_domain: Optional[str] = None
    alliance_domains_set: set[str] = set()
    sync_config_source = "None" # Track source for logging

    if db_session:
        db_user = user_crud.get_user_full_instance(db=db_session, email=owner_email)
        if not db_user:
             logger.error(f"[Op:{operation_id}] User {owner_email} not found in DB. Cannot proceed or check sync config.")
             # Fallback logic will run below if primary_domain remains None
        else:
            try:
                sync_config = db_user.outlook_sync_config
                parsed_config: Optional[Dict] = None

                if isinstance(sync_config, dict):
                    parsed_config = sync_config
                    sync_config_source = "DB (dict/JSONB)"
                elif isinstance(sync_config, str):
                    try:
                        parsed_config = json.loads(sync_config)
                        sync_config_source = "DB (string parsed)"
                    except json.JSONDecodeError as json_err:
                        logger.warning(f"[Op:{operation_id}] Failed to parse outlook_sync_config string for user {owner_email}: {json_err}. Will attempt fallback.")
                else:
                     logger.warning(f"[Op:{operation_id}] User {owner_email} outlook_sync_config is not a dict or string: {type(sync_config)}. Will attempt fallback.")

                if parsed_config:
                    # Try to get primaryDomain from the parsed config
                    primary_domain = parsed_config.get("primaryDomain", "").strip().lower() or None
                    if primary_domain:
                        sync_config_source += " - primaryDomain found"
                    else:
                        # Explicitly log if key exists but value is empty/null
                        if "primaryDomain" in parsed_config:
                             logger.info(f"[Op:{operation_id}] 'primaryDomain' key found in config but is empty/null.")
                        else:
                             logger.info(f"[Op:{operation_id}] 'primaryDomain' key not found in config.")
                    
                    # Get allianceDomains from the parsed config
                    alliance_domains = parsed_config.get("allianceDomains", [])
                    if isinstance(alliance_domains, list):
                         alliance_domains_set = {str(domain).strip().lower() for domain in alliance_domains if isinstance(domain, str) and domain.strip()}
                    else:
                        logger.warning(f"[Op:{operation_id}] allianceDomains in config is not a list: {type(alliance_domains)}. Ignoring.")

            except (TypeError, AttributeError, KeyError) as cfg_err:
                # Catch errors accessing/parsing config fields after initial type check/load
                logger.error(f"[Op:{operation_id}] Error processing outlook_sync_config fields for user {owner_email}: {cfg_err}. Will attempt fallback.")
                primary_domain = None # Reset on error to ensure fallback logic runs
                alliance_domains_set = set()

        # *** Fallback Logic: If primary_domain wasn't found in config or user wasn't found, use owner_email's domain ***
        if not primary_domain:
            logger.info(f"[Op:{operation_id}] primaryDomain not found/invalid/user missing (Source: {sync_config_source}). Attempting fallback using owner_email: {owner_email}")
            primary_domain = _extract_domain(owner_email)
            if primary_domain:
                logger.info(f"[Op:{operation_id}] Using owner's email domain as primary reference: '{primary_domain}'")
                sync_config_source = "Owner Email Fallback" # Update source indicator
            else:
                 # This should be rare if owner_email is valid
                 logger.error(f"[Op:{operation_id}] Could not extract domain from owner_email '{owner_email}'. Cannot determine primary domain.")
                 sync_config_source = "Fallback Failed"

    else:
        logger.warning(f"[Op:{operation_id}] No DB session provided. Cannot fetch user or sync config. Attempting fallback using owner_email.")
        # Fallback directly if no DB session
        primary_domain = _extract_domain(owner_email)
        if primary_domain:
             logger.info(f"[Op:{operation_id}] Using owner's email domain as primary reference (no DB session): '{primary_domain}'")
             sync_config_source = "Owner Email Fallback (No DB)"
        else:
            logger.error(f"[Op:{operation_id}] Could not extract domain from owner_email '{owner_email}' (no DB session). Cannot determine primary domain.")
            sync_config_source = "Fallback Failed (No DB)"

    # Log final settings being used
    logger.info(f"[Op:{operation_id}] Final domains for outsider check -> Primary ('{primary_domain}' Source: {sync_config_source}), Alliance: {alliance_domains_set}")

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
                update_meta = {
                    'progress': progress_percent, # Keep updating percentage
                    'status': f'Processed email {i+1}/{total_emails_found}',
                    'processed_email_count': processed_email_count,
                    'failed_email_count': failed_email_count,
                    'processed_attachment_count': processed_attachment_count,
                    'failed_attachment_count': failed_attachment_count,
                    'total_emails_found': total_emails_found
                }
                update_state_func(state='PROGRESS', meta=update_meta)

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
                            temperature=0.2, 
                            max_tokens=150, # Increased max_tokens from 50
                            response_format={"type": "json_object"}
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

                # --- Prepare Attachment Details (for Iceberg parent row) ---
                processed_attachments_metadata = [] # Store metadata for parent row
                email_attachment_count = 0 # Count attachments *belonging to this specific email*
                email_failed_attachment_count = 0 # Count failures for *this specific email*

                if email_content.attachments:
                    for att_index, att in enumerate(email_content.attachments):
                        # Initialize flags for success tracking within the loop
                        upload_success = False
                        db_record_success = False
                        filename = getattr(att, 'name', 'unknown_filename')
                        att_id = getattr(att, 'id', str(uuid.uuid4())) # Use uuid.uuid4() for fallback ID
                        source_uri = f"email://{email_id}/attachment/{att_id}"

                        try:
                            # --- Check for existing ProcessedFile record FIRST ---
                            existing_record = None
                            if db_session and att_id:
                                try:
                                    existing_record = crud_processed_file.get_processed_file_by_source_id(db=db_session, source_identifier=source_uri)
                                except Exception as db_check_err:
                                    logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Error checking DB for existing ProcessedFile for {source_uri}: {db_check_err}", exc_info=True)
                            else:
                                logger.warning(f"[Op:{operation_id}] [Attach {att_index+1}] Skipping DB check for {att_id} due to missing DB session or attachment ID.")

                            if existing_record:
                                logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Attachment {att_id} ('{filename}') already processed (DB ID: {existing_record.id}, R2 Key: {existing_record.r2_object_key}). Using existing record.")
                                # Add metadata from existing record for the parent email row
                                processed_attachments_metadata.append({
                                    "id": att_id,
                                    "name": existing_record.original_filename,
                                    "contentType": existing_record.content_type,
                                    "size": existing_record.size_bytes,
                                    "isInline": False, # Assume not inline if processed (or get from DB if stored)
                                    "r2_key": existing_record.r2_object_key
                                })
                                email_attachment_count += 1 # Count as successfully processed for this email
                                processed_attachment_count += 1 # Increment global counter
                                continue # Skip to the next attachment

                            # --- Skip Inline/Images/Specific Extensions (No R2 Upload/DB Record) ---
                            is_inline = getattr(att, 'isInline', False)
                            attachment_extension = os.path.splitext(filename)[1].lower()
                            allowed_extensions = ['.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.pdf']

                            if is_inline:
                                logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Skipping inline attachment: {att_id} ('{filename}').")
                                continue
                            if attachment_extension not in allowed_extensions:
                                logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Skipping attachment: {att_id} ('{filename}') due to disallowed extension ('{attachment_extension}'). Allowed: {allowed_extensions}")
                                continue

                            # --- Fetch contentBytes separately only if needed ---
                            attachment_content_bytes = None
                            if r2_client and db_session:
                                try:
                                    attachment_content_bytes = await outlook_service.get_attachment_content(
                                        message_id=email_id,
                                        attachment_id=att_id
                                    )
                                    if not attachment_content_bytes:
                                        logger.warning(f"[Op:{operation_id}] [Attach {att_index+1}] Fetched attachment {att_id} but contentBytes was missing or empty.")
                                        email_failed_attachment_count += 1
                                        failed_attachment_count += 1
                                        continue
                                except Exception as content_fetch_err:
                                    logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Failed to fetch contentBytes for attachment {att_id}: {content_fetch_err}", exc_info=True)
                                    email_failed_attachment_count += 1
                                    failed_attachment_count += 1
                                    continue
                            else:
                                logger.warning(f"[Op:{operation_id}] [Attach {att_index+1}] Skipping contentBytes fetch and processing for {att_id} due to missing R2 client or DB session.")
                                email_failed_attachment_count += 1
                                failed_attachment_count += 1
                                continue

                            # --- Upload and Create DB Record ---
                            content_type = getattr(att, 'contentType', 'application/octet-stream')
                            r2_key = generate_email_attachment_r2_key(email_id, att_id, filename)
                            logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Uploading attachment '{filename}' as '{r2_key}' to R2 (Size: {len(attachment_content_bytes)} bytes).")

                            upload_successful = await r2_service.upload_bytes_to_r2(
                                r2_client=r2_client,
                                bucket_name=settings.R2_BUCKET_NAME,
                                object_key=r2_key,
                                data_bytes=attachment_content_bytes,
                                content_type=content_type
                            )

                            if upload_successful:
                                logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Successfully uploaded to R2 as '{r2_key}'.")
                                upload_success = True
                                # Now create the DB record
                                try:
                                    file_metadata = {
                                        "r2_object_key": r2_key,
                                        "original_filename": filename,
                                        "source_type": "email_attachment",
                                        "source_identifier": source_uri,
                                        "content_type": content_type,
                                        "size_bytes": getattr(att, 'size', len(attachment_content_bytes)), # Use actual size if available
                                        "status": "pending_analysis"
                                    }
                                    created_record = crud_processed_file.create_processed_file_entry(
                                        db=db_session,
                                        file_data=ProcessedFile(**file_metadata,
                                                              ingestion_job_id=ingestion_job_id,
                                                              owner_email=owner_email)
                                    )
                                    if created_record:
                                        logger.info(f"[Op:{operation_id}] [Attach {att_index+1}] Saved ProcessedFile {created_record.id} for attachment {att_id} ('{filename}').")
                                        db_record_success = True
                                        # Add metadata for the parent email row *after* successful upload and DB record
                                        processed_attachments_metadata.append({
                                            "id": att_id,
                                            "name": filename,
                                            "contentType": content_type,
                                            "size": file_metadata["size_bytes"],
                                            "isInline": is_inline, # Keep original value
                                            "r2_key": r2_key
                                        })
                                    else:
                                        logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] CRUD function failed to return ProcessedFile record for attachment {att_id} ('{filename}').")
                                except Exception as db_err:
                                    logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Failed to save ProcessedFile record for attachment {att_id} ('{filename}') after R2 upload: {db_err}", exc_info=True)
                                    # Even if DB fails, R2 upload succeeded, but we might want to handle this (e.g., retry DB later?)
                            else:
                                logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Call to r2_service.upload_bytes_to_r2 failed for key '{r2_key}'.")

                            # Update counters based on final success
                            if upload_success and db_record_success:
                                email_attachment_count += 1
                                processed_attachment_count += 1 # Increment global counter
                            else:
                                email_failed_attachment_count += 1
                                failed_attachment_count += 1 # Increment global counter

                        except Exception as att_error:
                            email_failed_attachment_count += 1
                            failed_attachment_count += 1 # Increment global counter
                            logger.error(f"[Op:{operation_id}] [Attach {att_index+1}] Unhandled error processing attachment {att_id} ('{filename}'): {att_error}", exc_info=True)

                has_attachments_bool = bool(processed_attachments_metadata) # Determine based on successfully processed/found attachments

                raw_text_content = email_content.body or ""
                if not raw_text_content and subject:
                    logger.warning(f"[Op:{operation_id}] Email {email_id} has empty body, using subject.")
                    raw_text_content = subject # Use subject if body is empty

                if not raw_text_content and not subject:
                     logger.warning(f"[Op:{operation_id}] Email {email_id} has empty body and subject. Skipping.")
                     failed_email_count += 1
                     continue # Skip this email if both body and subject are empty

                # --- Analyze Email Body for Flattened Structure ---
                quote_data_list = []
                email_body = raw_text_content # Use the potentially subject-filled content
                original_body_lines = []
                current_quote_block = []
                in_quote = False
                quote_depth = 0 # Reset for each email

                # Regex to detect common reply headers (adjust as needed)
                reply_header_pattern = re.compile(r"^\s*_{2,}\s*Original Message\s*_{2,}\s*$|" # ----- Original Message -----
                                                r"^\s*From:\s*.*$|"                            # From: ...
                                                r"^\s*Sent:\s*.*$|"                            # Sent: ...
                                                r"^\s*To:\s*.*$|"                              # To: ...
                                                r"^\s*Cc:\s*.*$|"                              # Cc: ...
                                                r"^\s*Subject:\s*.*$")                         # Subject: ...

                # Regex to detect quote indicators (e.g., '>', '>>')
                quote_indicator_pattern = re.compile(r"^\s*>+\s?")

                for line in email_body.splitlines():
                    is_reply_header = reply_header_pattern.match(line)
                    quote_match = quote_indicator_pattern.match(line)
                    current_line_depth = len(quote_match.group(0).strip()) if quote_match else 0

                    if is_reply_header and not in_quote:
                        # Start of a new quote block detected by header
                        # Finalize previous original body text block if any
                        if original_body_lines and not raw_text_content: # Only capture the first block
                             raw_text_content = "\n".join(original_body_lines).strip()
                             original_body_lines = [] # Reset for safety

                        # Finalize previous quote block if any (shouldn't happen if header starts a new block logically)
                        if current_quote_block:
                            quote_data_list.append({
                                "quoted_raw_text": "\n".join(current_quote_block).strip(),
                                "quoted_depth": quote_depth
                            })
                        current_quote_block = [line] # Start new block with header line
                        in_quote = True
                        quote_depth = 1 # Assume depth 1 for header block, could refine
                    elif quote_match:
                         # Line starts with '>'
                        current_line_depth = len(quote_match.group(0).strip())
                        if not in_quote:
                             # Transitioning from original text to quoted text
                             if original_body_lines and not raw_text_content: # Capture first original block
                                 raw_text_content = "\n".join(original_body_lines).strip()
                                 original_body_lines = []

                             in_quote = True
                             current_quote_block = [line]
                             quote_depth = current_line_depth
                        elif current_line_depth > quote_depth:
                             # Nested quote detected within the current block
                             # Keep appending to the same block but update max depth
                             current_quote_block.append(line)
                             quote_depth = current_line_depth # Update max depth for the block
                        elif current_line_depth < quote_depth:
                             # Depth decreased, signifies end of nested block and possibly start of new outer block
                             # Finalize the deeper block
                             if current_quote_block:
                                 quote_data_list.append({
                                    "quoted_raw_text": "\n".join(current_quote_block).strip(),
                                    "quoted_depth": quote_depth
                                 })
                             # Start new block with current line
                             current_quote_block = [line]
                             quote_depth = current_line_depth
                             in_quote = True # Remain in quote mode
                        else: # current_line_depth == quote_depth
                             # Continuation of the same quote level
                             current_quote_block.append(line)
                    elif in_quote:
                         # We were in a quote block, but this line doesn't start with '>' or header
                         # Check if it's likely continuation (not empty) or end (empty)
                         if line.strip():
                             # Assume continuation (handles wrapped lines)
                             current_quote_block.append(line)
                         else:
                             # Empty line likely signifies end of the current quote block
                             if current_quote_block:
                                 quote_data_list.append({
                                     "quoted_raw_text": "\n".join(current_quote_block).strip(),
                                     "quoted_depth": quote_depth
                                 })
                             current_quote_block = []
                             in_quote = False
                             quote_depth = 0
                             # Don't add the empty line itself to original_body_lines yet
                    else:
                         # Not in quote, not starting a quote -> must be original body
                         # Only collect if we haven't captured the first block yet
                         if not raw_text_content:
                            original_body_lines.append(line)

                # Finalize any remaining blocks after loop
                if current_quote_block:
                    quote_data_list.append({
                        "quoted_raw_text": "\n".join(current_quote_block).strip(),
                        "quoted_depth": quote_depth
                    })
                # Capture remaining original body lines if no quotes were found or if it's the last block
                if original_body_lines and not raw_text_content:
                    raw_text_content = "\n".join(original_body_lines).strip()

                # --- End Improved Quote Parsing Logic ---

                # ADDED: Log number of quotes found
                logger.debug(f"[Op:{operation_id}] Email {email_id}: Found {len(quote_data_list)} quote blocks.")

                # List to hold all rows (parent + quotes) for this email
                all_email_rows = []

                # --- Prepare Parent Email Row ---
                parent_row_id = email_id # Use real ID for parent row
                parent_email_data = {
                    "message_id": parent_row_id, # Real ID, used for upsert grouping
                    "row_id": parent_row_id, # Unique ID for THIS row (parent)
                    "job_id": str(ingestion_job_id) if ingestion_job_id else None,
                    "owner_email": owner_email,
                    "sender": email_content.sender_email, # Corrected: Use sender_email field
                    "sender_name": email_content.sender, # Corrected: Use sender field (which holds the name)
                    "recipients": json.dumps(email_content.recipients) if hasattr(email_content, 'recipients') and email_content.recipients else json.dumps([]),
                    "cc_recipients": json.dumps(email_content.cc_recipients) if hasattr(email_content, 'cc_recipients') and email_content.cc_recipients else json.dumps([]),
                    "bcc_recipients": json.dumps([]), # Assuming bcc is not directly available on EmailContent
                    "subject": email_content.subject,
                    "received_datetime_utc": ensure_utc(email_content.received_date, operation_id, email_id), # Corrected attribute name
                    "sent_datetime_utc": ensure_utc(email_content.sent_date, operation_id, email_id), # Corrected attribute name
                    "folder_id": filter_criteria.folder_id, # Assuming folder_id applies to parent
                    "conversation_id": email_content.conversation_id,
                    "has_attachments": has_attachments_bool, # Based on successfully processed/found ones
                    "attachment_count": len(processed_attachments_metadata), # Count of successfully processed/found
                    "attachment_details": json.dumps(processed_attachments_metadata), # Details of successfully processed/found
                    "generated_tags": json.dumps(generated_tags),
                    "ingested_at_utc": datetime.now(timezone.utc),
                    "body_text": raw_text_content, # Only parent body text
                    "granularity": "full_message", # ADDED: Indicate parent row
                    "quoted_raw_text": None,
                    "quoted_depth": 0, # Parent is depth 0
                }
                all_email_rows.append(parent_email_data)

                # --- Prepare Quote Rows (Conditional based on Outsider Status) ---
                outsider_quotes_saved_count = 0 # Counter for logging
                for idx, quote_data in enumerate(quote_data_list):
                    is_outsider = False # Default to False (insider/unknown)
                    quoted_sender_email = None
                    quoted_sender_domain = None

                    # Only check if we have domains defined to compare against
                    # If primary_domain is None and alliance_domains_set is empty, is_outsider remains False
                    can_check_outsider = bool(primary_domain or alliance_domains_set)
                    
                    if can_check_outsider:
                        raw_quote_text = quote_data.get("quoted_raw_text")
                        # Use the helper function to attempt sender extraction
                        quoted_sender_email = _extract_sender_from_quote(raw_quote_text) 

                        if quoted_sender_email:
                            # Use the helper function to attempt domain extraction
                            quoted_sender_domain = _extract_domain(quoted_sender_email) 
                            if quoted_sender_domain:
                                # *** Outsider Logic ***
                                # Check 1: Is primary_domain defined AND matches? -> Insider
                                if primary_domain and quoted_sender_domain == primary_domain:
                                    is_outsider = False
                                # Check 2: Is domain in alliance_domains_set? -> Insider
                                elif quoted_sender_domain in alliance_domains_set:
                                    is_outsider = False
                                # Check 3: If neither of the above, it's an outsider
                                else:
                                    is_outsider = True
                                    logger.debug(f"[Op:{operation_id}] Email {email_id}, Quote {idx+1}: Found OUTSIDER sender '{quoted_sender_email}' (domain '{quoted_sender_domain}').")
                                
                                if not is_outsider:
                                    logger.debug(f"[Op:{operation_id}] Email {email_id}, Quote {idx+1}: Found INSIDER sender '{quoted_sender_email}' (domain '{quoted_sender_domain}'). Skipping save.")
                            else:
                                 # Could not extract domain from the found email
                                 logger.debug(f"[Op:{operation_id}] Email {email_id}, Quote {idx+1}: Found sender email '{quoted_sender_email}' but could not extract domain. Treating as insider (skipping save).")
                                 is_outsider = False # Treat as insider if domain extraction fails
                        else:
                            # Could not extract sender email from the quote text
                            logger.debug(f"[Op:{operation_id}] Email {email_id}, Quote {idx+1}: Could not extract sender email from quote text. Treating as insider (skipping save).")
                            is_outsider = False # Treat as insider if sender extraction fails
                    else:
                        # If no primary/alliance domains configured, cannot determine outsider status.
                        # Defaulting to NOT saving any quotes in this case.
                         logger.debug(f"[Op:{operation_id}] Email {email_id}, Quote {idx+1}: Skipping quote save as primary/alliance domains not configured or parsed.")
                         is_outsider = False # Ensure is_outsider is False

                    # *** Only proceed if the quote is determined to be from an outsider ***
                    if is_outsider:
                        outsider_quotes_saved_count += 1
                        quote_row_id = f"{parent_row_id}_quote_{idx+1}" # Synthetic ID for quote row
                        quote_email_data = {
                            "message_id": quote_row_id, 
                            "row_id": quote_row_id, # Keep this for now, though potentially redundant
                            "job_id": str(ingestion_job_id) if ingestion_job_id else None,
                            "owner_email": owner_email,
                            # Still inherit parent details as fallback/context, sender fields ideally would be the parsed ones if needed later
                            "sender": email_content.sender_email, # Inherited parent sender email
                            "sender_name": email_content.sender, # Inherited parent sender name
                            "recipients": json.dumps([]), # Quotes likely don't have distinct recipients
                            "cc_recipients": json.dumps([]),
                            "bcc_recipients": json.dumps([]),
                            "subject": email_content.subject, # Inherit parent subject
                            "received_datetime_utc": ensure_utc(email_content.received_date, operation_id, email_id), # Inherit parent received time
                            "sent_datetime_utc": ensure_utc(email_content.sent_date, operation_id, email_id), # Inherit parent sent time
                            "folder_id": filter_criteria.folder_id, # Inherit parent folder
                            "conversation_id": email_content.conversation_id, # Inherit parent conversation ID
                            "has_attachments": False, # Quotes don't have attachments themselves
                            "attachment_count": 0,
                            "attachment_details": json.dumps([]),
                            "generated_tags": json.dumps([]), # Tags apply to parent message usually
                            "ingested_at_utc": datetime.now(timezone.utc),
                            "body_text": None, # Body text belongs to parent
                            "granularity": "quoted_message", # Indicate quote row
                            # Quote-specific fields:
                            "quoted_raw_text": quote_data.get("quoted_raw_text"),
                            "quoted_depth": quote_data.get("quoted_depth", 1), # Default depth 1 if missing
                            # Optional: Add the extracted info if schema allows/needs it
                            # "quoted_sender_email": quoted_sender_email, 
                            # "quoted_sender_domain": quoted_sender_domain,
                            # "is_quoted_sender_outsider": True 
                        }
                        all_email_rows.append(quote_email_data)

                # ADDED: Log count of *saved* outsider quotes
                logger.debug(f"[Op:{operation_id}] Email {email_id}: Found {len(quote_data_list)} total quote blocks. Saved {outsider_quotes_saved_count} outsider quote rows.")
                
                # --- End Conditional Quote Row Preparation ---

                # ADDED: Log total rows generated for this email before extending
                logger.debug(f"[Op:{operation_id}] Email {email_id}: Generated {len(all_email_rows)} total rows (parent + saved quotes). Extending facts_for_iceberg.")

                # Add the list of dictionaries (parent + quotes) to the main list for Celery
                facts_for_iceberg.extend(all_email_rows)

                # Update progress using the callback
                processed_email_count += 1
                if update_state_func:
                    # Corrected call structure to match expected signature (state, meta)
                    # Pass detailed counts in the meta dictionary
                    update_meta = {
                        'progress': progress_percent,  # Keep updating overall progress percentage
                        'status': f'Processed email {i+1}/{total_emails_found}',  # Update status message
                        'processed_email_count': processed_email_count,
                        'failed_email_count': failed_email_count,
                        'processed_attachment_count': processed_attachment_count,
                        'failed_attachment_count': failed_attachment_count,
                        'total_emails_found': total_emails_found
                    }
                    update_state_func(state='PROGRESS', meta=update_meta)

                # Log progress periodically
                if processed_email_count % 10 == 0:
                    logger.info(f"[Op:{operation_id}] Processed {processed_email_count}/{total_emails_found} emails...")

            except Exception as process_err:
                logger.error(f"[Op:{operation_id}] Failed to process email_id {email_id}: {process_err}", exc_info=True)
                failed_email_count += 1
                # Optionally update state for this specific email failure

    except Exception as outer_loop_err:
        logger.error(f"[Op:{operation_id}] Error during main processing setup/loop: {str(outer_loop_err)}", exc_info=True)
        # Update state to reflect a more serious failure if needed
        if update_state_func:
            update_state_func(state='FAILURE', meta={'error': f'Outer loop error: {str(outer_loop_err)}'})

    logger.info(f"[Op:{operation_id}] Email processing loop finished. Emails Processed: {processed_email_count}, Emails Failed: {failed_email_count}. Attachments Found/Processed: {processed_attachment_count}, Attachments Failed: {failed_attachment_count}. Total Records for Iceberg: {len(facts_for_iceberg)}")
    # MODIFIED: Return the list of fact dictionaries for Iceberg, plus global attachment counts
    return processed_email_count, failed_email_count, processed_attachment_count, failed_attachment_count, facts_for_iceberg

# Helper function to ensure datetime is UTC
# MODIFIED: Added context parameters for logging
def ensure_utc(dt_obj: datetime | str | None, operation_id: str = "UNKNOWN_OP", email_id: str = "UNKNOWN_EMAIL") -> datetime | None:
    if dt_obj is None: return None

    # Handle string input (common from APIs)
    if isinstance(dt_obj, str):
        try:
            # Attempt ISO 8601 parsing, common format
            dt_obj = datetime.fromisoformat(dt_obj.replace('Z', '+00:00'))
        except ValueError:
             logger.error(f"[Op:{operation_id}] Email {email_id}: ensure_utc received unparseable string: {dt_obj}. Cannot process.")
             return None

    # Ensure input is now a datetime object
    if not isinstance(dt_obj, datetime):
         logger.error(f"[Op:{operation_id}] Email {email_id}: ensure_utc received non-datetime/non-string object: {type(dt_obj)}. Cannot process.")
         return None

    if dt_obj.tzinfo is None:
        logger.warning(f"[Op:{operation_id}] Email {email_id}: Making naive datetime {dt_obj} UTC-aware.")
        return dt_obj.replace(tzinfo=timezone.utc)
    elif dt_obj.tzinfo != timezone.utc:
        logger.debug(f"[Op:{operation_id}] Email {email_id}: Converting timezone-aware datetime {dt_obj} to UTC.")
        return dt_obj.astimezone(timezone.utc)
    else:
        # Already UTC and timezone-aware
        return dt_obj

def get_email_address(recipient_obj) -> str | None:
    """Safely extracts email address string from Outlook recipient object."""
    if recipient_obj and hasattr(recipient_obj, 'emailAddress') and recipient_obj.emailAddress:
        return getattr(recipient_obj.emailAddress, 'address', None)
    return None