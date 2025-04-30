import json
import re  # For rate-card dollar filtering
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI, RateLimitError # Import RateLimitError
from sqlalchemy.orm import Session
import logging # Import logging
import asyncio  # For async operations
from datetime import datetime, timedelta, timezone # Added datetime imports
from zoneinfo import ZoneInfo # Added ZoneInfo import
import tiktoken # ADDED tiktoken import

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.models.user import User # Assuming User model is here
# Import RAG components - Updated for Milvus
from app.services.embedder import create_embedding, search_milvus_knowledge_hybrid, rerank_results, create_retrieval_embedding
# Keep the old dense search function imported in case it's used elsewhere or for future reference
from app.services.embedder import search_milvus_knowledge
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
from app.utils.security import decrypt_token, encrypt_token

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
    original_message: str = "",
    user_client: AsyncOpenAI = None # ADDED user_client parameter
) -> List[Dict[str, Any]]:
    """Queries the email_facts Iceberg table for a user using DuckDB and keywords, with LLM-extracted date filtering."""
    results = []
    # Keep initial check: if no keywords AND no message, skip.
    if not keywords and not original_message:
        logger.debug("No keywords provided and no message for date extraction, skipping DuckDB query.")
        return results

    # Ensure user_client is passed
    if not user_client:
        logger.error("DuckDB Query: User-specific OpenAI client (user_client) was not provided.")
        # Cannot proceed without the client for date extraction
        return results 

    try:
        catalog = await get_iceberg_catalog()
        if not catalog:
            return results

        full_table_name = f"{settings.ICEBERG_DEFAULT_NAMESPACE}.{settings.ICEBERG_EMAIL_FACTS_TABLE}"
        try:
            iceberg_table = catalog.load_table(full_table_name)
        except NoSuchTableError:
            logger.error(f"Iceberg table {full_table_name} not found.")
            return results

        con = duckdb.connect(database=':memory:', read_only=False)
        view_name = 'email_facts_view'
        iceberg_table.scan().to_duckdb(table_name=view_name, connection=con)

        # --- START: LLM-based Date Filtering Logic ---
        date_filter_sql = ""
        params = [user_email] # Start params list with user_email
        start_date_utc: Optional[datetime] = None
        end_date_utc: Optional[datetime] = None

        if original_message: # Only attempt date extraction if there's a message
            logger.debug(f"Attempting LLM date extraction from message: '{original_message}'")
            try:
                # Get current time in UTC as reference for LLM
                now_utc_iso = datetime.now(timezone.utc).isoformat()
                
                date_extraction_prompt = f"""Analyze the user's message to determine the intended date range for a search. The current UTC time is {now_utc_iso}.

User Message: "{original_message}"

Identify the start date and end date implied by the message. Consider relative terms like "yesterday", "last week", "last 2 weeks", "last 4 weeks", "this month", "last month", specific dates, etc. 

Respond ONLY with a JSON object containing two keys: "start_date_utc" and "end_date_utc". 
The date format MUST be ISO 8601 UTC (e.g., "YYYY-MM-DDTHH:MM:SSZ"). 
If no specific date range is implied, return null for both keys.

Example for "yesterday": {{"start_date_utc": "2024-08-11T00:00:00Z", "end_date_utc": "2024-08-11T23:59:59Z"}}
Example for "last 2 weeks" (assuming today is 2024-08-12T10:00:00Z): {{"start_date_utc": "2024-07-29T10:00:00Z", "end_date_utc": "2024-08-12T10:00:00Z"}}
Example for "show me emails": {{"start_date_utc": null, "end_date_utc": null}}

JSON Response:"""
                
                # Use the passed user_client
                response = await user_client.chat.completions.create(
                    # Use a fast, cheaper model if possible for this structured task
                    model=getattr(settings, 'DATE_EXTRACTION_MODEL', 'gpt-4.1-mini'), 
                    messages=[
                        {"role": "system", "content": "You are an expert date range extractor. Respond only with the specified JSON format."},
                        {"role": "user", "content": date_extraction_prompt}
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                
                date_result_json = response.choices[0].message.content
                logger.debug(f"LLM Date Extraction Response: {date_result_json}")
                
                date_result = json.loads(date_result_json)
                raw_start = date_result.get("start_date_utc")
                raw_end = date_result.get("end_date_utc")

                # Attempt to parse the dates
                if raw_start:
                    try:
                        # Ensure timezone info is handled correctly (Z means UTC)
                        start_date_utc = datetime.fromisoformat(raw_start.replace('Z', '+00:00'))
                        # Convert aware datetime to naive UTC for DuckDB compatibility if needed, or ensure DuckDB handles aware
                        # start_date_utc = start_date_utc.astimezone(timezone.utc).replace(tzinfo=None) 
                    except ValueError:
                        logger.warning(f"LLM returned invalid start date format: {raw_start}. Ignoring date filter.")
                if raw_end:
                    try:
                        end_date_utc = datetime.fromisoformat(raw_end.replace('Z', '+00:00'))
                        # end_date_utc = end_date_utc.astimezone(timezone.utc).replace(tzinfo=None)
                    except ValueError:
                        logger.warning(f"LLM returned invalid end date format: {raw_end}. Ignoring date filter.")
                        start_date_utc = None # Invalidate start date too if end date is bad

                if start_date_utc and end_date_utc:
                     # Optional: Basic validation (start <= end)
                    if start_date_utc > end_date_utc:
                         logger.warning(f"LLM returned start date after end date ({start_date_utc} > {end_date_utc}). Ignoring date filter.")
                    else:
                        date_filter_sql = " AND received_datetime_utc >= ? AND received_datetime_utc <= ?"
                        # Insert date params *after* user_email but *before* keywords
                        params.insert(1, start_date_utc) 
                        params.insert(2, end_date_utc)
                        logger.info(f"Applying LLM-extracted date filter: >= {start_date_utc.isoformat()} AND <= {end_date_utc.isoformat()} UTC")
                else:
                     logger.info("LLM did not extract a valid date range from the message.")

            except Exception as llm_date_err:
                logger.error(f"Error during LLM date extraction: {llm_date_err}", exc_info=True)
                # Proceed without date filter on error
                date_filter_sql = ""
                params = [user_email] # Reset params
        # --- END: LLM-based Date Filtering Logic ---

        # Build WHERE clause for keywords (simple LIKE matching)
        keyword_params = []
        keyword_filter = ""
        if keywords:
            like_clauses = []
            for kw in keywords:
                like_clauses.append(f"(subject LIKE ? OR body_text LIKE ? OR sender LIKE ? OR sender_name LIKE ? OR generated_tags LIKE ?)")
                # Escape % and _ within the keyword itself before adding wildcards
                safe_kw = kw.replace('%', '\\%').replace('_', '\\_')
                keyword_params.extend([f'%{safe_kw}%', f'%{safe_kw}%', f'%{safe_kw}%', f'%{safe_kw}%', f'%{safe_kw}%'])
            keyword_filter = " OR ".join(like_clauses)
            params.extend(keyword_params) # Add keyword params to the list
        else:
            # If no keywords AND date filter exists, we need a valid filter condition
            if date_filter_sql:
                 # No keyword filter needed, date filter is sufficient if present
                 pass # keyword_filter remains ""
            else: # No keywords and no date filter - this case should be handled by initial check/original_message presence
                 # Original logic check: if not keywords and not original_message, return [] early.
                 # If original_message WAS present but date extraction failed, AND no keywords were given,
                 # this path might be hit. Should we proceed with just owner_email? Let's log.
                 logger.warning("Querying DuckDB potentially without keywords OR date filter. Review logic if this occurs unexpectedly.")
                 # Reverting the forced return for now, let it proceed if date extraction failed but message existed.
                 # con.close()
                 # return []

        # Construct the full SQL query
        # Ensure AND is added only if both date and keyword filters exist
        # ORIGINAL SQL Logic restored: Check if keyword_filter has content
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


# --- Helper function for token counting ---
_token_encoders = {}

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Estimates the number of tokens for a given text and model."""
    if model not in _token_encoders:
        try:
            _token_encoders[model] = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Model {model} not found in tiktoken. Using cl100k_base encoding.")
            _token_encoders[model] = tiktoken.get_encoding("cl100k_base")
    
    if not isinstance(text, str):
        logger.warning(f"Attempted to count tokens for non-string type: {type(text)}. Returning 0.")
        return 0
        
    try:
        encoder = _token_encoders[model]
        return len(encoder.encode(text))
    except Exception as e:
        logger.error(f"Error encoding text for token count: {e}", exc_info=True)
        return 0 # Return 0 on error

def truncate_text_by_tokens(text: str, model: str, max_tokens: int) -> str:
    """Truncates text to a maximum number of tokens."""
    if not isinstance(text, str):
        logger.warning(f"Attempted to truncate non-string type: {type(text)}. Returning empty string.")
        return ""
        
    if model not in _token_encoders:
        try:
            _token_encoders[model] = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Model {model} not found for truncation. Using cl100k_base encoding.")
            _token_encoders[model] = tiktoken.get_encoding("cl100k_base")
            
    try:
        encoder = _token_encoders[model]
        tokens = encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens]
        # Use decode with error handling
        return encoder.decode(truncated_tokens, errors='replace') + "...[TRUNCATED BY TOKEN LIMIT]"
    except Exception as e:
        logger.error(f"Error truncating text by tokens: {e}", exc_info=True)
        # Fallback to character truncation if tokenization fails
        fallback_chars = max_tokens * 3 # Rough estimate
        return text[:fallback_chars] + "...[TRUNCATED BY CHAR LIMIT DUE TO ERROR]"
# --- End Helper ---

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
    try: # Outer try block
        # Determine model and user-specific client
        chat_model = model_id or settings.OPENAI_MODEL_NAME
        # Determine provider based on model name
        if chat_model.lower().startswith("deepseek"):
            provider = "deepseek"
        # Add other providers here if needed
        # elif chat_model.lower().startswith("another-provider"):
        #     provider = "another-provider"
        else:
            provider = "openai" # Default to openai if not specified

        logger.debug(f"Using LLM model: {chat_model} for user {user.email} via provider {provider}")

        # --- MODIFIED: Fetch APIKeyDB object and decrypt key (replaces get_decrypted_credentials) ---
        # Fetch the stored API key record
        db_api_key = api_key_crud.get_api_key(db, user.email, provider)
        if not db_api_key:
            logger.warning(f"User {user.email} missing active {provider} key.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider.capitalize()} API key required.")
        # Decrypt the key
        user_api_key = decrypt_token(db_api_key.encrypted_key)
        if not user_api_key:
            logger.error(f"Failed to decrypt stored {provider} key for user {user.email}. Key ID: {db_api_key.id}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not decrypt stored {provider.capitalize()} API key.")
        # Retrieve custom base URL if any
        user_base_url = db_api_key.model_base_url
        # --- End Modification ---

        # --- MODIFIED: Conditionally set base_url for the client (logic remains same) --- 
        client_kwargs = {
            "api_key": user_api_key,
            "timeout": settings.OPENAI_TIMEOUT_SECONDS or 30.0
        }
        if user_base_url:
            logger.info(f"Using custom base URL for {provider} for user {user.email}: {user_base_url}")
            client_kwargs["base_url"] = user_base_url
        else:
            logger.info(f"Using default base URL for {provider} for user {user.email}")
            # No base_url kwarg passed, library uses default

        user_client = AsyncOpenAI(**client_kwargs)
        # --- End Modification ---

        # --- START: Intent Detection (Email vs. General KB) ---
        async def _detect_query_intent(user_query: str, client: AsyncOpenAI) -> str:
            logger.debug(f"Detecting intent for query: '{user_query}'")
            # Use a cheaper/faster model for classification
            # MODIFICATION START: Select model based on provider
            intent_model = chat_model # Default to the main chat model
            if provider == "openai":
                 # Use specific cheaper model for OpenAI if defined
                 intent_model = getattr(settings, 'INTENT_DETECTION_MODEL', 'gpt-4.1-mini') 
            # MODIFICATION END
            
            # MODIFICATION START: Adjust prompt for non-JSON mode if needed
            prompt_instruction = "Respond ONLY with the chosen category ('email_focused' or 'general_or_mixed')."
            system_content = f"You are an intent classifier. {prompt_instruction}"
            # Keep original prompt structure
            prompt = (
                f"Analyze the user's query and classify its primary information need. Choose ONE category:\\n"
                f"- 'email_focused': The query asks for specific information likely found only in recent emails (e.g., summaries of recent emails, specific email content, counts/lists based on recent communications like 'who left last week', 'emails from X yesterday').\\n"
                f"- 'general_or_mixed': The query asks for general knowledge, policies, procedures, or information that might exist in documents OR emails, or requires combining both (e.g., 'what is the policy on X?', 'explain concept Y', 'rate card for role Z', 'project status update').\\n\\n"
                f"User Query: \\\"{user_query}\\\"\\n\\n"
                f"{prompt_instruction}"
            )
            # MODIFICATION END

            try:
                 # MODIFICATION START: Conditional response_format
                 completion_args = {
                     "model": intent_model,
                     "messages": [
                         {"role": "system", "content": system_content},
                         {"role": "user", "content": prompt}
                     ],
                     "temperature": 0.0,
                     "max_tokens": 15 # Slightly increase for potential variability
                 }
                 # Only add response_format if provider is OpenAI (assuming DeepSeek might not support it)
                 if provider == "openai":
                      # Check if the selected intent_model for OpenAI supports JSON mode
                      # We'll assume gpt-4o-mini does, but ideally, this needs model-specific checks
                      logger.debug(f"Requesting JSON format for intent detection with OpenAI model {intent_model}")
                      # completion_args["response_format"] = {"type": "json_object"} # Temporarily disabled JSON for testing simpler text parsing first
                      pass # Keep parsing text response for now even for OpenAI

                 # MODIFICATION END
                 
                 # Always expect text response for now
                 response = await client.chat.completions.create(**completion_args)
                 
                 # Parse the text response directly
                 detected_intent = response.choices[0].message.content.strip().lower()
                 # Clean up potential extra text or quotes
                 if 'email_focused' in detected_intent:
                     detected_intent = 'email_focused'
                 elif 'general_or_mixed' in detected_intent:
                     detected_intent = 'general_or_mixed'
                 else: # Handle unexpected responses
                    logger.warning(f"Intent detection returned unexpected text: '{response.choices[0].message.content}'. Attempting basic extraction.")
                    # Simple fallback check
                    if 'email' in detected_intent: detected_intent = 'email_focused'
                    else: detected_intent = 'general_or_mixed' # Default if still unclear

                 logger.info(f"Detected query intent: {detected_intent}")
                 # Check remains the same
                 if detected_intent in ['email_focused', 'general_or_mixed']:
                     return detected_intent
                 else:
                     # This path should ideally not be hit with the cleanup above, but kept as safeguard
                     logger.warning(f"Intent detection failed after cleanup: '{detected_intent}'. Defaulting to 'general_or_mixed'.")
                     return "general_or_mixed"
                 
            except Exception as intent_err:
                logger.error(f"Intent detection LLM call failed: {intent_err}", exc_info=True)
                logger.warning("Defaulting to 'general_or_mixed' due to intent detection error.")
                return "general_or_mixed"
        # --- END Intent Detection ---

        # Detect intent before starting retrievals
        query_intent = await _detect_query_intent(message, user_client)
        
        # --- START: Simple Intent Detection for Calendar ---
        calendar_keywords = ["meeting", "calendar", "event", "appointment", "schedule", "upcoming"]
        is_calendar_query = any(keyword in message.lower() for keyword in calendar_keywords)
        logger.debug(f"Is calendar query detected: {is_calendar_query}")
        # --- END: Simple Intent Detection ---

        # --- Keyword extraction logic (assumed correct indentation) ---
        # 1. Extract Keywords for Email Search
        # Basic word extraction
        basic_keywords = [word for word in re.findall(r'\b\w{3,}\b', message.lower()) 
                          if word not in ['the', 'a', 'is', 'and', 'or', 'find', 'search', 'email', 'emails', 'how', 'many', 'last', 'weeks']]
        # Extract email addresses specifically
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        extracted_emails = re.findall(email_pattern, message)
        # Combine and deduplicate
        base_keywords_for_email = list(set(basic_keywords + extracted_emails))
        # Remove empty strings just in case
        base_keywords_for_email = [kw for kw in base_keywords_for_email if kw]

        # 1b. Expand Keywords using LLM
        async def _get_expanded_keywords(user_query: str, client: AsyncOpenAI, base_keywords: List[str]) -> List[str]:
            logger.debug(f"Attempting LLM keyword expansion for query: '{user_query}'")
            # Use a cheaper/faster model
            # MODIFICATION START: Select model based on provider
            expansion_model = chat_model # Default to the main chat model
            if provider == "openai":
                # Use specific cheaper model for OpenAI if defined
                expansion_model = getattr(settings, 'KEYWORD_EXPANSION_MODEL', 'gpt-4.1-mini')
            # MODIFICATION END
            
            # Create a context string from base keywords if available
            base_kw_context = ", ".join(base_keywords)
            if base_kw_context:
                base_kw_context = f"Initial keywords extracted were: {base_kw_context}. "
            else:
                base_kw_context = ""

            prompt = f"""Analyze the user's query and generate a list of related keywords and synonyms that are likely to appear in relevant emails. Focus on variations and related concepts.
User Query: '{user_query}'
+{base_kw_context}
Consider terms related to the core intent. For example, if the query is about departures, include terms like resignation, leaving, offboarding, contract end, non-renewal, replacement, terminated, last day, etc.

Respond ONLY with a comma-separated list of 5-10 relevant keywords/phrases. Do not include the original query keywords unless they are highly relevant variations.

Comma-separated keywords:"""
            try:
                response = await client.chat.completions.create(
                    model=expansion_model,
                    messages=[
                        {"role": "system", "content": "You are a keyword generator for email search. Respond ONLY with a comma-separated list."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2, # Allow a little creativity
                    max_tokens=100 
                )
                expanded_keywords_str = response.choices[0].message.content.strip()
                # Split, strip whitespace from each, and filter empty strings
                expanded_list = [kw.strip() for kw in expanded_keywords_str.split(',') if kw.strip()]
                logger.info(f"LLM Expansion generated {len(expanded_list)} keywords: {expanded_list}")
                return expanded_list
            except Exception as expansion_err:
                logger.error(f"LLM keyword expansion failed: {expansion_err}", exc_info=True)
                return [] # Return empty list on error

        # Combine base + expanded, ensure uniqueness, case-insensitivity handled by query logic later
        final_keywords_for_email = list(set(base_keywords_for_email + await _get_expanded_keywords(message, user_client, base_keywords_for_email)))
        logger.debug(f"Final keywords for email search (base + expanded): {final_keywords_for_email}")
        # --- End Keyword Extraction ---

        # --- Context Retrieval Functions (_get_milvus_context, _get_email_context, _get_calendar_context)
        # Assume these inner async functions are defined correctly here with proper indentation
        # (Using the previously modified _get_milvus_context that returns a list)
        async def _get_milvus_context(max_items: int, max_chunk_chars: int) -> List[Dict[str, Any]]:
            logger.debug(f"Starting Milvus context retrieval (Returning top {max_items} raw results)...")
            try:
                retrieval_query = message
                refined = None
                # MODIFICATION START: Skip refinement if provider is not openai or if specifically disabled
                # Also skip for rate card explicitly
                should_refine_query = (provider == "openai") and getattr(settings, 'ENABLE_QUERY_REFINEMENT', True) 
                
                if should_refine_query and 'rate card' not in message.lower():
                # END MODIFICATION
                    try:
                        # MODIFICATION: Ensure prompt asks for JSON within text if not using JSON mode (though we skip for deepseek now)
                        refine_prompt = (
                            f"Question: {message}\\n"
                            f"Extract the target table/section and the entity from the user question. " 
                            f"Respond ONLY with a JSON object string containing keys 'table' and 'role', like this: "
                            f"{{ \"table\":\"...\", \"role\":\"...\"}}. If not applicable return the string 'null' exactly."
                        )
                        refine_msgs = [
                            {"role": "system","content": ("You are a query refiner. Extract the target table/section and the entity. Respond ONLY with the JSON string or 'null'.")},
                            {"role": "user","content": refine_prompt }
                        ]
                        
                        # MODIFICATION START: Only use response_format for OpenAI
                        refine_args = {
                            "model": chat_model,
                            "messages": refine_msgs,
                            "temperature": 0.0
                        }
                        if provider == "openai": # Only OpenAI gets JSON mode for now
                            refine_args["response_format"] = {"type": "json_object"}
                        
                        resp_refine = await user_client.chat.completions.create(**refine_args)
                        # END MODIFICATION
                        
                        content = resp_refine.choices[0].message.content
                        # MODIFICATION START: Handle parsing based on whether JSON was requested
                        if provider == "openai": # Assume direct JSON object
                            if content and content.strip().lower() != 'null':
                                refined = json.loads(content) # Should already be JSON object if format worked
                            else:
                                refined = None
                        else: # Parse text response assuming it contains JSON string or 'null'
                            content_cleaned = content.strip()
                            if content_cleaned.lower() == 'null':
                                refined = None
                            else:
                                try:
                                    # Extract JSON part if wrapped in ```json ... ``` or similar
                                    if content_cleaned.startswith("```json"):
                                        content_cleaned = content_cleaned.split("\n", 1)[1].rsplit("\n```", 1)[0]
                                    refined = json.loads(content_cleaned)
                                except json.JSONDecodeError:
                                    logger.warning(f"Query refinement for {provider} returned non-JSON text: '{content}'. Using original query.")
                                    refined = None
                        # END MODIFICATION

                        # Original logic using refined result
                        if refined and (refined.get('table') or refined.get('role')):
                            parts = []
                            if refined.get('table'): parts.append(refined['table'])
                            if refined.get('role'): parts.append(refined['role'])
                            if parts: 
                                retrieval_query = ' '.join(parts)
                                logger.debug(f"RAG: Refined retrieval query for Milvus: {retrieval_query}")
                        else: 
                            logger.debug("Query refinement deemed not applicable or failed.")
                            
                    except Exception as refine_e: 
                        logger.warning(f"Query refinement failed, using original message: {refine_e}", exc_info=True)
                # MODIFICATION START: Log reason for skipping
                elif 'rate card' in message.lower():
                     logger.debug("RAG: Skipping query refinement for rate card query.")
                else: # Skipped because provider != openai or setting disabled
                    logger.debug(f"RAG: Skipping query refinement (Provider: {provider}, Enabled: {getattr(settings, 'ENABLE_QUERY_REFINEMENT', True)}).")
                # END MODIFICATION
                
                # HyDE generation logic follows...

                hyde_document = retrieval_query
                if 'rate card' not in message.lower() and getattr(settings, 'ENABLE_HYDE', True):
                    try:
                        hyde_msgs = [{"role": "system", "content": ("You are an assistant that generates a concise, factual hypothetical document that directly answers the user's question. Output only the document content, no extra text.")},{"role": "user", "content": f"Generate a hypothetical document answering: {message}"}]
                        hyde_resp = await user_client.chat.completions.create(model=chat_model, messages=hyde_msgs, temperature=0.0)
                        generated_doc = hyde_resp.choices[0].message.content.strip()
                        if generated_doc: hyde_document = generated_doc; logger.debug(f"RAG: Generated HyDE document for Milvus: {hyde_document[:50]}...")
                        else: logger.warning("HyDE generation returned empty content, using retrieval_query for Milvus embedding.")
                    except Exception as hyde_e: logger.warning(f"HyDE generation failed, using retrieval_query for Milvus embedding: {hyde_e}", exc_info=True)
                elif 'rate card' in message.lower(): logger.debug("RAG: Skipping HyDE generation for rate card query.")
                hyde_embedding = await create_retrieval_embedding(hyde_document, field='dense')
                logger.debug(f"RAG: Generated HyDE embedding for Milvus retrieval.")
                search_filter = None
                k_dense = int(getattr(settings, 'RAG_DENSE_RESULTS', max_items))
                k_sparse = int(getattr(settings, 'RAG_SPARSE_RESULTS', max_items))
                sanitized_email = user.email.replace('@', '_').replace('.', '_')
                target_collection_name = f"{sanitized_email}_knowledge_base_bm"
                logger.info(f"RAG: Initial retrieval from: {target_collection_name} with limit {max_items}")
                dense_search_result_list = await search_milvus_knowledge(collection_name=target_collection_name, query_texts=[hyde_document], limit=k_dense, filter_expr=search_filter)
                dense_search_results = dense_search_result_list[0] if dense_search_result_list else []
                if not dense_search_results: logger.warning(f"RAG: Initial Milvus dense search returned no results for collection '{target_collection_name}'."); return []
                logger.info(f"RAG: Initial dense search found {len(dense_search_results)} results. Reranking...")
                reranked_results = await rerank_results(query=message, results=dense_search_results)
                logger.debug(f"RAG: Reranked {len(reranked_results)} Milvus results.")
                results_to_return = reranked_results[:max_items]
                logger.info(f"RAG: Returning top {len(results_to_return)} reranked Milvus documents as context.")
                return results_to_return
            except Exception as e_milvus: logger.error(f"Failed during Milvus context retrieval: {e_milvus}", exc_info=True); return []

        async def _get_email_context(max_items: int, max_chunk_chars: int, user_client: AsyncOpenAI):
            logger.debug(f"Starting Email context retrieval (max_items={max_items}, max_chars={max_chunk_chars})...")
            def _truncate_text(text: str, max_len: int) -> str:
                if len(text) > max_len: return text[:max_len] + "... [TRUNCATED]"; return text
            try:
                initial_email_results = await query_iceberg_emails_duckdb(user_email=user.email,keywords=final_keywords_for_email, limit=max_items, original_message=message,user_client=user_client)
                if not initial_email_results: logger.info("Email Retrieval: No initial results from DuckDB."); return "No relevant emails found."
                logger.info(f"Email Retrieval: Initially retrieved {len(initial_email_results)} emails from DuckDB.")
                email_context = "\n\n---\n\n".join([f"Email ID: {email.get('message_id')}\nReceived: {email.get('received_datetime_utc')}\nSender: {email.get('sender')}\nSubject: {email.get('subject')}\nTags: {email.get('generated_tags')}\nSnippet: {_truncate_text(email.get('body_snippet', ''), max_chunk_chars)}" for email in initial_email_results ])
                logger.debug(f"Email Retrieval: Final formatted context length: {len(email_context)} chars from {len(initial_email_results)} emails.")
                return email_context
            except Exception as e_email: logger.error(f"Failed to retrieve Email context: {e_email}", exc_info=True); return "Error retrieving email context."

        async def _get_calendar_context():
            if not is_calendar_query: return "Calendar query not detected."
            if not ms_token: logger.warning("MS token not available, cannot fetch calendar events."); return "Error: Cannot fetch calendar events (auth token missing)."
            logger.debug("Starting Calendar context retrieval...")
            try:
                outlook_service = OutlookService(access_token=ms_token)
                events = await outlook_service.get_upcoming_events()
                if not events: return "No upcoming calendar events found in the next 7 days."
                calendar_context = "\n\n---\n\n".join([f"Event Subject: {event.get('subject')}\nStart: {event.get('start_time')} ({event.get('start_timezone')})\nEnd: {event.get('end_time')} ({event.get('end_timezone')})\nLocation: {event.get('location')}\nAttendees: {', '.join(event.get('attendees', []))}\nPreview: {event.get('preview', '')[:100]}..." for event in events])
                return calendar_context
            except Exception as e_cal: logger.error(f"Failed to retrieve Calendar context: {e_cal}", exc_info=True); return "Error retrieving calendar context."
        # --- End Context Retrieval Functions ---

        # Read limits from settings
        MAX_MILVUS_CONTEXT_ITEMS = int(getattr(settings, 'RAG_LLM_MILVUS_LIMIT', 20))
        MAX_EMAIL_CONTEXT_ITEMS = int(getattr(settings, 'RAG_LLM_EMAIL_LIMIT', 100))
        MAX_CALENDAR_CONTEXT_ITEMS = int(getattr(settings, 'RAG_LLM_CALENDAR_LIMIT', 20))
        MAX_CHUNK_CHARS = int(getattr(settings, 'RAG_CHUNK_MAX_CHARS', 5000))
        logger.debug(f"Using LLM context limits - Milvus: {MAX_MILVUS_CONTEXT_ITEMS}, Email: {MAX_EMAIL_CONTEXT_ITEMS}, Calendar: {MAX_CALENDAR_CONTEXT_ITEMS}")
        logger.debug(f"Using max chars per chunk: {MAX_CHUNK_CHARS}")

        # --- START: Conditional Context Retrieval (Refactored) ---
        retrieved_milvus_docs: List[Dict[str, Any]] = []
        retrieved_email_context: str = ""
        retrieved_calendar_context: str = ""

        if query_intent == 'email_focused':
            logger.info("Query intent is email_focused, running email and calendar retrieval first.")
            retrieved_email_context, retrieved_calendar_context = await asyncio.gather( _get_email_context(max_items=MAX_EMAIL_CONTEXT_ITEMS, max_chunk_chars=MAX_CHUNK_CHARS, user_client=user_client), _get_calendar_context())
            logger.info("Skipping knowledge base retrieval due to email-focused query intent.")
        else: # 'general_or_mixed' intent
            logger.info("Query intent is general_or_mixed, retrieving from knowledge base first.")
            retrieved_milvus_docs, retrieved_calendar_context = await asyncio.gather(_get_milvus_context(max_items=MAX_MILVUS_CONTEXT_ITEMS, max_chunk_chars=MAX_CHUNK_CHARS), _get_calendar_context())
            if not retrieved_milvus_docs:
                logger.info("Milvus KB context is empty or errored, proceeding with email retrieval.")
                retrieved_email_context = await _get_email_context(max_items=MAX_EMAIL_CONTEXT_ITEMS, max_chunk_chars=MAX_CHUNK_CHARS, user_client=user_client)
            else:
                logger.info(f"Milvus KB retrieval successful ({len(retrieved_milvus_docs)} docs found). Skipping email retrieval for now.")
                retrieved_email_context = "Email search skipped as knowledge base context was retrieved."
        # --- END: Conditional Context Retrieval (Refactored) ---
        
        # --- Token Budgeting Setup ---
        # Use the actual model name determined earlier
        tokenizer_model = chat_model 
        # Define max context tokens, leaving room for response generation (e.g., ~4k)
        MODEL_MAX_TOKENS = getattr(settings, 'MODEL_MAX_TOKENS', 128000) # Example for gpt-4-turbo
        RESPONSE_BUFFER_TOKENS = getattr(settings, 'RESPONSE_BUFFER_TOKENS', 4096)
        MAX_CONTEXT_TOKENS = MODEL_MAX_TOKENS - RESPONSE_BUFFER_TOKENS
        logger.debug(f"Token budgeting: Model={tokenizer_model}, Max Context Tokens={MAX_CONTEXT_TOKENS}")

        # Estimate tokens for base prompt components (system, history, user message)
        # Build temporary messages list *without* the large context for estimation
        temp_system_prompt_structure = f"""You are Jarvis, an AI assistant.
        You are chatting with {user.display_name or user.email}.
        Your task is to answer the user's question based *only* on the information presented in the context sections below...
        **Crucially, when you use information from a specific Knowledge Base Document, you MUST cite...**
        Do not add information not present in the context...
        Context Provided:
        <CONTEXT_PLACEHOLDER>
        """ # Simplified structure for estimation
        base_tokens = count_tokens(temp_system_prompt_structure, tokenizer_model)
        base_tokens += count_tokens(message, tokenizer_model) 
        for msg in chat_history:
            base_tokens += count_tokens(msg.get("content", ""), tokenizer_model)
        
        remaining_token_budget = MAX_CONTEXT_TOKENS - base_tokens
        logger.debug(f"Token budgeting: Base prompt tokens={base_tokens}, Remaining budget for context={remaining_token_budget}")

        if remaining_token_budget <= 0:
            logger.warning("Token budget exceeded by base prompt and history alone. Cannot add context.")
            # Handle this case - maybe return an error or a response without context?
            raise HTTPException(status_code=400, detail="Query and history are too long to process.")
        # --- End Token Budgeting Setup ---

        # --- START: Construct Final Context Directly (with Token Budgeting) ---
        final_context_parts = []

        # 1. Format Milvus Documents
        if retrieved_milvus_docs:
            milvus_context_str = "<Knowledge Base Documents>\n"
            def _truncate_context_text(text: str, max_len: int) -> str: # Define helper here
                return text[:max_len] + "...[TRUNCATED]" if len(text) > max_len else text
                
            # Estimate tokens used by boilerplate text for each doc
            doc_boilerplate_template = "--- Document {idx} (Source: {src}, ID: {id}, Score: {score:.4f}) ---\n{content}\n--- End Document {idx} ---\n"
            estimated_boilerplate_tokens_per_doc = count_tokens(doc_boilerplate_template.format(idx=1, src="a.pdf", id="x", score=1.0, content=""), tokenizer_model)

            for idx, doc in enumerate(retrieved_milvus_docs):
                doc_content = doc.get("content", "")
                doc_id = doc.get("id", "N/A")
                doc_score = doc.get("rerank_score", doc.get("score", "N/A")) 
                doc_metadata = doc.get("metadata") 
                source_filename = "Unknown Source"
                if isinstance(doc_metadata, dict): source_filename = doc_metadata.get('original_filename', 'Unknown Source')
                elif isinstance(doc_metadata, str):
                    try: meta_dict = json.loads(doc_metadata); source_filename = meta_dict.get('original_filename', 'Unknown Source')
                    except json.JSONDecodeError: source_filename = "Metadata Parse Error"
                truncated_content = _truncate_context_text(doc_content, MAX_CHUNK_CHARS) 
                
                # Token-based truncation for Milvus docs
                current_doc_tokens = count_tokens(doc_content, tokenizer_model)
                max_allowed_tokens_for_this_doc = max(0, remaining_token_budget - estimated_boilerplate_tokens_per_doc) # Ensure non-negative
                
                if current_doc_tokens > max_allowed_tokens_for_this_doc:
                    logger.warning(f"Truncating Milvus doc {doc_id} (Source: {source_filename}) from {current_doc_tokens} tokens to fit budget {max_allowed_tokens_for_this_doc}.")
                    truncated_content = truncate_text_by_tokens(doc_content, tokenizer_model, max_allowed_tokens_for_this_doc)
                else:
                    truncated_content = doc_content # Use original if it fits

                # Add the (potentially truncated) content to the context string
                milvus_context_str += (f"--- Document {idx+1} (Source: {source_filename}, ID: {doc_id}, Score: {doc_score:.4f}) ---\n"
                                     f"{truncated_content}\n"
                                     f"--- End Document {idx+1} ---\n")
                # Update remaining budget
                tokens_added = count_tokens(milvus_context_str.split("--- Document {idx+1}")[-1], tokenizer_model) # Count tokens for the added part
                remaining_token_budget -= tokens_added
                if remaining_token_budget <= 0:
                    logger.warning("Token budget exhausted while adding Milvus documents. Stopping context addition.")
                    break # Stop adding more docs if budget is gone

            milvus_context_str += "</Knowledge Base Documents>"
            final_context_parts.append(milvus_context_str)
        else:
             if query_intent == 'email_focused': final_context_parts.append("<Knowledge Base Documents>\nSearch skipped (email-focused query).\n</Knowledge Base Documents>")
             else: final_context_parts.append("<Knowledge Base Documents>\nNo relevant documents found in the knowledge base.\n</Knowledge Base Documents>")

        # 2. Format Email Context
        if retrieved_email_context and remaining_token_budget > 0:
            email_boilerplate_tokens = count_tokens("<User Email Context>\n\n</User Email Context>", tokenizer_model)
            allowed_email_tokens = max(0, remaining_token_budget - email_boilerplate_tokens)
            current_email_tokens = count_tokens(retrieved_email_context, tokenizer_model)
            
            if current_email_tokens > allowed_email_tokens:
                logger.warning(f"Truncating Email context from {current_email_tokens} tokens to fit budget {allowed_email_tokens}.")
                truncated_email_context = truncate_text_by_tokens(retrieved_email_context, tokenizer_model, allowed_email_tokens)
            else:
                truncated_email_context = retrieved_email_context
                
            final_context_parts.append(f"<User Email Context>\n{truncated_email_context}\n</User Email Context>")
            remaining_token_budget -= count_tokens(final_context_parts[-1], tokenizer_model) # Update budget
        else: final_context_parts.append("<User Email Context>\nNo relevant emails found or search skipped.\n</User Email Context>")

        # 3. Format Calendar Context
        if retrieved_calendar_context and remaining_token_budget > 0 and "error retrieving" not in retrieved_calendar_context.lower() and "query not detected" not in retrieved_calendar_context.lower():
            calendar_boilerplate_tokens = count_tokens("<Calendar Events Context>\n\n</Calendar Events Context>", tokenizer_model)
            allowed_calendar_tokens = max(0, remaining_token_budget - calendar_boilerplate_tokens)
            current_calendar_tokens = count_tokens(retrieved_calendar_context, tokenizer_model)
            
            if current_calendar_tokens <= allowed_calendar_tokens:
                final_context_parts.append(f"<Calendar Events Context>\n{retrieved_calendar_context}\n</Calendar Events Context>")
                remaining_token_budget -= count_tokens(final_context_parts[-1], tokenizer_model) # Update budget
            else:
                logger.warning(f"Skipping Calendar context ({current_calendar_tokens} tokens) as it exceeds remaining budget ({allowed_calendar_tokens}).")
                final_context_parts.append("<Calendar Events Context>\nCalendar events found but omitted due to token limits.\n</Calendar Events Context>")
        else: final_context_parts.append("<Calendar Events Context>\nNo relevant calendar events found or search skipped.\n</Calendar Events Context>")

        # Combine all parts into the final context string
        final_context = "\n\n".join(final_context_parts)
        final_context_tokens = count_tokens(final_context, tokenizer_model)
        logger.info(f"Constructed final context for LLM. Estimated tokens: {final_context_tokens} (Budget remaining: {remaining_token_budget})")
        logger.debug(f"Final Context Snippet:\n{final_context[:1000]}...")
        # --- END: Construct Final Context Directly ---

        # --- 4. Final Answer Generation using NEW Final Context ---
        formatted_history = []
        if chat_history:
            for msg in chat_history:
                role = "user" if msg.get("role") == "user" else "assistant"
                formatted_history.append({"role": role, "content": msg.get("content", "")})

        # MODIFIED: Updated final system prompt
        final_system_prompt = f"""You are Jarvis, an AI assistant.
        You are chatting with {user.display_name or user.email}.

        Your task is to answer the user's question based *only* on the information presented in the context sections below (Knowledge Base Documents, User Email Context, Calendar Events Context).
        Analyze the context provided and synthesize a comprehensive answer.
        
        **Crucially, when you use information from a specific Knowledge Base Document, you MUST cite its source filename parenthetically after the information, like this: (Source: filename.ext).** Use the 'Source:' value provided for each document.
        
        Do not add information not present in the context.
        Present the relevant findings clearly, structuring the information using Markdown (lists, bullet points etc.) where appropriate.
        If the context indicates no relevant information was found in a section (or overall), state that politely.

        Context Provided:
        {final_context}
        """
        final_messages = [ {"role": "system", "content": final_system_prompt} ]
        
        # MODIFICATION START: Handle DeepSeek's first message requirement
        needs_dummy_user_message = (
            provider == "deepseek" and 
            formatted_history and 
            formatted_history[0].get("role") == "assistant"
        )
        
        if needs_dummy_user_message:
            logger.debug("Prepending dummy user message for DeepSeek history requirement.")
            final_messages.append({"role": "user", "content": "Okay."})
        # END MODIFICATION
            
        final_messages.extend(formatted_history)
        final_messages.append({"role": "user", "content": message})

        logger.debug(f"Sending final prompt to {chat_model}...")
        # Ensure this await call is properly indented within the async function
        # ADDED RETRY LOGIC FOR RATE LIMIT
        max_retries = 2
        retry_delay = 5 # seconds
        for attempt in range(max_retries + 1):
            try:
                final_response_obj = await user_client.chat.completions.create(
                    model=chat_model,
                    messages=final_messages,
                    temperature=settings.OPENAI_TEMPERATURE
                )
                final_response = final_response_obj.choices[0].message.content
                logger.debug(f"RAG: Received final response from {chat_model} after attempt {attempt+1}.")
                return final_response # Success!
            except RateLimitError as rle:
                logger.warning(f"OpenAI Rate Limit Error (Attempt {attempt+1}/{max_retries+1}): {rle}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2 # Exponential backoff
                else:
                    logger.error("Max retries reached for OpenAI rate limit error.")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="OpenAI API rate limit exceeded after multiple retries. Please try again later."
                    ) from rle
            except Exception as final_call_err:
                # Catch other potential errors during the final call
                logger.error(f"Error during final OpenAI API call: {final_call_err}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An unexpected error occurred during the final response generation."
                ) from final_call_err

        # Should not be reached if logic is correct, but as a fallback:
        raise HTTPException(status_code=500, detail="Failed to generate response after retries.") 

    # Outer except blocks, correctly indented
    except HTTPException as http_exc:
        logger.error(f"HTTP Exception during RAG: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as e:
        logger.error(f"Error generating RAG response for user {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating the response." # Consider adding more detail from e?
        )

# --- Helper function for cosine similarity --- 
import numpy as np

def cos_sim(a, b):
    # ... (cos_sim logic) ...
    if not isinstance(a, (list, tuple, np.ndarray)) or not isinstance(b, (list, tuple, np.ndarray)): logger.warning(f"Invalid input types for cosine similarity: {type(a)}, {type(b)}"); return 0.0
    if not all(isinstance(x, (int, float)) for x in a) or not all(isinstance(x, (int, float)) for x in b): logger.warning("Non-numeric elements found in embeddings for cosine similarity."); return 0.0
    a = np.array(a); b = np.array(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0 or a.shape != b.shape: logger.warning("Invalid vectors for cosine similarity (zero vector or shape mismatch)."); return 0.0
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return similarity
# --- End Helper ---

# --- START: ADVANCED RAG FOR RATE CARDS ---
async def get_rate_card_response_advanced(
    message: str,
    user: User,
    db: Session
) -> str:
    logger.info(f"Initiating ADVANCED rate card query for user {user.email}: '{message}'")
    try:
        # Determine model and provider
        # NOTE: This function doesn't take model_id, so it uses the default setting.
        # If rate card RAG needs to support different models per query, model_id should be passed.
        chat_model = settings.OPENAI_MODEL_NAME 
        if not chat_model: # Add fallback if setting is missing
             logger.error("RateCardRAG: OPENAI_MODEL_NAME setting is not configured.")
             raise HTTPException(status_code=500, detail="LLM model name not configured for rate card search.")
             
        # Determine provider based on the configured model name
        if chat_model.lower().startswith("deepseek"):
            provider = "deepseek"
        # Add other providers here if needed
        # elif chat_model.lower().startswith("another-provider"):
        #     provider = "another-provider"
        else:
            provider = "openai" # Default to openai
        logger.debug(f"RateCardRAG: Using LLM model: {chat_model} via provider {provider}")

        # Fetch API key and base URL dynamically based on provider
        db_api_key = api_key_crud.get_api_key(db, user.email, provider)
        if not db_api_key:
            logger.warning(f"User {user.email} missing active {provider} key for Rate Card RAG.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider.capitalize()} API key required.")
        user_api_key = decrypt_token(db_api_key.encrypted_key)
        if not user_api_key:
            logger.error(f"Failed to decrypt stored {provider} key for user {user.email} (Rate Card RAG). Key ID: {db_api_key.id}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not decrypt stored {provider.capitalize()} API key.")
        user_base_url = db_api_key.model_base_url

        # Initialize client dynamically
        client_kwargs = {
            "api_key": user_api_key,
            "timeout": settings.OPENAI_TIMEOUT_SECONDS or 30.0 # Reuse timeout setting
        }
        if user_base_url:
            logger.info(f"RateCardRAG: Using custom base URL for {provider} for user {user.email}: {user_base_url}")
            client_kwargs["base_url"] = user_base_url
        else:
            logger.info(f"RateCardRAG: Using default base URL for {provider} for user {user.email}")
            
        user_client = AsyncOpenAI(**client_kwargs)
        # --- End Dynamic Client Init ---
        
        logger.debug("RateCardRAG: Analyzing query for key features...")
        # MODIFIED: Updated analysis prompt for better entity extraction
        # MODIFICATION: Prompt adjusted slightly to request JSON within text if JSON mode fails
        analysis_prompt_instruction = ("Return ONLY a JSON object string with keys: 'role', 'experience', 'skills' (list), 'location', 'amount' (integer), 'document_type'. "
                                     "Prioritize identifying the 'role' (main subject/entity) accurately. "
                                     "If a feature is not mentioned or unclear, use null or an empty list/string or 'unknown' for document_type.")
        analysis_system_content = ("You accurately extract key features (especially the main subject/role and document type) from user queries according to instructions. " + analysis_prompt_instruction)
        analysis_user_content = (
            f"Analyze the user query: '{message}'. "
            "Your goal is to extract key details to find the correct document and information within it. "
            "Identify:\n"
            "1. The **main subject** or **entity** the query is about (e.g., a client name like 'MAS' or 'GIC', a specific project, or a general role). This will be the 'role' field.\n"
            "2. Any specified **experience level** (e.g., junior, senior).\n"
            "3. Any specific **skills** mentioned.\n"
            "4. Any specified **location** or region.\n"
            "5. Any specific **dollar amount** mentioned.\n"
            "6. The **type of document** likely requested (e.g., 'rate card', 'SOW', 'LOA', 'general info', 'unknown').\n\n"
            f"{analysis_prompt_instruction}\n"
            "\nExample 1:\nQuery: Show the MAS rate card\nOutput: {\"role\": \"MAS\", \"experience\": null, \"skills\": [], \"location\": null, \"amount\": null, \"document_type\": \"rate card\"}\n"
            "Example 2:\nQuery: What is the rate for a senior GIC developer?\nOutput: {\"role\": \"GIC developer\", \"experience\": \"senior\", \"skills\": [], \"location\": null, \"amount\": null, \"document_type\": \"rate card\"}\n"
            "Example 3:\nQuery: Tell me about the Beyondsoft SOW\nOutput: {\"role\": \"Beyondsoft\", \"experience\": null, \"skills\": [], \"location\": null, \"amount\": null, \"document_type\": \"SOW\"}"
        )
        
        # MODIFICATION START: Conditional JSON format request
        analysis_args = {
            "model": chat_model,
            "messages": [
                {"role": "system", "content": analysis_system_content},
                {"role": "user", "content": analysis_user_content}
            ],
            "temperature": 0.0
        }
        # Assume only OpenAI supports JSON mode reliably for now
        request_json_mode = (provider == "openai")
        if request_json_mode:
            analysis_args["response_format"] = {"type": "json_object"}
        # END MODIFICATION

        analysis_response = await user_client.chat.completions.create(**analysis_args)
        
        # MODIFICATION START: Parse response based on whether JSON mode was requested
        content = analysis_response.choices[0].message.content
        query_features = None
        try:
            if request_json_mode: # Expect direct JSON object
                query_features = json.loads(content)
            else: # Parse text response, expecting JSON string
                content_cleaned = content.strip()
                # Attempt to extract JSON from potential markdown code blocks
                if content_cleaned.startswith("```json"):
                     content_cleaned = content_cleaned.split("\n", 1)[1].rsplit("\n```", 1)[0]
                elif content_cleaned.startswith("`{") and content_cleaned.endswith("`"):
                     content_cleaned = content_cleaned[1:-1] # Handle single backticks
                elif content_cleaned.startswith("{") and content_cleaned.endswith("}"): 
                     pass # Looks like JSON already
                else:
                     logger.warning(f"RateCardRAG: Query analysis for {provider} returned unexpected format: '{content}'. Attempting direct parse.")
                     # Attempt direct parse anyway, might work
                query_features = json.loads(content_cleaned) 
        except json.JSONDecodeError as json_err:
            logger.error(f"RateCardRAG: Failed to parse query feature analysis response ({provider}, JSON mode={request_json_mode}): {json_err}. Response: '{content}'", exc_info=True)
            # Raise or fallback? Fallback might be better UX.
            # raise HTTPException(status_code=500, detail="Failed to analyze query features for rate card search.") from json_err
            query_features = {} # Fallback to empty dict
        except Exception as parse_err: # Catch other unexpected errors
             logger.error(f"RateCardRAG: Error processing query feature analysis response: {parse_err}. Response: '{content}'", exc_info=True)
             query_features = {} # Fallback
        # END MODIFICATION
        
        # Ensure query_features is a dict even after fallback
        if query_features is None: query_features = {}

        logger.debug(f"RateCardRAG: Extracted query features: {query_features}")
        
        # Extract requested document type
        requested_doc_type = query_features.get('document_type')
        if requested_doc_type == 'unknown': requested_doc_type = None # Treat unknown as None

        # 3. Construct Multi-Vector Retrieval Queries
        retrieval_queries = []
        # MODIFIED: Construct base query including document type
        base_query_parts = [query_features.get(k) for k in ['role', 'experience', 'location'] if query_features.get(k)]
        if query_features.get('skills'):
            base_query_parts.extend(query_features['skills'])
        # Add the document type if identified and not None/empty
        if requested_doc_type:
            base_query_parts.append(requested_doc_type)
            
        # Filter out None or empty strings before joining
        filtered_parts = [part for part in base_query_parts if part]
        base_query = " ".join(filtered_parts) if filtered_parts else message # Fallback to original message if no parts
        retrieval_queries.append(base_query)
        logger.debug(f"RateCardRAG: Refined base retrieval query: {base_query}")
        
        # Additional queries (e.g., focusing only on role and experience)
        # Consider if these should also include doc_type?
        if query_features.get('role') and query_features.get('experience'):
            role_exp_query = f"{query_features['role']} {query_features['experience']}"
            # Optionally add doc_type here too? 
            # if requested_doc_type: role_exp_query += f" {requested_doc_type}"
            retrieval_queries.append(role_exp_query)
            logger.debug(f"RateCardRAG: Role/Experience query: {role_exp_query}")
        # Consider adding queries focusing only on skills if present
        if query_features.get('skills'):
            skills_query = " ".join(query_features['skills'])
            # Optionally add doc_type here too?
            # if requested_doc_type: skills_query += f" {requested_doc_type}"
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
                # MODIFIED: Adjust HyDE prompt based on document type if available
                hyde_system_prompt = "Generate a concise, factual hypothetical document answering the query."
                if requested_doc_type and requested_doc_type != 'general info':
                    hyde_system_prompt = f"Generate a concise, factual hypothetical **{requested_doc_type}** document snippet answering the query."
                    
                hyde_msgs = [
                    {"role": "system", "content": hyde_system_prompt}, 
                    {"role": "user", "content": q}
                ]
                hyde_resp = await user_client.chat.completions.create(model=chat_model, messages=hyde_msgs, temperature=0.0)
                gen_doc = hyde_resp.choices[0].message.content.strip()
                if gen_doc: hyde_doc = gen_doc
            except Exception: pass # Ignore HyDE failure for individual queries
            
            # Create embedding using the HyDE document (or original query if HyDE failed)
            embedding = await create_retrieval_embedding(hyde_doc, field='dense')
            query_vectors.append(embedding)
            # MODIFIED: Log the actual text used for embedding (HyDE or query)
            logger.debug(f"RateCardRAG: Generated embedding for query: '{q}' (using text: {hyde_doc[:50]}...)")

        # 5. Perform Multi-Vector Search in Milvus
        k_per_query = int(getattr(settings, 'RATE_CARD_RESULTS_PER_QUERY', 3))
        all_search_results = []
        # Build filename filter requiring all key terms
        terms = ['rate', 'card']
        role_term = query_features.get('role')
        if role_term:
            terms.insert(0, role_term)
        logger.debug(f"RateCardRAG: Using filename terms for pre-filtering: {terms}")

        # MODIFIED: Call the new hybrid search function for each query vector
        for i, q in enumerate(retrieval_queries):
            logger.debug(f"RateCardRAG: Performing HYBRID search for query: '{q}'")
            # Determine target collection name (RAG collection)
            sanitized_email = user.email.replace('@', '_').replace('.', '_')
            target_collection_name = f"{sanitized_email}_knowledge_base_bm"

            # Call the hybrid function with the filename terms list
            hybrid_results = await search_milvus_knowledge_hybrid(
                query_text=q,  # Pass the actual query text
                collection_name=target_collection_name,
                limit=k_per_query,
                # Pass the list of terms directly
                filename_terms=terms 
            )
            # The hybrid function returns a single list of fused results for the query
            all_search_results.extend(hybrid_results)
            logger.debug(f"RateCardRAG: Found {len(hybrid_results)} fused results for query '{q}'.")
            
        logger.info(f"RateCardRAG: Total raw results from hybrid searches: {len(all_search_results)}")

        # 6. Deduplicate and Re-rank Results (No change needed here, works on the combined list)
        unique_results = {res['id']: res for res in all_search_results} 

        # 7. Context Selection & Formatting (Select top N re-ranked results)
        # This part now uses the results reranked by the cross-encoder
        final_context_limit = int(getattr(settings, 'RATE_CARD_FINAL_CONTEXT_LIMIT', 5))
        context_parts = []
        for res in unique_results.values():
            doc_id = res.get('id', 'N/A')
            # Use 'content' field directly as returned by search_milvus_knowledge
            doc_content = res.get('content', '') 
            # Extract metadata and filename safely
            doc_metadata = res.get("metadata") 
            source_filename = "Unknown Source"
            if isinstance(doc_metadata, dict): 
                source_filename = doc_metadata.get('original_filename', 'Unknown Source')
            elif isinstance(doc_metadata, str):
                try: 
                    meta_dict = json.loads(doc_metadata)
                    source_filename = meta_dict.get('original_filename', 'Unknown Source')
                except json.JSONDecodeError:
                    source_filename = "Metadata Parse Error"
            # Format string including source
            context_parts.append(f"--- Document ID: {doc_id} (Source: {source_filename}) ---\nContent: {doc_content}")
        
        context = "\n\n".join(context_parts)
        # context = "\n\n---\n\n".join([f"Document ID: {res['id']}\nContent: {json.dumps(res.get('content'))}" for res in ranked_results[:final_context_limit]]) # Original line
        logger.debug(f"RateCardRAG: Formatted final context (top {len(unique_results.values())}):\n{context[:500]}...")

        # 8. Generate Final Response using LLM
        # MODIFIED: Update system prompt to instruct citation
        system_prompt = (
            "You are Jarvis, an AI assistant specializing in providing rate card information. "
            f"You are chatting with {user.display_name or user.email}. "
            "Use the provided context containing relevant rate card entries to answer the user's query accurately. "
            "Directly quote rates and associated details (like role, experience, skills, location) from the context. "
            "**When using information from a document, cite its source filename like this: (Source: filename.ext).** "
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
        response = await user_client.chat.completions.create(model=chat_model,messages=messages,temperature=0.0)
        final_response = response.choices[0].message.content
        logger.info("RateCardRAG: Generated final response.")
        return final_response
    except HTTPException as http_exc: raise http_exc
    except Exception as e: logger.error(f"Error during advanced rate card RAG for user {user.email}: {e}", exc_info=True); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="An error occurred while processing your rate card request.")
# --- END: ADVANCED RAG FOR RATE CARDS --- 
