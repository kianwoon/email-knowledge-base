import json
import re  # For rate-card dollar filtering
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import logging # Import logging
import asyncio  # For async operations
from datetime import datetime, timedelta, timezone # Added datetime imports
from zoneinfo import ZoneInfo # Added ZoneInfo import

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.models.user import User # Assuming User model is here
# Import RAG components - Updated for Milvus
from app.services.embedder import create_embedding, search_milvus_knowledge, search_milvus_knowledge_sparse, create_retrieval_embedding
# Removed: search_qdrant_knowledge, search_qdrant_knowledge_sparse
from app.crud import api_key_crud # Import API key CRUD
from fastapi import HTTPException, status # Import HTTPException
# Qdrant specific imports (no longer needed for search in llm.py)
# from qdrant_client import models
# from qdrant_client.http.models import PayloadField, Filter, IsEmptyCondition
import itertools  # for merging hybrid search results
# Import DuckDB and PyIceberg Catalog
import duckdb
from pyiceberg.catalog import load_catalog, Catalog
from pyiceberg.exceptions import NoSuchTableError
from app.services.outlook import OutlookService # ADDED: Import OutlookService

# Set up logger for this module
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

# --- START: Global Catalog Variable (Initialize lazily) ---
# Use a global variable to hold the catalog instance to avoid reinitialization on every call.
# Ensure thread-safety if your application uses threads extensively for requests.
_iceberg_catalog: Optional[Catalog] = None
_catalog_lock = asyncio.Lock() # Use asyncio lock for async context

async def get_iceberg_catalog() -> Catalog:
    """Initializes and returns the Iceberg catalog instance, ensuring it's done only once."""
    global _iceberg_catalog
    async with _catalog_lock:
        if _iceberg_catalog is None:
            logger.info("Initializing Iceberg REST Catalog for DuckDB integration...")
            try:
                catalog_props = {
                    # Use a distinct name
                    "name": settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_duckdb_llm",
                    "uri": settings.R2_CATALOG_URI,
                    "warehouse": settings.R2_CATALOG_WAREHOUSE,
                    "token": settings.R2_CATALOG_TOKEN,
                    # Add S3 specific creds if needed by PyArrowFileIO used under the hood
                    # These might come from settings or environment variables
                    # "s3.endpoint": settings.R2_ENDPOINT_URL, 
                    # "s3.access-key-id": settings.R2_ACCESS_KEY_ID,
                    # "s3.secret-access-key": settings.R2_SECRET_ACCESS_KEY
                }
                # Remove None values from props before passing to load_catalog
                catalog_props = {k: v for k, v in catalog_props.items() if v is not None}
                _iceberg_catalog = load_catalog(**catalog_props)
                logger.info("Iceberg Catalog initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Iceberg Catalog: {e}", exc_info=True)
                # Raise or handle appropriately - maybe return None or raise specific exception
                raise RuntimeError(f"Could not initialize Iceberg Catalog: {e}") from e
    return _iceberg_catalog
# --- END: Global Catalog Variable ---

# Keep the global client for other potential uses (like analyze_email_content)
# But Jarvis chat will use a user-specific key if available.
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# --- START: DuckDB Query Helper ---
async def query_iceberg_emails_duckdb(
    user_email: str,
    keywords: List[str],
    limit: int = 5,
    original_message: str = "" # Added original_message parameter
) -> List[Dict[str, Any]]:
    """Queries the email_facts Iceberg table for a user using DuckDB and keywords, with optional date filtering."""
    results = []
    if not keywords and not original_message: # Allow query if message contains date phrase even without keywords
        logger.debug("No keywords provided and no date phrase detected, skipping DuckDB query.")
        return results

    try:
        catalog = await get_iceberg_catalog()
        if not catalog:
            # Catalog initialization failed earlier
            return results

        full_table_name = f"{settings.ICEBERG_DEFAULT_NAMESPACE}.{settings.ICEBERG_EMAIL_FACTS_TABLE}"

        # Load the Iceberg table object
        try:
            iceberg_table = catalog.load_table(full_table_name)
        except NoSuchTableError:
            logger.error(f"Iceberg table {full_table_name} not found.")
            return results

        # Connect to an in-memory DuckDB database
        con = duckdb.connect(database=':memory:', read_only=False)

        # Register the Iceberg table view
        view_name = 'email_facts_view'
        iceberg_table.scan().to_duckdb(table_name=view_name, connection=con)

        # --- START: Date Filtering Logic (Refined) ---
        date_filter_sql = ""
        params = [user_email] # Start params list with user_email
        start_date_utc: Optional[datetime] = None
        end_date_utc: Optional[datetime] = None

        # Simple date phrase parsing (can be expanded)
        # Assume SGT for relative phrases like "last 2 weeks" if timezone unspecified
        # TODO: Make timezone configurable or detect from user profile
        try:
            sgt = ZoneInfo("Asia/Singapore") 
            now_local = datetime.now(sgt)
            message_lower = original_message.lower() if original_message else ""

            if "last 2 weeks" in message_lower or "past 2 weeks" in message_lower:
                start_date_local = now_local - timedelta(weeks=2)
                end_date_local = now_local
                start_date_utc = start_date_local.astimezone(timezone.utc)
                end_date_utc = end_date_local.astimezone(timezone.utc)
            elif "last week" in message_lower or "past week" in message_lower:
                start_date_local = now_local - timedelta(weeks=1)
                end_date_local = now_local
                start_date_utc = start_date_local.astimezone(timezone.utc)
                end_date_utc = end_date_local.astimezone(timezone.utc)
            elif "yesterday" in message_lower:
                start_date_local = (now_local - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date_local = (now_local - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
                start_date_utc = start_date_local.astimezone(timezone.utc)
                end_date_utc = end_date_local.astimezone(timezone.utc)
            elif "today" in message_lower:
                start_date_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date_local = now_local # Use current time as end for "today"
                start_date_utc = start_date_local.astimezone(timezone.utc)
                end_date_utc = end_date_local.astimezone(timezone.utc)
            # Add more phrases as needed (e.g., "last month", "this year", specific dates)

            if start_date_utc and end_date_utc:
                # Ensure end_date includes the full day if it was set to midnight
                if end_date_utc.hour == 0 and end_date_utc.minute == 0 and end_date_utc.second == 0:
                    end_date_utc = end_date_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                date_filter_sql = " AND received_datetime_utc >= ? AND received_datetime_utc <= ?" 
                # Insert date params *after* user_email but *before* keywords
                params.insert(1, start_date_utc)
                params.insert(2, end_date_utc)
                logger.info(f"Applying date filter: >= {start_date_utc.isoformat()} AND <= {end_date_utc.isoformat()} UTC")
            elif original_message and any(phrase in message_lower for phrase in ["last 2 weeks", "past 2 weeks", "last week", "past week", "yesterday", "today"]):
                 logger.warning(f"Date phrase detected ('{original_message}') but failed to parse into date range. Querying without date filter.")

        except Exception as tz_err:
            logger.error(f"Could not apply timezone-aware date filter: {tz_err}. Proceeding without date filter.", exc_info=True)
            date_filter_sql = "" # Ensure filter is empty on error
            params = [user_email] # Reset params if date parsing fails mid-way
        # --- END: Date Filtering Logic ---

        # Build WHERE clause for keywords (simple LIKE matching)
        keyword_params = []
        keyword_filter = ""
        if keywords: 
            like_clauses = []
            for kw in keywords:
                like_clauses.append(f"(subject LIKE ? OR body_text LIKE ? OR sender LIKE ? OR sender_name LIKE ?)")
                # Escape % and _ within the keyword itself before adding wildcards
                safe_kw = kw.replace('%', '\\%').replace('_', '\\_')
                keyword_params.extend([f'%{safe_kw}%', f'%{safe_kw}%', f'%{safe_kw}%', f'%{safe_kw}%'])
            keyword_filter = " OR ".join(like_clauses)
            params.extend(keyword_params) # Add keyword params to the list
        else:
            # If no keywords but date filter exists, we need a valid filter condition
            if date_filter_sql:
                keyword_filter = "1=1" # Or just omit the AND clause later
            else: # No keywords and no date filter - this case should be handled by the initial check
                 logger.warning("Querying DuckDB with no keywords and no date filter - should have been skipped.")
                 con.close()
                 return []

        # Construct the full SQL query
        # Ensure AND is added only if both date and keyword filters exist
        sql_query = f"""
        SELECT
            message_id,
            subject,
            sender,
            received_datetime_utc,
            generated_tags,
            body_text as body_snippet
        FROM {view_name}
        WHERE owner_email = ? 
          {date_filter_sql} 
          { "AND (" + keyword_filter + ")" if keyword_filter else ""} 
        ORDER BY received_datetime_utc DESC
        LIMIT ?;
        """
        params.append(limit) # Add limit to parameters

        logger.debug(f"Executing DuckDB query for user {user_email}. SQL: {sql_query.strip()} PARAMS: {params}")

        # Execute and fetch results
        result_df = con.execute(sql_query, params).fetchdf()
        logger.info(f"DuckDB query returned {len(result_df)} email facts for user {user_email}.")

        # Convert to list of dicts
        results = result_df.to_dict('records')

        con.close()

    except Exception as e:
        logger.error(f"DuckDB query failed for user {user_email}: {e}", exc_info=True)
        if 'con' in locals() and con:
            try:
                con.close()
            except Exception as close_err:
                logger.error(f"Error closing DuckDB connection: {close_err}")

    return results
# --- END: DuckDB Query Helper ---


async def analyze_email_content(email: EmailContent) -> EmailAnalysis:
    """
    Analyze email content using ChatGPT-4o mini to extract knowledge, tags, and detect PII
    """
    # Prepare the content for analysis
    content_to_analyze = f"""
Subject: {email.subject}
From: {email.sender} <{email.sender_email}>
Date: {email.received_date.isoformat()}
Body:
{email.body}
    """
    
    # Add attachment content if available
    if email.attachments:
        content_to_analyze += "\n\nAttachments:"
        for attachment in email.attachments:
            if attachment.content:
                content_to_analyze += f"\n\n{attachment.name}:\n{attachment.content}"
    
    # Create the prompt for the LLM
    system_prompt = """
You are an AI assistant that analyzes emails to extract knowledge and detect sensitive information.
Analyze the provided email and extract the following information:
1. Sensitivity level (low, medium, high, critical)
2. Department the knowledge belongs to (general, engineering, product, marketing, sales, finance, hr, legal, other)
3. Relevant tags for categorizing the content (3-5 tags)
4. Whether the email contains private/confidential information (true/false)
5. Types of personal identifiable information (PII) detected (name, email, phone, address, ssn, passport, credit_card, bank_account, date_of_birth, salary, other)
6. Recommended action (store or exclude)
7. Brief summary of the content (1-2 sentences)
8. Key knowledge points extracted (3-5 bullet points)

Respond with a JSON object containing these fields.
"""
    
    user_prompt = f"""
Please analyze this email content:

{content_to_analyze}

Return a JSON object with the following fields:
- sensitivity: The sensitivity level (low, medium, high, critical)
- department: The department this knowledge belongs to (general, engineering, product, marketing, sales, finance, hr, legal, other)
- tags: Array of relevant tags for categorizing this content (3-5 tags)
- is_private: Boolean indicating if this contains private/confidential information
- pii_detected: Array of PII types detected (empty array if none)
- recommended_action: "store" or "exclude"
- summary: Brief summary of the content
- key_points: Array of key knowledge points extracted
"""
    
    try:
        # Call OpenAI API
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        
        # Create EmailAnalysis object
        analysis = EmailAnalysis(
            sensitivity=result.get("sensitivity", "low"),
            department=result.get("department", "general"),
            tags=result.get("tags", []),
            is_private=result.get("is_private", False),
            pii_detected=result.get("pii_detected", []),
            recommended_action=result.get("recommended_action", "exclude" if result.get("is_private", False) else "store"),
            summary=result.get("summary", ""),
            key_points=result.get("key_points", [])
        )
        
        return analysis
    
    except Exception as e:
        # Log the error and return a default analysis
        print(f"Error analyzing email: {str(e)}")
        return EmailAnalysis(
            sensitivity=SensitivityLevel.LOW,
            department=Department.GENERAL,
            tags=["error", "processing_failed"],
            is_private=True,  # Default to private if analysis fails
            pii_detected=[],
            recommended_action="exclude",
            summary="Analysis failed. Please review manually.",
            key_points=["Analysis failed due to an error."]
        )


# CORRECTED Function Definition
async def generate_openai_rag_response(
    message: str,
    chat_history: List[Dict[str, str]],
    user: User,
    db: Session, # Database session
    model_id: Optional[str] = None,  # Override the default LLM model
    ms_token: Optional[str] = None # ADDED: Pass validated MS token if available
) -> str:
    """
    Generates a chat response using RAG with context from Milvus and Iceberg (emails),
    using an LLM to select/synthesize the most relevant context.
    Fails if the user has not provided their OpenAI API key.
    """
    # Outer try block corresponding to original line 267
    try:
        # Determine model and user-specific client
        chat_model = model_id or settings.OPENAI_MODEL_NAME
        logger.debug(f"Using LLM model: {chat_model} for user {user.email}")
        user_openai_key = api_key_crud.get_decrypted_api_key(db, user.email, "openai")
        if not user_openai_key:
            logger.warning(f"User {user.email} missing OpenAI key.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OpenAI API key required.")
        user_client = AsyncOpenAI(api_key=user_openai_key, timeout=settings.OPENAI_TIMEOUT_SECONDS or 30.0)

        # --- START: Simple Intent Detection for Calendar ---
        calendar_keywords = ["meeting", "calendar", "event", "appointment", "schedule", "upcoming"]
        is_calendar_query = any(keyword in message.lower() for keyword in calendar_keywords)
        logger.debug(f"Is calendar query detected: {is_calendar_query}")
        # --- END: Simple Intent Detection ---

        # 1. Extract Keywords for Email Search
        # Basic word extraction
        basic_keywords = [word for word in re.findall(r'\b\w{3,}\b', message.lower()) 
                          if word not in ['the', 'a', 'is', 'and', 'or', 'find', 'search', 'email', 'emails', 'how', 'many', 'last', 'weeks']]
        # Extract email addresses specifically
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        extracted_emails = re.findall(email_pattern, message)
        # Combine and deduplicate
        keywords_for_email = list(set(basic_keywords + extracted_emails))
        # Remove empty strings just in case
        keywords_for_email = [kw for kw in keywords_for_email if kw]

        logger.debug(f"Extracted keywords for email search: {keywords_for_email}")

        # 2. Retrieve Context from Both Sources Concurrently
        async def _get_milvus_context(max_items: int, max_chunk_chars: int):
            logger.debug(f"Starting Milvus context retrieval (max_items={max_items}, max_chars={max_chunk_chars})...")
            # Define truncate helper locally
            def _truncate_text(text: str, max_len: int) -> str:
                if len(text) > max_len:
                    return text[:max_len] + "... [TRUNCATED]"
                return text
            try:
                retrieval_query = message
                refined = None
                # Query refinement step
                if 'rate card' not in message.lower():
                    # try corresponding to original line 289
                    try:
                        # Correctly define the list of dictionaries
                        refine_msgs = [
                            {
                                "role": "system",
                                "content": ("You are a query refiner. Extract the target table/section and the entity from the user question. "
                                            "Return JSON with keys 'table' and 'role'.")
                            },
                            {
                                "role": "user",
                                "content": f"Question: {message}\\nRespond with JSON: {{\\\"table\\\":\\\"...\\\", \\\"role\\\":\\\"...\\\"}}. If not applicable return nulls."
                            }
                        ]
                        # Ensure the create call parentheses are balanced
                        resp_refine = await user_client.chat.completions.create(
                            model=chat_model,
                            messages=refine_msgs,
                            temperature=0.0,
                            response_format={"type": "json_object"}
                        )
                        content = resp_refine.choices[0].message.content
                        if content and content.strip().lower() != 'null':
                            refined = json.loads(content)
                            parts = []
                            if refined and refined.get('table'): parts.append(refined['table'])
                            if refined and refined.get('role'): parts.append(refined['role'])
                            if parts:
                                retrieval_query = ' '.join(parts)
                                logger.debug(f"RAG: Refined retrieval query for Milvus: {retrieval_query}")
                        else:
                            logger.debug("Query refinement deemed not applicable.")
                    # Add except block for inner try (line 289)
                    except Exception as refine_e:
                        logger.warning(f"Query refinement failed, using original message: {refine_e}", exc_info=True)
                else:
                    logger.debug("RAG: Skipping query refinement for rate card query.")

                # --- START: HyDE Generation (Assumed Correct) ---
                hyde_document = retrieval_query
                if 'rate card' not in message.lower() and getattr(settings, 'ENABLE_HYDE', True):
                    try:
                        hyde_msgs = [
                            {"role": "system", "content": ("You are an assistant that generates a concise, factual hypothetical document "
                                                          "that directly answers the user's question. Output only the document content, no extra text.")},
                            {"role": "user", "content": f"Generate a hypothetical document answering: {message}"}
                        ]
                        hyde_resp = await user_client.chat.completions.create(model=chat_model, messages=hyde_msgs, temperature=0.0)
                        generated_doc = hyde_resp.choices[0].message.content.strip()
                        if generated_doc:
                            hyde_document = generated_doc
                            logger.debug(f"RAG: Generated HyDE document for Milvus: {hyde_document[:50]}...")
                        else:
                            logger.warning("HyDE generation returned empty content, using retrieval_query for Milvus embedding.")
                    except Exception as hyde_e:
                        logger.warning(f"HyDE generation failed, using retrieval_query for Milvus embedding: {hyde_e}", exc_info=True)
                elif 'rate card' in message.lower():
                    logger.debug("RAG: Skipping HyDE generation for rate card query.")
                hyde_embedding = await create_retrieval_embedding(hyde_document, field='dense')
                logger.debug(f"RAG: Generated HyDE embedding for Milvus retrieval.")
                # --- END HyDE Generation ---

                # --- Search Milvus (Dense + Sparse + RRF) (Assumed Correct) ---
                search_filter = None
                k_dense = int(getattr(settings, 'RAG_DENSE_RESULTS', 5))
                k_sparse = int(getattr(settings, 'RAG_SPARSE_RESULTS', 5))
                sanitized_email = user.email.replace('@', '_').replace('.', '_')
                target_collection_name = f"{sanitized_email}_knowledge_base_bm"
                logger.info(f"RAG: Targeting Milvus search in collection: {target_collection_name}")
                dense_task = search_milvus_knowledge(collection_name=target_collection_name, query_embedding=hyde_embedding, limit=k_dense, filter_expression=search_filter)
                sparse_task = search_milvus_knowledge_sparse(collection_name=target_collection_name, query_text=retrieval_query, limit=k_sparse, filter_expression=search_filter)
                dense_search_results, sparse_search_results = await asyncio.gather(dense_task, sparse_task)
                logger.debug(f"RAG: Milvus Dense search returned {len(dense_search_results)} results.")
                logger.debug(f"RAG: Milvus Sparse search returned {len(sparse_search_results)} results.")
                combined_results = {}
                rrf_k = 60
                for rank, hit in enumerate(dense_search_results):
                    doc_id = hit["id"]
                    score = 1.0 / (rank + 1 + rrf_k)
                    if doc_id not in combined_results: combined_results[doc_id] = {"score": 0, "payload": hit["payload"], "id": doc_id}
                    combined_results[doc_id]["score"] += score
                for rank, hit in enumerate(sparse_search_results):
                    doc_id = hit["id"]
                    score = 1.0 / (rank + 1 + rrf_k)
                    if doc_id not in combined_results: combined_results[doc_id] = {"score": 0, "payload": hit.get("payload", {}), "id": doc_id}
                    combined_results[doc_id]["score"] += score
                ranked_results = sorted(combined_results.values(), key=lambda x: x["score"], reverse=True)
                logger.debug(f"RAG: Combined {len(ranked_results)} unique Milvus results after RRF.")
                # Apply item limit and chunk truncation HERE before returning
                milvus_context = "\n\n---\n\n".join([
                    f"Document ID: {res['id']}\nContent: {_truncate_text(json.dumps(res['payload']), max_chunk_chars)}"
                    for res in ranked_results[:max_items] # Use max_items limit
                ])
                return milvus_context
            # Add except block for try (line 284)
            except Exception as e_milvus:
                logger.error(f"Failed to retrieve Milvus context: {e_milvus}", exc_info=True)
                return "Error retrieving knowledge base context."

        async def _get_email_context(max_items: int, max_chunk_chars: int):
            logger.debug(f"Starting Email context retrieval (max_items={max_items}, max_chars={max_chunk_chars})...")
            # Define truncate helper locally
            def _truncate_text(text: str, max_len: int) -> str:
                if len(text) > max_len:
                    return text[:max_len] + "... [TRUNCATED]"
                return text
            try:
                # Use the max_items limit when querying emails
                email_results = await query_iceberg_emails_duckdb(
                    user_email=user.email,
                    keywords=keywords_for_email,
                    limit=max_items, # Use max_items for query limit
                    original_message=message
                )
                if not email_results:
                    return "No relevant emails found."
                # Apply chunk truncation HERE before returning
                email_context = "\n\n---\n\n".join([
                    f"Email ID: {email.get('message_id')}\n"
                    f"Received: {email.get('received_datetime_utc')}\n"
                    f"Sender: {email.get('sender')}\n"
                    f"Subject: {email.get('subject')}\n"
                    f"Tags: {email.get('generated_tags')}\n"
                    # Truncate email snippet using the helper
                    f"Snippet: {_truncate_text(email.get('body_snippet', ''), max_chunk_chars)}"
                    # No need for [:max_items] here as limit was applied in query
                    for email in email_results 
                ])
                return email_context
            except Exception as e_email:
                logger.error(f"Failed to retrieve Email context: {e_email}", exc_info=True)
                return "Error retrieving email context."

        # --- START: New Calendar Context Retrieval Helper ---
        async def _get_calendar_context():
            if not is_calendar_query:
                return "Calendar query not detected."
            if not ms_token: # Check if MS token was passed
                logger.warning("MS token not available, cannot fetch calendar events.")
                return "Error: Cannot fetch calendar events (auth token missing)."

            logger.debug("Starting Calendar context retrieval...")
            try:
                outlook_service = OutlookService(access_token=ms_token)
                # Fetch events for the next 7 days (default in get_upcoming_events)
                events = await outlook_service.get_upcoming_events()
                if not events:
                    return "No upcoming calendar events found in the next 7 days."
                
                # Format events for context
                calendar_context = "\n\n---\n\n".join([
                    f"Event Subject: {event.get('subject')}\n"
                    f"Start: {event.get('start_time')} ({event.get('start_timezone')})\n"
                    f"End: {event.get('end_time')} ({event.get('end_timezone')})\n"
                    f"Location: {event.get('location')}\n"
                    f"Attendees: {', '.join(event.get('attendees', []))}\n"
                    f"Preview: {event.get('preview', '')[:100]}..." # Limit preview length
                    for event in events
                ])
                return calendar_context
            except Exception as e_cal:
                logger.error(f"Failed to retrieve Calendar context: {e_cal}", exc_info=True)
                return "Error retrieving calendar context."
        # --- END: New Calendar Context Retrieval Helper ---

        # Read limits from settings, with defaults
        MAX_MILVUS_CONTEXT_ITEMS = int(getattr(settings, 'RAG_LLM_MILVUS_LIMIT', 1))
        MAX_EMAIL_CONTEXT_ITEMS = int(getattr(settings, 'RAG_LLM_EMAIL_LIMIT', 1))
        MAX_CALENDAR_CONTEXT_ITEMS = int(getattr(settings, 'RAG_LLM_CALENDAR_LIMIT', 5))
        # Define max characters per context item
        MAX_CHUNK_CHARS = int(getattr(settings, 'RAG_CHUNK_MAX_CHARS', 5000))

        logger.debug(f"Using LLM context limits - Milvus: {MAX_MILVUS_CONTEXT_ITEMS}, Email: {MAX_EMAIL_CONTEXT_ITEMS}, Calendar: {MAX_CALENDAR_CONTEXT_ITEMS}")
        logger.debug(f"Using max chars per chunk: {MAX_CHUNK_CHARS}")

        # Run retrievals concurrently, passing the limits
        retrieved_milvus_context, retrieved_email_context, retrieved_calendar_context = await asyncio.gather(
            _get_milvus_context(max_items=MAX_MILVUS_CONTEXT_ITEMS, max_chunk_chars=MAX_CHUNK_CHARS),
            _get_email_context(max_items=MAX_EMAIL_CONTEXT_ITEMS, max_chunk_chars=MAX_CHUNK_CHARS),
            _get_calendar_context() # Calendar still gets full context for now
        )

        # Now use the already limited/truncated results directly
        limited_milvus_context = retrieved_milvus_context
        limited_email_context = retrieved_email_context
        limited_calendar_context = retrieved_calendar_context

        # Log lengths before combining for LLM call
        logger.debug(f"Context Lengths - Milvus: {len(limited_milvus_context)} chars, Email: {len(limited_email_context)} chars, Calendar: {len(limited_calendar_context)} chars")

        selection_prompt = f"""Based on the user's question: '{message}'

Evaluate the following three sets of retrieved context:

<Knowledge Base Results (Top {MAX_MILVUS_CONTEXT_ITEMS})>
{limited_milvus_context}
</Knowledge Base Results>

<User Email Results (Top {MAX_EMAIL_CONTEXT_ITEMS})>
{limited_email_context}
</User Email Results>

<Calendar Events>
{limited_calendar_context}
</Calendar Events>

Determine which context source (Knowledge Base, Emails, Calendar) is most relevant, or if multiple are needed. Briefly explain your reasoning.
Then, synthesize the most pertinent information from the relevant source(s) into a concise summary that will directly help answer the user's question.
If the user's question asks for a quantity (e.g., "how many", "count", "list all"), explicitly count the relevant items found in the context and state the total count using digits (e.g., "Found 5 relevant items:") in your Synthesized Context.
Focus only on the information needed to answer '{message}'.
Output:
Reasoning: [Your brief reasoning]
Synthesized Context: [Your concise summary including the count using digits if applicable, or indicate if none is relevant]
"""
        synthesized_context = "No relevant context synthesized."
        try:
            selection_response = await user_client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that evaluates and synthesizes retrieved information to determine relevance to a user's question."},
                    {"role": "user", "content": selection_prompt}
                ],
                temperature=0.0
            )
            raw_synthesis_output = selection_response.choices[0].message.content
            logger.debug(f"Intermediate LLM Context Selection/Synthesis Output:\n{raw_synthesis_output}")
            match = re.search(r"Synthesized Context:\s*(.*)", raw_synthesis_output, re.DOTALL | re.IGNORECASE)
            if match:
                extracted_context = match.group(1).strip()
                if extracted_context and not extracted_context.lower().startswith(("no relevant", "neither source")):
                     synthesized_context = extracted_context
                else:
                     synthesized_context = "No relevant context was found or synthesized from the knowledge base, emails, or calendar."
            else:
                logger.warning("Could not parse Synthesized Context from intermediate LLM response. Using raw output.")
                synthesized_context = raw_synthesis_output
        except Exception as synth_err:
            logger.error(f"Intermediate LLM call for context synthesis failed: {synth_err}", exc_info=True)
            logger.warning("Falling back to combining limited contexts due to synthesis error.")
            # Use the LIMITED contexts in the fallback as well
            # Also log the lengths here for the fallback scenario
            logger.debug(f"Fallback Context Lengths - Milvus: {len(limited_milvus_context)} chars, Email: {len(limited_email_context)} chars, Calendar: {len(limited_calendar_context)} chars")
            synthesized_context = f"Knowledge Base Context (Top {MAX_MILVUS_CONTEXT_ITEMS}):\n{limited_milvus_context}\n\nEmail Context (Top {MAX_EMAIL_CONTEXT_ITEMS}):\n{limited_email_context}\n\nCalendar Context (Top {MAX_CALENDAR_CONTEXT_ITEMS}):\n{limited_calendar_context}"

        # --- 4. Final Answer Generation using Synthesized Context ---
        # The synthesized_context variable now contains either the LLM synthesis
        # or the limited combined context from the fallback.
        logger.debug(f"Using synthesized context for final answer generation:\n{synthesized_context[:500]}...")
        formatted_history = []
        if chat_history:
            for msg in chat_history:
                role = "user" if msg.get("role") == "user" else "assistant"
                formatted_history.append({"role": role, "content": msg.get("content", "")})

        final_system_prompt = f"""You are Jarvis, an AI assistant.\n        You are chatting with {user.display_name or user.email}.\n\n        Your task is to answer the user's question based *only* on the information presented in the 'Synthesized Context' below.\n        Present the relevant findings *as detailed in the context* to directly address the user's query. Structure the information clearly, mirroring the detail level of the context.\n        If the context indicates no relevant information was found, state that politely.\n        Do not add information not present in the synthesized context.\n\n        Instructions for your presentation:\n        - Include all relevant specific details found in the context (e.g., names, roles, dates, document titles, specific examples, meeting details like time/location/attendees).\n        - When stating quantities or counts, always use digits (e.g., '3').\n        - Format your entire response using Markdown, using lists or bullet points where appropriate for clarity.\n\n        Synthesized Context:\n        {synthesized_context}\n        """
        final_messages = [ {"role": "system", "content": final_system_prompt} ]
        final_messages.extend(formatted_history)
        final_messages.append({"role": "user", "content": message})

        logger.debug(f"Sending final prompt to {chat_model}...")
        final_response_obj = await user_client.chat.completions.create(
            model=chat_model,
            messages=final_messages,
            temperature=settings.OPENAI_TEMPERATURE
        )
        final_response = final_response_obj.choices[0].message.content
        logger.debug(f"RAG: Received final response from {chat_model}.")
        return final_response

    # Add except block for the outer try (line 267)
    except HTTPException as http_exc:
        logger.error(f"HTTP Exception during RAG: {http_exc.detail}", exc_info=True) # Log stack trace for HTTP exceptions too
        raise http_exc
    except Exception as e:
        logger.error(f"Error generating RAG response for user {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating the response." # Keep detail generic for security
        )

# --- Helper function for cosine similarity ---
import numpy as np

def cos_sim(a, b):
    # Ensure embeddings are valid lists/tuples of numbers
    if not isinstance(a, (list, tuple, np.ndarray)) or not isinstance(b, (list, tuple, np.ndarray)):
        logger.warning(f"Invalid input types for cosine similarity: {type(a)}, {type(b)}")
        return 0.0 # Or raise an error?
        
    # Check if elements are numeric (simple check)
    if not all(isinstance(x, (int, float)) for x in a) or not all(isinstance(x, (int, float)) for x in b):
        logger.warning("Non-numeric elements found in embeddings for cosine similarity.")
        return 0.0
        
    # Convert to numpy arrays
    a = np.array(a)
    b = np.array(b)
    
    # Check for zero vectors or dimension mismatch
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0 or a.shape != b.shape:
        logger.warning("Invalid vectors for cosine similarity (zero vector or shape mismatch).")
        return 0.0
        
    # Calculate cosine similarity
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return similarity
# --- End Helper --- 

# --- START: ADVANCED RAG FOR RATE CARDS --- 
async def get_rate_card_response_advanced(
    message: str,
    user: User,
    db: Session
) -> str:
    """Advanced RAG pipeline specifically for rate card queries."""
    
    logger.info(f"Initiating ADVANCED rate card query for user {user.email}: '{message}'")
    
    try:
        # 1. User API Key & Client Setup (same as standard RAG)
        user_openai_key = api_key_crud.get_decrypted_api_key(db, user.email, "openai")
        if not user_openai_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OpenAI API key required.")
        user_client = AsyncOpenAI(api_key=user_openai_key, timeout=30.0)
        chat_model = settings.OPENAI_MODEL_NAME
        
        # 2. Query Analysis & Feature Extraction (Tailored for Rate Cards)
        logger.debug("RateCardRAG: Analyzing query for key features...")
        analysis_prompt = (
            f"Analyze the following rate card query: '{message}'. "
            "Extract key features like role, experience level (e.g., junior, mid, senior, principal), specific skills mentioned, "
            "location/region (if any), and requested dollar amount (if any). "
            "Return a JSON object with keys: 'role', 'experience', 'skills' (list), 'location', 'amount' (integer). "
            "If a feature is not mentioned, use null or an empty list."
        )
        analysis_response = await user_client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": "You are a query analyzer specializing in rate card requests."},
                {"role": "user", "content": analysis_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        query_features = json.loads(analysis_response.choices[0].message.content)
        logger.debug(f"RateCardRAG: Extracted query features: {query_features}")
        
        # 3. Construct Multi-Vector Retrieval Queries
        retrieval_queries = []
        # Base query from features
        base_query_parts = [query_features.get(k) for k in ['role', 'experience', 'location'] if query_features.get(k)]
        if query_features.get('skills'):
            base_query_parts.extend(query_features['skills'])
        base_query = " ".join(base_query_parts) if base_query_parts else message # Fallback to original message
        retrieval_queries.append(base_query)
        logger.debug(f"RateCardRAG: Base retrieval query: {base_query}")
        
        # Additional queries (e.g., focusing only on role and experience)
        if query_features.get('role') and query_features.get('experience'):
            role_exp_query = f"{query_features['role']} {query_features['experience']}"
            retrieval_queries.append(role_exp_query)
            logger.debug(f"RateCardRAG: Role/Experience query: {role_exp_query}")
        # Consider adding queries focusing only on skills if present
        if query_features.get('skills'):
            skills_query = " ".join(query_features['skills'])
            retrieval_queries.append(skills_query)
            logger.debug(f"RateCardRAG: Skills query: {skills_query}")
            
        # Deduplicate retrieval queries
        retrieval_queries = list(set(retrieval_queries))
        logger.debug(f"RateCardRAG: Final unique retrieval queries: {retrieval_queries}")

        # 4. Generate Embeddings (potentially HyDE for each query)
        query_vectors = []
        hyde_docs = {}
        for q in retrieval_queries:
            # Optional: Generate HyDE doc for each retrieval query
            hyde_doc = q # Default if HyDE fails
            try:
                hyde_msgs = [
                    {"role": "system", "content": "Generate a concise, factual hypothetical rate card document answering the query."}, 
                    {"role": "user", "content": q}
                ]
                hyde_resp = await user_client.chat.completions.create(model=chat_model, messages=hyde_msgs, temperature=0.0)
                gen_doc = hyde_resp.choices[0].message.content.strip()
                if gen_doc: hyde_doc = gen_doc
            except Exception: pass # Ignore HyDE failure for individual queries
            hyde_docs[q] = hyde_doc
            
            # Create embedding using the HyDE document (or original query if HyDE failed)
            embedding = await create_retrieval_embedding(hyde_doc)
            query_vectors.append(embedding)
            logger.debug(f"RateCardRAG: Generated embedding for query: '{q}' (using HyDE: {hyde_doc[:50]}...)")

        # 5. Perform Multi-Vector Search in Milvus
        k_per_query = int(getattr(settings, 'RATE_CARD_RESULTS_PER_QUERY', 3)) # Retrieve fewer per query initially
        all_search_results = [] 
        
        # Build filter based on extracted amount
        # search_filter = None
        # requested_amount = query_features.get('amount')
        # if requested_amount is not None and isinstance(requested_amount, int):
        #     # Assuming rate is stored in metadata_json.rate_card_amount
        #     search_filter = f"metadata_json['rate_card_amount'] >= {requested_amount}"
        #     logger.debug(f"RateCardRAG: Applying search filter: {search_filter}")
        # else:
        #     logger.debug("RateCardRAG: No amount filter applied.")
        search_filter = None # TEMPORARILY DISABLED filter

        for i, vector in enumerate(query_vectors):
            logger.debug(f"RateCardRAG: Searching with vector {i+1} for query: '{retrieval_queries[i]}'")
            # Determine target collection name (RAG collection)
            sanitized_email = user.email.replace('@', '_').replace('.', '_')
            target_collection_name = f"{sanitized_email}_knowledge_base_bm"
            results = await search_milvus_knowledge(
                collection_name=target_collection_name, # ADDED collection name
                query_embedding=vector, # Use correct argument name 'query_embedding'
                limit=k_per_query, 
                filter_expression=search_filter
            )
            all_search_results.extend(results) # Combine results from all queries
            logger.debug(f"RateCardRAG: Found {len(results)} results for vector {i+1}.")
            
        logger.info(f"RateCardRAG: Total raw results from multi-vector search: {len(all_search_results)}")

        # 6. Deduplicate and Re-rank Results
        unique_results = {res['id']: res for res in all_search_results} # Simple deduplication by ID
        ranked_results = list(unique_results.values())
        logger.info(f"RateCardRAG: Unique results after deduplication: {len(ranked_results)}")
        
        # Re-ranking based on relevance to the *original* user message
        if ranked_results:
            logger.debug("RateCardRAG: Re-ranking based on original query similarity...")
            original_query_embedding = await create_retrieval_embedding(message)
            
            # Calculate similarity between original query and each result's content/embedding
            for result in ranked_results:
                result_embedding = result.get('vector') # Assuming search_milvus_knowledge can return vectors
                # Use 'payload' key which holds the content, instead of 'metadata'
                result_text = json.dumps(result.get('payload', {})) # Use payload text
                
                if result_embedding:
                    # Option 1: Use pre-computed embedding from result if available
                    similarity = cos_sim(original_query_embedding, result_embedding)
                else:
                    # Option 2: Re-embed result text (less efficient but fallback)
                    logger.warning(f"RateCardRAG: Re-embedding result ID {result['id']} for re-ranking as vector not found.")
                    result_embedding_rerank = await create_retrieval_embedding(result_text)
                    similarity = cos_sim(original_query_embedding, result_embedding_rerank)
                
                # Assign similarity score for sorting (can combine with original distance if needed)
                result['rerank_score'] = similarity 
                logger.debug(f"RateCardRAG: Result ID {result['id']} rerank similarity: {similarity:.4f}")
            
            # Sort by the new rerank_score (higher is better)
            ranked_results.sort(key=lambda x: x.get('rerank_score', 0.0), reverse=True)
            logger.debug("RateCardRAG: Completed re-ranking.")
        
        # 7. Context Selection & Formatting (Select top N re-ranked results)
        final_context_limit = int(getattr(settings, 'RATE_CARD_FINAL_CONTEXT_LIMIT', 5))
        # Use 'payload' key which holds the content, instead of 'metadata'
        context = "\n\n---\n\n".join([f"Document ID: {res['id']}\nContent: {json.dumps(res['payload'])}" for res in ranked_results[:final_context_limit]])
        logger.debug(f"RateCardRAG: Formatted final context (top {len(ranked_results[:final_context_limit])}):\n{context[:500]}...")

        # 8. Generate Final Response using LLM
        system_prompt = (
            "You are Jarvis, an AI assistant specializing in providing rate card information. "
            f"You are chatting with {user.display_name or user.email}. "
            "Use the provided context containing relevant rate card entries to answer the user's query accurately. "
            "Directly quote rates and associated details (like role, experience, skills, location) from the context. "
            "If the context doesn't contain a precise match, state that clearly but offer the closest information available in the context. "
            "Do not make up rates or information not present in the context."
            "Structure your answer clearly, perhaps listing relevant entries found."
            f"\n\nContext:\n{context}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        logger.debug(f"RateCardRAG: Sending final prompt to {chat_model}...")
        response = await user_client.chat.completions.create(
            model=chat_model,
            messages=messages,
            temperature=0.0 # Very low temp for factual rate card response
        )
        final_response = response.choices[0].message.content
        logger.info("RateCardRAG: Generated final response.")
        return final_response

    except HTTPException as http_exc:
        raise http_exc # Re-raise specific errors
    except Exception as e:
        logger.error(f"Error during advanced rate card RAG for user {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your rate card request."
        )
# --- END: ADVANCED RAG FOR RATE CARDS --- 
