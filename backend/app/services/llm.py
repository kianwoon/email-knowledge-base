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
from ..models.token_models import TokenDB # Import TokenDB
from ..config import settings # Import settings if not already

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
    # REMOVED: keywords: List[str],
    # REMOVED: original_message: str = "",
    # ADDED: Specific filter parameters
    sender_filter: Optional[str] = None,
    subject_filter: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search_terms: Optional[List[str]] = None, # Renamed from keywords for general search
    limit: int = 5,
    user_client: AsyncOpenAI = None, # Client configured for the correct provider
    token: Optional[TokenDB] = None, # ADDED: Optional Token parameter
    provider: str = "openai" # ADDED: Provider name ('openai', 'deepseek', etc.)
) -> List[Dict[str, Any]]:
    """Queries the email_facts Iceberg table using DuckDB based on structured filters, applying token scope (columns) if provided.""" # Updated docstring
    results = []
    # REMOVED: Check for keywords/original_message
    # ADDED: Basic check if *any* filter is provided beyond user_email
    if not sender_filter and not subject_filter and not start_date and not end_date and not search_terms:
        logger.warning("DuckDB Query: No specific filters (sender, subject, date, terms) provided. Returning empty results.")
        return results
    if not user_client:
        logger.error("DuckDB Query: User-specific OpenAI client (user_client) was not provided.")
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

        # --- REMOVED: LLM-based Date Filtering Logic ---
        # Removed the entire block that called an LLM to extract dates.
        # --- END REMOVED ---

        # --- REVISED: Build WHERE clause based on provided filters ---
        where_clauses = ["owner_email = ?"]
        params = [user_email]

        # Add specific filters
        if sender_filter:
            # --- ADDED: Check if sender_filter looks plausible --- 
            is_plausible_sender = '@' in sender_filter or len(sender_filter.split()) > 1 # Simple check: contains @ or multiple words?
            if is_plausible_sender:
                where_clauses.append("sender LIKE ?")
                params.append(f"%{sender_filter}%") 
                logger.debug(f"Applying sender filter: {sender_filter}")
            else:
                logger.warning(f"Ignoring likely implausible sender filter extracted by LLM: '{sender_filter}'")
            # --- END CHECK --- 
        if subject_filter:
            where_clauses.append("subject LIKE ?")
            params.append(f"%{subject_filter}%")
            logger.debug(f"Applying subject filter: {subject_filter}")
        if start_date:
            where_clauses.append("received_datetime_utc >= ?")
            params.append(start_date)
            logger.debug(f"Applying start_date filter: {start_date.isoformat()}")
        if end_date:
            where_clauses.append("received_datetime_utc <= ?")
            params.append(end_date)
            logger.debug(f"Applying end_date filter: {end_date.isoformat()}")

        # Add general search terms filter (like original keyword logic)
        keyword_params = []
        keyword_filter_parts = []
        if search_terms:
            logger.debug(f"Applying general search terms: {search_terms}")
            for term in search_terms:
                # Apply LIKE across multiple relevant fields
                like_part = f"(subject LIKE ? OR body_text LIKE ? OR sender LIKE ? OR sender_name LIKE ? OR generated_tags LIKE ? OR quoted_raw_text LIKE ?)"
                keyword_filter_parts.append(like_part)
                # Escape % and _ within the term itself before adding wildcards
                safe_term = term.replace('%', '\\%').replace('_', '\\_')
                keyword_params.extend([f'%{safe_term}%'] * 6) # Parameter for each '?' in like_part

            if keyword_filter_parts:
                # Combine keyword parts with OR, and wrap the whole group in parentheses
                keyword_clause = "(" + " OR ".join(keyword_filter_parts) + ")"
                where_clauses.append(keyword_clause)
                params.extend(keyword_params)

        # --- END REVISED WHERE clause ---

        # --- START: Determine SELECT columns based on token ---
        select_columns = "*" # Default to selecting all columns
        # Define columns essential for the query logic (WHERE, ORDER BY) AND context building
        essential_query_cols = {"owner_email", "received_datetime_utc", "subject", "body_text", "sender", "sender_name", "generated_tags", "granularity", "quoted_raw_text", "message_id"}
        
        if token and token.allow_columns: # Check if token exists and allow_columns is set
            allowed_set = set(token.allow_columns)
            # Ensure essential columns are included
            final_select_set = allowed_set.union(essential_query_cols)
            # We need to check against actual columns in the view to avoid errors
            view_columns = set([desc[0] for desc in con.execute(f"DESCRIBE {view_name};").fetchall()])
            valid_select_cols = [col for col in final_select_set if col in view_columns]
            
            if valid_select_cols:
                select_columns = ", ".join([f'"{col}"' for col in valid_select_cols]) # Quote column names
                logger.info(f"Applying column projection based on token {token.id}. Selecting: {select_columns}")
            else:
                # This case should be rare if essential cols exist, but prevents selecting nothing
                logger.warning(f"Token {token.id} allow_columns resulted in empty valid selection. Defaulting to SELECT *.")
                select_columns = "*"
        # --- END: Determine SELECT columns ---

        # Construct the full SQL query with dynamic SELECT and WHERE clauses
        effective_limit = token.row_limit if token else limit # Prioritize token limit if available
        effective_limit = min(effective_limit, limit) # Ensure it doesn't exceed the requested limit

        # Combine specific filters (sender, subject, date) with AND
        specific_filters_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # Combine keyword search part with OR
        keyword_search_sql = "(" + " OR ".join(keyword_filter_parts) + ")" if keyword_filter_parts else "FALSE"

        # Combine specific filters and keyword search with OR, ensuring owner_email is always applied
        where_sql = f"owner_email = ? AND ({specific_filters_sql.replace('owner_email = ? AND ', '', 1)} OR {keyword_search_sql})"
        # Adjust params: owner_email is first, then specific filter params, then keyword params
        final_params = [user_email] + params[1:] + keyword_params

        sql_query = f"""
        SELECT
            {select_columns}
        FROM {view_name}
        WHERE {where_sql}
        ORDER BY received_datetime_utc DESC
        LIMIT ?;
        """
        final_params.append(effective_limit) # Add limit as the last parameter

        logger.debug(f"Executing DuckDB Query: {sql_query}")
        logger.debug(f"With Params: {final_params}")

        # Execute query and fetch results
        arrow_table = con.execute(sql_query, final_params).fetch_arrow_table()
        results = arrow_table.to_pylist()
        logger.info(f"DuckDB query returned {len(results)} email results.")

    except Exception as e:
        logger.error(f"Error querying DuckDB for emails: {e}", exc_info=True)
        results = [] # Ensure empty list on error
    finally:
        if 'con' in locals() and con:
            con.close()

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
    """Truncates text to fit within a specified token limit."""
    if not text:
        return ""
    
    if not isinstance(text, str):
        logger.warning(f"Attempted to truncate non-string type: {type(text)}. Returning empty string.")
        return ""
    
    current_tokens = count_tokens(text, model)
    if current_tokens <= max_tokens:
        return text  # No truncation needed
    
    try:
        # Get the encoder for the model
        if model not in _token_encoders:
            try:
                _token_encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                logger.warning(f"Model {model} not found in tiktoken. Using cl100k_base encoding.")
                _token_encoders[model] = tiktoken.get_encoding("cl100k_base")
        
        encoder = _token_encoders[model]
        
        # Encode the text to tokens
        tokens = encoder.encode(text)
        
        # Truncate to max_tokens
        truncated_tokens = tokens[:max_tokens]
        
        # Decode back to text
        truncated_text = encoder.decode(truncated_tokens)
        
        # Add truncation indicator
        if len(truncated_text) < len(text):
            truncated_text += " [...truncated...]"
        
        return truncated_text
    except Exception as e:
        logger.error(f"Error truncating text by tokens: {e}", exc_info=True)
        # Fallback to simple character-based truncation if token-based fails
        approx_chars_per_token = 4  # Very rough approximation
        approx_chars = max_tokens * approx_chars_per_token
        fallback_text = text[:approx_chars] + " [...truncated due to error...]"
        return fallback_text

# --- End Helper ---

# --- START: Email Batch Summarization Helper Function ---
async def _summarize_email_batch(
    email_batch: List[Dict[str, Any]], 
    original_query: str,
    batch_llm_client: AsyncOpenAI, # Use the configured client
    batch_model_name: str,         # Use the configured model
    max_chars_per_email: int = 1000 # Limit context per email within batch
) -> str:
    """Summarizes a batch of emails focusing on relevance to the original query."""
    logger.debug(f"Starting summary for batch of {len(email_batch)} emails.")
    if not email_batch: return "" # Return empty string if batch is empty

    # Helper to truncate email body within the batch context
    def _truncate_email_body(text: str, max_len: int) -> str:
        text_str = str(text) if text is not None else ''
        if len(text_str) > max_len: return text_str[:max_len] + "... [TRUNCATED FOR SUMMARY]"; return text_str

    # Format the batch context
    batch_context_parts = []
    for i, email in enumerate(email_batch): 
        # Extract only essential fields for summarization
        sender = email.get('sender', 'Unknown Sender')
        subject = email.get('subject', 'No Subject')
        received_date = email.get('received_datetime_utc', 'Unknown Date')
        body_text = email.get('body_text', '')
        quoted_text = email.get('quoted_raw_text', '') 
        full_body = f"{body_text}\n\n--- Quoted Text ---\n{quoted_text}".strip()
        truncated_body = _truncate_email_body(full_body, max_chars_per_email)

        # Build the entry string incrementally
        entry_str = f"--- Email {i+1} ---\n"
        entry_str += f"From: {sender}\n"
        entry_str += f"Subject: {subject}\n"
        entry_str += f"Date: {received_date}\n"
        entry_str += f"Body:\n{truncated_body}\n"
        entry_str += f"--- End Email {i+1} ---"
        batch_context_parts.append(entry_str)
    batch_context_str = "\n\n".join(batch_context_parts)

    # Define the summarization prompt
    summary_system_prompt = (
        f"You are an expert summarizer. Your task is to read the following batch of emails and extract the key information, updates, developments, action items, or news that are **directly relevant** to the user's original query: \"{original_query}\".\n" \
        f"Focus ONLY on information related to that query. Ignore irrelevant details.\n" \
        f"Produce a concise summary of the relevant points found within this email batch. If no relevant information is found, state that clearly.\n" \
        f"Present the summary clearly, perhaps using bullet points for distinct items."
    )
    
    summary_user_prompt = f"Email Batch Context:\n{batch_context_str}"

    try:
        # Call the LLM for summarization
        response = await batch_llm_client.chat.completions.create(
            model=batch_model_name,
            messages=[
                {"role": "system", "content": summary_system_prompt},
                {"role": "user", "content": summary_user_prompt}
            ],
            temperature=0.1, # Lower temperature for factual summary
            max_tokens=1024 # Adjust max tokens for summary length as needed
        )
        summary = response.choices[0].message.content.strip()
        logger.debug(f"Batch summary generated (length {len(summary)}): {summary[:100]}...")
        return summary
    except Exception as e:
        logger.error(f"Error during email batch summarization LLM call: {e}", exc_info=True)
        return "Error summarizing this email batch." # Return error message
# --- END Email Batch Summarization Helper ---


# --- START: Email Context Retrieval Helper ---
async def _get_email_context(
    max_items: int, 
    max_chunk_chars: int, # Note: max_chunk_chars isn't directly used by query_iceberg, but kept for consistency
    user_client: AsyncOpenAI, 
    search_params: dict, 
    user_email: str
) -> List[Dict[str, Any]]:
    """Retrieves email context by calling query_iceberg_emails_duckdb."""
    logger.debug(f"_get_email_context called with params: {search_params}, limit: {max_items}")
    try:
        # Determine provider based on client type or add as parameter if needed
        # This assumes user_client is configured for a specific provider (OpenAI/Deepseek)
        # A more robust way might involve passing the provider string explicitly
        provider = "openai" # Default assumption, adjust if necessary
        if hasattr(user_client, 'base_url') and 'deepseek' in str(user_client.base_url):
            provider = "deepseek"
            
        email_results = await query_iceberg_emails_duckdb(
            user_email=user_email,
            sender_filter=search_params.get("sender_filter"),
            subject_filter=search_params.get("subject_filter"),
            start_date=search_params.get("start_date"),
            end_date=search_params.get("end_date"),
            search_terms=search_params.get("search_terms"),
            limit=max_items, # Pass the calculated limit
            user_client=user_client, # Pass the client
            provider=provider, # Pass determined provider
            token=None # Pass token if applicable/available
        )
        logger.info(f"_get_email_context retrieved {len(email_results)} emails.")
        return email_results
    except Exception as e_iceberg:
        logger.error(f"Error calling query_iceberg_emails_duckdb within _get_email_context: {e_iceberg}", exc_info=True)
        return [] # Return empty list on error
# --- END: Email Context Retrieval Helper ---


# --- START: Milvus Context Retrieval Helper ---
async def _get_milvus_context(
    max_items: int, 
    max_chunk_chars: int,
    query: str,
    user_email: str
) -> List[Dict[str, Any]]:
    """Retrieves document context from Milvus using the search_milvus_knowledge_hybrid function."""
    logger.debug(f"_get_milvus_context called with query: '{query[:50]}...', limit: {max_items}")
    try:
        # Create collection name using the user's email
        sanitized_email = user_email.replace('@', '_').replace('.', '_')
        collection_name = f"{sanitized_email}_knowledge_base_bm"
        
        # Call the hybrid search function from embedder.py
        document_results = await search_milvus_knowledge_hybrid(
            query_text=query,
            collection_name=collection_name,
            limit=max_items
        )
        
        # Rerank if more than 1 result is returned for improved relevance
        if len(document_results) > 1:
            document_results = await rerank_results(
                query=query,
                results=document_results
            )
            # Apply final limit after reranking
            document_results = document_results[:max_items]
            
        logger.info(f"_get_milvus_context retrieved {len(document_results)} documents.")
        return document_results
    except Exception as e_milvus:
        logger.error(f"Error during Milvus document retrieval in _get_milvus_context: {e_milvus}", exc_info=True)
        return [] # Return empty list on error
# --- END: Milvus Context Retrieval Helper ---


# --- START: Helper function to build the system prompt ---
def _build_system_prompt() -> str:
    # This is a basic system prompt. You can customize it further.
    return "You are a helpful AI assistant. Your user is asking a question.\n" \
           "You have been provided with some context information (RAG Context) that might be relevant to the user's query.\n" \
           "Please use this context to answer the user's question accurately and concisely.\n" \
           "If the context doesn't provide enough information, state that you couldn't find the answer in the provided documents or emails.\n" \
           "Do not make up information.\n\n" \
           "<RAG_CONTEXT_PLACEHOLDER>"
# --- END: Helper function to build the system prompt ---

# --- START: Helper function to format chat history ---
def _format_chat_history(
    chat_history: List[Dict[str, str]], 
    model: str = "gpt-4", # Default model for token counting
    max_tokens: Optional[int] = None
) -> str:
    """Formats chat history into a string, optionally truncating by tokens."""
    if not chat_history:
        return ""

    formatted_history_parts = []
    for entry in chat_history:
        role = entry.get("role", "user") # Default to user if role is missing
        content = entry.get("content", "")
        formatted_history_parts.append(f"{role.capitalize()}: {content}")
    
    full_history_str = "\n".join(formatted_history_parts)

    if max_tokens is not None:
        current_tokens = count_tokens(full_history_str, model)
        if current_tokens > max_tokens:
            logger.warning(f"Chat history ({current_tokens} tokens) exceeds max_tokens ({max_tokens}). Truncating.")
            # For simplicity, this example truncates from the beginning of the history.
            # More sophisticated truncation (e.g., keeping recent messages) might be needed.
            truncated_history = truncate_text_by_tokens(full_history_str, model, max_tokens)
            return truncated_history
            
    return full_history_str
# --- END: Helper function to format chat history ---


async def get_rate_card_response_advanced(
    message: str,
    chat_history: List[Dict[str, str]],  # ADDED: chat_history parameter
    user: "User",
    db: "Session",
    model_id: Optional[str] = None,      # Add model_id parameter
    ms_token: Optional[str] = None       # Add ms_token parameter
) -> str:
    logger.info(f"Initiating ADVANCED rate card query for user {user.email}: '{message}'")
    fallback_response = (
        "I apologize, but I encountered an unexpected error while "
        "processing your rate card query. Our team has been notified of this issue."
    )
    try:
        # 1. Determine model & provider
        chat_model = model_id or settings.OPENAI_MODEL_NAME
        if not chat_model:
            logger.error(
                "RateCardRAG: LLM model name not configured "
                "(model_id missing and OPENAI_MODEL_NAME not set)."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LLM model name not configured for rate card search."
            )

        provider = "deepseek" if chat_model.lower().startswith("deepseek") else "openai"
        logger.debug(
            f"RateCardRAG: Using LLM model: {chat_model} via provider {provider}"
        )

        # 2. Fetch & decrypt API key
        db_api_key = api_key_crud.get_api_key(db, user.email, provider)
        if not db_api_key:
            logger.warning(
                f"User {user.email} missing active {provider} key for Rate Card RAG."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{provider.capitalize()} API key required."
            )
        user_api_key = decrypt_token(db_api_key.encrypted_key)
        if not user_api_key:
            logger.error(
                f"Failed to decrypt {provider} key for user {user.email}. Key ID: {db_api_key.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not decrypt stored {provider.capitalize()} API key."
            )

        # 3. Initialize client
        default_timeout = settings.DEFAULT_LLM_TIMEOUT_SECONDS
        if provider == "deepseek":
            provider_timeout = float(
                settings.DEEPSEEK_TIMEOUT_SECONDS or default_timeout
            )
        else:
            provider_timeout = float(
                settings.OPENAI_TIMEOUT_SECONDS or default_timeout
            )

        client_kwargs = {"api_key": user_api_key, "timeout": provider_timeout}
        if db_api_key.model_base_url:
            client_kwargs["base_url"] = db_api_key.model_base_url
        elif provider == "deepseek":
            client_kwargs["base_url"] = "https://api.deepseek.com/v1"

        user_client = AsyncOpenAI(**client_kwargs)

        # 4. Extract query features via LLM
        logger.debug("RateCardRAG: Analyzing query for key features...")
        analysis_system = (
            "You extract key features from user queries for rate card lookup. "
            "Return ONLY a JSON object with fields: "
            "'role', 'experience', 'skills' (list), 'location', 'amount' (integer), "
            "'document_type'. Use null for missing."
        )
        analysis_user = (
            f"Analyze this query: '{message}' and extract:\n"
            "1. role (main subject/entity)\n"
            "2. experience level (if any)\n"
            "3. skills list\n"
            "4. location\n"
            "5. dollar amount\n"
            "6. document_type (e.g., 'rate card', 'SOW', etc.)\n\n"
            "Respond with JSON only.\n\n"
            "Examples:\n"
            "  Query: Show the MAS rate card\n"
            "  Output: {\"role\":\"MAS\",\"experience\":null,\"skills\":[],"
            "\"location\":null,\"amount\":null,\"document_type\":\"rate card\"}\n"
            "  Query: Rate for a senior GIC developer?\n"
            "  Output: {\"role\":\"GIC developer\",\"experience\":\"senior\",\"skills\":[],"
            "\"location\":null,\"amount\":null,\"document_type\":\"rate card\"}"
        )
        analysis_args = {
            "model": chat_model,
            "messages": [
                {"role": "system", "content": analysis_system},
                {"role": "user", "content": analysis_user}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"} if provider == "openai" else None
        }
        analysis_response = await user_client.chat.completions.create(**analysis_args)
        raw = analysis_response.choices[0].message.content
        try:
            query_features = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"RateCardRAG: Failed to parse JSON: {raw}")
            query_features = {}

        # Normalize document_type
        doc_type = query_features.get("document_type")
        if doc_type == "unknown":
            doc_type = None

        # 5. Build filename_terms_for_search
        filename_terms = []
        m = re.search(r"original_filename\s*(?:is|=)\s*['\"]?([^.'\"]+)['\"]?", message, re.IGNORECASE)
        if m:
            part = m.group(1).strip()
            filename_terms = [
                t for t in re.split(r"[\s_-]+", part)
                if len(t) > 1 and t.lower() not in {"and","the","of","for","a","to","v"}
            ]
        if not filename_terms:
            # fallback to role & doc_type tokens
            role = query_features.get("role")
            if role:
                filename_terms += [t for t in re.split(r"[\s_-]+", role) if t]
            if doc_type:
                filename_terms += [t for t in re.split(r"[\s_-]+", doc_type) if t]
            if "rate card" in message.lower() or doc_type == "rate card":
                filename_terms += ["rate","card"]
        filename_terms = list({t for t in filename_terms if t})

        # 6. Build retrieval queries
        base_parts = [query_features.get(f) for f in ("role","experience","location") if query_features.get(f)]
        if skills := query_features.get("skills"):
            base_parts += skills
        if doc_type:
            base_parts.append(doc_type)
        queries = list({ " ".join([p for p in base_parts if p]) or message })

        # 7. HyDE & embeddings
        embeddings = []
        for q in queries:
            hyde = q
            try:
                hyde_resp = await user_client.chat.completions.create(
                    model=chat_model,
                    messages=[{"role":"user","content":f"Generate a brief rate-card snippet for: '{q}'"}],
                    temperature=0.0
                )
                hyde = hyde_resp.choices[0].message.content.strip() or q
            except Exception:
                pass
            embeddings.append(await create_retrieval_embedding(hyde, field="dense"))

        # 8. Hybrid search in Milvus
        sanitized = user.email.replace("@","_").replace(".","_")
        collection = f"{sanitized}_knowledge_base_bm"
        per_q = int(getattr(settings, "RATE_CARD_RESULTS_PER_QUERY", 3))
        # -- BEGIN: Bypass filename_terms filter and boost top-k for Mas rate card retrieval --
        # Temporarily disable filename_terms filtering to surface the MAS rate card document
        filename_terms = []
        # Increase number of candidates fetched
        per_q = max(per_q, int(getattr(settings, "RATE_CARD_RESULTS_PER_QUERY", 3)) * 2)
        # -- END: Bypass filename_terms filter and boost top-k for Mas rate card retrieval --
        raw_results = []
        for vec, q in zip(embeddings, queries):
            hits = await search_milvus_knowledge_hybrid(
                query_text=q,
                collection_name=collection,
                limit=per_q,
                filename_terms=filename_terms,
                dense_params={"metric_type":"COSINE","params":{"ef":128},"search_data_override":vec}
            )
            raw_results.extend(hits)

        # Fallback: if hybrid search yields no results, use dense-only search
        if not raw_results:
            logger.info("RateCardRAG: Hybrid search returned no results; falling back to dense search without filename filter.")
            try:
                dense_results = await search_milvus_knowledge(
                    query_text=message,
                    collection_name=collection,
                    limit=per_q
                )
                if dense_results:
                    logger.info(f"RateCardRAG: Dense search returned {len(dense_results)} results.")
                    raw_results = dense_results
            except Exception as e_dense:
                logger.error(f"RateCardRAG: Dense fallback search failed: {e_dense}", exc_info=True)

        # 9. Dedupe & rerank
        unique = {r["id"]: r for r in raw_results}.values()
        reranked = await rerank_results(query=message, results=list(unique))

        # PRIORITIZE MAS DOCUMENT if present
        prioritized = []
        for doc in reranked:
            fname = doc.get('metadata', {}).get('original_filename', '').lower()
            if 'mas' in fname:
                prioritized.append(doc)
        # Remove prioritized docs from reranked and prepend them
        if prioritized:
            reranked = [doc for doc in reranked if doc not in prioritized]
            reranked = prioritized + reranked
            logger.info(f"RateCardRAG: Prioritized {len(prioritized)} MAS-related documents in final context order.")

        # 10. Format top‐K context
        k = int(getattr(settings, "RATE_CARD_FINAL_CONTEXT_LIMIT", 5))
        chosen = reranked[:k]
        if not chosen:
            doc_context = "No rate card documents matched your query."
        else:
            parts = []
            for d in chosen:
                txt = d.get("content","")
                limit = int(getattr(settings,"RATE_CARD_MAX_CHARS_PER_DOC",4000))
                txt = txt[:limit] + ("...[TRUNC]" if len(txt)>limit else "")
                fname = d.get("metadata",{}).get("original_filename","Unknown")
                score = d.get("rerank_score",d.get("score","N/A"))
                parts.append(f"Source: {fname} (Score:{score})\n{txt}")
            doc_context = "<Rate Card Context>\n" + "\n\n---\n\n".join(parts) + "\n</Rate Card Context>"

        # 11. Token‐budgeting & final prompt
        MAX_TOK = int(getattr(settings, "MODEL_MAX_TOKENS", 16384))
        BUF = int(getattr(settings, "RESPONSE_BUFFER_TOKENS", 4096))
        HST = int(getattr(settings, "MAX_CHAT_HISTORY_TOKENS", 2000))
        system_prompt = _build_rate_card_system_prompt()
        hist = _format_chat_history(chat_history, model=chat_model, max_tokens=HST)
        used = (
            count_tokens(system_prompt.replace("<RATE_CARD_CONTEXT>",""), chat_model) +
            count_tokens(hist, chat_model) +
            count_tokens(message, chat_model) +
            BUF
        )
        remain = MAX_TOK - used
        if remain <= 0:
            rag_ctx = "Context omitted due to token limits."
        else:
            needed = count_tokens(doc_context, chat_model)
            if needed <= remain:
                rag_ctx = doc_context
            else:
                rag_ctx = truncate_text_by_tokens(doc_context, chat_model, remain)

        final_sys = system_prompt.replace("<RATE_CARD_CONTEXT>", rag_ctx)
        messages_out = [{"role":"system","content":final_sys}]
        if hist:
            messages_out.append({"role":"user","content":f"History:\n{hist}"})
        messages_out.append({"role":"user","content":message})

        # 12. Final LLM call
        resp = await user_client.chat.completions.create(
            model=chat_model,
            messages=messages_out,
            temperature=float(getattr(settings,"OPENAI_TEMPERATURE",0.1)),
            max_tokens=BUF
        )
        content = resp.choices[0].message.content.strip()
        return _format_rate_card_response(content)

    except HTTPException:
        raise
    except RateLimitError:
        return "I'm experiencing high demand—please try again shortly."
    except Exception as e:
        logger.error(f"Unexpected error in RateCardRAG: {e}", exc_info=True)
        return fallback_response

    # Defensive fallback
    return fallback_response

# --- Helper function to build rate card system prompt ---
def _build_rate_card_system_prompt() -> str:
    """Builds a specialized system prompt for rate card queries."""
    return "You are a helpful AI assistant specializing in rate card information. Your user is asking about pricing, costs, or rates.\n" \
           "You have been provided with rate card context that might be relevant to the user's query.\n" \
           "When responding to rate card questions:\n" \
           "1. Be precise and specific about pricing, using exact figures when available.\n" \
           "2. Clearly state any conditions, terms, or qualifications that apply to the rates.\n" \
           "3. Organize information in a clear, structured format when presenting multiple options.\n" \
           "4. If the context doesn't provide specific rate information for the user's query, state that clearly.\n" \
           "5. Do not make up or estimate prices if they are not in the provided context.\n\n" \
           "<RATE_CARD_CONTEXT>"

# --- Rate card parameter extraction helper ---
async def _extract_rate_card_parameters(message: str, user_client: AsyncOpenAI, model: str) -> Dict[str, Any]:
    """Extracts rate card specific parameters from the user's message."""
    try:
        extraction_prompt = f"""Extract key rate card parameters from this query: "{message}"
Please identify the following:
1. Service or product the user is asking about
2. Specific region or location (if mentioned)
3. Time period or duration (if mentioned)
4. Any specific pricing tier or level (if mentioned)
5. Any specific client or customer type (if mentioned)

Respond with a JSON object containing these fields (null if not found):
{{
  "service": string or null,
  "region": string or null,
  "time_period": string or null,
  "tier": string or null,
  "client_type": string or null
}}"""

        response = await user_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Extract rate card parameters from the user query."},
                      {"role": "user", "content": extraction_prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        params = json.loads(response.choices[0].message.content)
        return params
    except Exception as e:
        logger.error(f"Error extracting rate card parameters: {e}", exc_info=True)
        return {
            "service": None,
            "region": None,
            "time_period": None,
            "tier": None,
            "client_type": None
        }

# --- Rate card response formatting helper ---
def _format_rate_card_response(response: str) -> str:
    """Post-processes rate card responses to format currency and numbers consistently."""
    try:
        # Format dollar amounts consistently (e.g., $1,000 instead of $1000)
        dollar_pattern = r'\$(\d+)(?![\d,])'
        response = re.sub(dollar_pattern, lambda m: f"${int(m.group(1)):,}", response)
        
        return response
    except Exception as e:
        logger.error(f"Error formatting rate card response: {e}", exc_info=True)
        return response

async def generate_openai_rag_response(
    message: str,
    chat_history: List[Dict[str, str]],
    user: User,
    db: Session,
    model_id: Optional[str] = None,
    ms_token: Optional[str] = None
) -> str:
    """Generates a chat response using RAG with context from Milvus and Iceberg (emails),
    using an LLM to select/synthesize the most relevant context.
    Fails if the user has not provided their OpenAI API key."""
    logger.error(f"DEBUG RAG - Function Entry: generate_openai_rag_response for user {user.email} - Message: '{message[:50]}...'")
    logger.critical("!!! RAG function execution STARTED !!!") # ADDED DEBUG LOG
    fallback_response = "I apologize, but I encountered an unexpected error while processing your request. Our team has been notified of this issue."
    
    # Define necessary constants from settings or defaults
    MAX_CHUNK_CHARS = int(getattr(settings, 'RAG_CHUNK_MAX_CHARS', 5000))
    MAX_TOTAL_TOKENS = int(getattr(settings, 'MODEL_MAX_TOKENS', 16384))
    RESPONSE_BUFFER_TOKENS = int(getattr(settings, 'RESPONSE_BUFFER_TOKENS', 4096))
    MAX_CHAT_HISTORY_TOKENS = int(getattr(settings, 'MAX_CHAT_HISTORY_TOKENS', 2000))
    MULTI_STAGE_EMAIL_TOKEN_THRESHOLD = int(getattr(settings, 'MULTI_STAGE_EMAIL_TOKEN_THRESHOLD', 8000))
    EMAIL_SUMMARY_BATCH_SIZE = int(getattr(settings, 'EMAIL_SUMMARY_BATCH_SIZE', 10))
    MAX_DOCUMENT_CONTEXT_CHARS = int(getattr(settings, 'RAG_DOCUMENT_MAX_CHARS_PER_ITEM', 3000)) # Max chars per document in context

    # Initial Setup
    try:
        chat_model = model_id or settings.OPENAI_MODEL_NAME
        provider = "deepseek" if chat_model.lower().startswith("deepseek") else "openai"
        db_api_key = api_key_crud.get_api_key(db, user.email, provider)
        if not db_api_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider.capitalize()} API key required.")
        user_api_key = decrypt_token(db_api_key.encrypted_key)
        if not user_api_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not decrypt API key.")

        # Configure client
        default_timeout_setting = settings.DEFAULT_LLM_TIMEOUT_SECONDS
        provider_timeout_setting = getattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS", default_timeout_setting)

        # Ensure we have a valid value before converting to float
        if provider_timeout_setting is None:
            logger.warning(f"Timeout setting for {provider.upper()} or DEFAULT is None. Using hardcoded default: 30.0s")
            provider_timeout = 30.0 # Hardcoded safe default
        else:
            try:
                provider_timeout = float(provider_timeout_setting)
            except (ValueError, TypeError):
                logger.error(f"Invalid timeout setting value: {provider_timeout_setting}. Using hardcoded default: 30.0s")
                provider_timeout = 30.0 # Hardcoded safe default on conversion error

        client_kwargs = {"api_key": user_api_key, "timeout": provider_timeout}
        if db_api_key.model_base_url:
            client_kwargs["base_url"] = db_api_key.model_base_url
        user_client = AsyncOpenAI(**client_kwargs)
    except HTTPException as http_setup_exc:
        logger.error(f"RAG: Caught HTTPException during setup, re-raising: {http_setup_exc.detail}")
        raise http_setup_exc # Re-raise HTTP exceptions directly
    except Exception as setup_err:
        logger.error(f"Error during RAG setup (model/key/client): {setup_err}", exc_info=True)
        return fallback_response # Return fallback for setup errors
    # --- End Initial Setup Try ---

    # Main Logic
    try:
        tokenizer_model = chat_model

        # Intent & Param Extraction
        extracted_email_params = {}
        try:
            # (Keep your calculate_past_date and LLM extraction logic here)
            def calculate_past_date(days, now_iso, start_of_day=False, end_of_day=False):
                try:
                    now = datetime.fromisoformat(now_iso.replace('Z', '+00:00'))
                    target_dt = now - timedelta(days=days)
                    if start_of_day:
                        target_dt = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif end_of_day:
                        target_dt = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                    return target_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                except Exception as date_calc_err:
                    logger.error(f"Error in calculate_past_date: {date_calc_err}")
                    return "[date error]"

            now_utc_iso = datetime.now(timezone.utc).isoformat()
            try:
                example_1_start_date = calculate_past_date(days=7, now_iso=now_utc_iso)
                example_2_start_date = calculate_past_date(days=1, now_iso=now_utc_iso, start_of_day=True)
                example_2_end_date = calculate_past_date(days=1, now_iso=now_utc_iso, end_of_day=True)
            except Exception as e:
                logger.error(f"Error calculating example dates: {e}", exc_info=True)
                example_1_start_date = "[7_days_ago_error]"
                example_2_start_date = "[yesterday_start_error]"
                example_2_end_date = "[yesterday_end_error]"

            extraction_prompt_template = "Analyze the user's message to extract parameters for searching emails. Current UTC time: {now_utc_iso}.\n" \
                "User Message: \"{message}\"\n" \
                "Extract: sender, subject, start_date_utc (ISO 8601 UTC, calc from relative terms like 'last week'='past 7 days'), end_date_utc (ISO 8601 UTC), search_terms (list).\n" \
                "Respond ONLY with a JSON object. Null if not found.\n" \
                "Example 1: \"emails from jeff last week about the UOB project\" (Time: {now_utc_iso}) -> {{\"sender\": \"jeff\", \"subject\": \"UOB project\", \"start_date_utc\": \"{example_1_start_date}\", \"end_date_utc\": \"{now_utc_iso}\", \"search_terms\": [\"UOB project\"]}}\n" \
                "Example 2: \"onboarding emails from yesterday\" (Time: {now_utc_iso}) -> {{\"sender\": null, \"subject\": \"onboarding\", \"start_date_utc\": \"{example_2_start_date}\", \"end_date_utc\": \"{example_2_end_date}\", \"search_terms\": [\"onboarding\"]}}\n" \
                "JSON Response:"
            extraction_prompt = extraction_prompt_template.format(
                message=message, now_utc_iso=now_utc_iso, example_1_start_date=example_1_start_date,
                example_2_start_date=example_2_start_date, example_2_end_date=example_2_end_date
            )
            extraction_model = chat_model
            response = await user_client.chat.completions.create(
                model=extraction_model,
                messages=[
                    {"role": "system", "content": "Extract email search parameters accurately into JSON. Calculate relative dates based on current time."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw_params = json.loads(response.choices[0].message.content)
            start_date_obj, end_date_obj = None, None
            raw_start = raw_params.get("start_date_utc")
            raw_end = raw_params.get("end_date_utc")
            if raw_start:
                try:
                    start_date_obj = datetime.fromisoformat(raw_start.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid start date format from LLM: {raw_start}")
            if raw_end:
                try:
                    end_date_obj = datetime.fromisoformat(raw_end.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid end date format from LLM: {raw_end}")
            if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
                logger.warning(f"LLM returned start date {start_date_obj} after end date {end_date_obj}. Ignoring dates.")
                start_date_obj, end_date_obj = None, None
            extracted_email_params = {k: v for k, v in {
                "sender_filter": raw_params.get("sender"),
                "subject_filter": raw_params.get("subject"),
                "start_date": start_date_obj,
                "end_date": end_date_obj,
                "search_terms": raw_params.get("search_terms") if isinstance(raw_params.get("search_terms"), list) else None
            }.items() if v is not None}
        except Exception:
            extracted_email_params = {}

        # Determine query type
        if extracted_email_params.get("sender_filter") or extracted_email_params.get("subject_filter") or extracted_email_params.get("start_date"):
            source_target = "email_focused"
        else:
            # More robust keyword checking for document focus
            doc_keywords = ['policy', 'procedure', 'document', 'rate card', 'sow', 'loa', 'guideline', 'report', 'agreement', 'contract', 'spec', 'manual']
            message_lower = message.lower()
            source_target = "document_focused" if any(k in message_lower for k in doc_keywords) else "mixed"
            
        is_email_focused = source_target == "email_focused"
        # Broad email query is one that is email_focused BUT lacks specific filters (sender, subject, date)
        # and might also imply no specific search_terms were extracted or they are very generic.
        # For now, stick to the definition of email_focused lacking sender/subject/date.
        is_broad_email_query = is_email_focused and not any(
            extracted_email_params.get(k) for k in ["sender_filter", "subject_filter", "start_date"]
        )
        logger.info(f"Query Intent Analysis - Source Target: {source_target}, Is Email Focused: {is_email_focused}, Is Broad Email Query: {is_broad_email_query}")
        logger.debug(f"Extracted Email Params: {extracted_email_params}")

        # --- END: Intent Analysis & Parameter Extraction ---


        # --- START: Conditional Context Retrieval (SEQUENTIAL) ---
        retrieved_document_dicts: List[Dict[str, Any]] = [] 
        retrieved_email_dicts: List[Dict[str, Any]] = []

        # Determine dynamic MAX_EMAIL_CONTEXT_ITEMS based on query type
        if is_broad_email_query:
            MAX_EMAIL_CONTEXT_ITEMS = int(getattr(settings, 'MAX_EMAIL_CONTEXT_ITEMS_BROAD', 50))
            logger.info(f"Using BROAD email context limit: {MAX_EMAIL_CONTEXT_ITEMS}")
        else:
            MAX_EMAIL_CONTEXT_ITEMS = int(getattr(settings, 'MAX_EMAIL_CONTEXT_ITEMS_FOCUSED', 20))
            logger.info(f"Using FOCUSED email context limit: {MAX_EMAIL_CONTEXT_ITEMS}")

        logger.info("Starting SEQUENTIAL context retrieval...")

        # Retrieve Documents (if needed)
        if source_target in ["mixed", "document_focused"]:
            logger.debug("Retrieving document context sequentially...")
            try:
                 MAX_MILVUS_CONTEXT_ITEMS = int(getattr(settings, 'RAG_LLM_MILVUS_LIMIT', 20))
                 retrieved_document_dicts = await _get_milvus_context(
                     max_items=MAX_MILVUS_CONTEXT_ITEMS,
                     max_chunk_chars=MAX_CHUNK_CHARS,
                     query=message,
                     user_email=user.email
                 )
                 logger.debug(f"Sequential document retrieval finished. Retrieved {len(retrieved_document_dicts)} documents.")
            except Exception as doc_err:
                 logger.error(f"Error during sequential document retrieval: {doc_err}", exc_info=True)
                 retrieved_document_dicts = [] # Ensure it's empty on error
                 # Add a log if RAG was supposed to get documents but failed
                 if source_target in ["mixed", "document_focused"]:
                     logger.warning("Document retrieval was expected but failed. Proceeding without document context.")

        # Retrieve Emails (if needed)
        if source_target in ["mixed", "email_focused"]:
            logger.debug("Retrieving email context sequentially...")
            try:
                 retrieved_email_dicts = await _get_email_context(
                     max_items=MAX_EMAIL_CONTEXT_ITEMS,
                     max_chunk_chars=MAX_CHUNK_CHARS,
                     user_client=user_client,
                     search_params=extracted_email_params,
                     user_email=user.email
                 )
                 logger.debug(f"Sequential email retrieval finished. Retrieved {len(retrieved_email_dicts)} emails.")
            except Exception as email_err:
                 logger.error(f"Error during sequential email retrieval: {email_err}", exc_info=True)
                 retrieved_email_dicts = [] # Ensure it's empty on error
                 # Add a log if RAG was supposed to get emails but failed
                 if source_target in ["mixed", "email_focused"]:
                     logger.warning("Email retrieval was expected but failed. Proceeding without email context.")

        logger.info("Finished SEQUENTIAL context retrieval.")
        # --- END: Conditional Context Retrieval (SEQUENTIAL) ---

        logger.critical("!!! POINTER: Right before Process Email Context block !!!") # ADDED

        # --- START: Process Email Context ---
        final_email_context_str = "No relevant emails found or search skipped."

        if retrieved_email_dicts:
            # REMOVED DEBUG LOG: logger.critical("!!! POINTER: Entered 'if retrieved_email_dicts:' block !!!")
            
            logger.debug(f"Processing {len(retrieved_email_dicts)} retrieved email dictionaries.") # Keep standard debug log
            # Helper to format a single email dictionary
            def _format_single_email(email: Dict[str, Any], max_len: int) -> str:
                def _truncate_text(text: str, max_l: int) -> str:
                    text_str = str(text) if text is not None else ''
                    if len(text_str) > max_l: return text_str[:max_l] + "... [TRUNCATED]"; return text_str

                granularity = email.get('granularity', 'full_message')
                text_content = ""
                entry_type = "Email (Unknown Granularity)"
                if granularity == 'full_message':
                    text_content = email.get('body_text')
                    entry_type = "Email Reply/Body"
                elif granularity == 'quoted_message':
                    text_content = email.get('quoted_raw_text')
                    entry_type = "Quoted Section"
                else:
                    text_content = email.get('body_text') or email.get('quoted_raw_text')

                # Safely access keys with defaults
                return (
                    f"Email ID: {email.get('message_id', 'N/A')}\n"
                    f"Type: {entry_type}\n"
                    f"Received: {email.get('received_datetime_utc', 'N/A')}\n"
                    f"Sender: {email.get('sender', 'N/A')}\n"
                    f"Subject: {email.get('subject', 'N/A')}\n"
                    f"Tags: {email.get('generated_tags', 'N/A')}\n"
                    f"Content: {_truncate_text(str(text_content) if text_content else '', max_len)}"
                )

            # Estimate tokens for the *full* potential context if NOT summarized
            # --- RESTORED --- 
            full_potential_email_context = "\n\n---\n\n".join([_format_single_email(email, MAX_CHUNK_CHARS) for email in retrieved_email_dicts])
            full_email_tokens = count_tokens(full_potential_email_context, tokenizer_model)
            logger.info(f"Estimated tokens for full email context ({len(retrieved_email_dicts)} emails): {full_email_tokens}")
            # REMOVED Dummy value & warning log
            # full_email_tokens = 0 
            # logger.warning("DEBUG: Bypassing initial token count for email context.")
            # --- END RESTORED ---

            # Check if multi-stage summarization is needed
            # --- RESTORED --- 
            trigger_summarization = is_broad_email_query and full_email_tokens > MULTI_STAGE_EMAIL_TOKEN_THRESHOLD
            # REMOVED forced False & warning log
            # trigger_summarization = False 
            # logger.warning(f"DEBUG: Forcing trigger_summarization={trigger_summarization}")
            # --- END RESTORED ---

            if trigger_summarization:
                # This block should now execute if conditions are met
                # REMOVED pass statement
                logger.warning(f"Multi-stage email summarization triggered. Token count {full_email_tokens} > threshold {MULTI_STAGE_EMAIL_TOKEN_THRESHOLD}. Query: '{message}'")

                # Split emails into batches
                email_batches = [
                    retrieved_email_dicts[i:i + EMAIL_SUMMARY_BATCH_SIZE]
                    for i in range(0, len(retrieved_email_dicts), EMAIL_SUMMARY_BATCH_SIZE)
                ]
                logger.info(f"Created {len(email_batches)} email batches for summarization (batch size: {EMAIL_SUMMARY_BATCH_SIZE}).")

                # Run summarization tasks concurrently
                summary_tasks = [
                    _summarize_email_batch(batch, message, user_client, chat_model, max_chars_per_email=1000)
                    for batch in email_batches
                ]
                try:
                    batch_summaries = await asyncio.gather(*summary_tasks)
                    combined_summaries = "\n\n---\n\n".join(filter(None, batch_summaries))
                    final_email_context_str = f"<Summarized Email Context (Multiple Batches, {len(retrieved_email_dicts)} emails total)>\n{combined_summaries}\n</Summarized Email Context>"
                    logger.info(f"Multi-stage summarization completed. Final summary token count: {count_tokens(final_email_context_str, tokenizer_model)}")
                except Exception as e_summary:
                    logger.error(f"Error during concurrent email batch summarization: {e_summary}", exc_info=True)
                    final_email_context_str = "<Error during multi-stage email summarization>"
            else:
                # Removed the verbose loop logging, keep the main info log
                logger.info(f"Using direct email context (Limit: {len(retrieved_email_dicts)} items). Summarization not triggered (Broad Query={is_broad_email_query}, Tokens={full_email_tokens}, Threshold={MULTI_STAGE_EMAIL_TOKEN_THRESHOLD}).")
                direct_context_entries = [_format_single_email(email, MAX_CHUNK_CHARS) for email in retrieved_email_dicts]
                final_email_context_str = "<User Email Context>\n" + "\n\n---\n\n".join(direct_context_entries) + "\n</User Email Context>"
                # Removed redundant token counting/logging here, it happens later in budgeting
        else: # If retrieved_email_dicts is empty
            final_email_context_str = "No email context was retrieved or searched for."
            logger.info("No email dictionaries were retrieved to process for context.")


        # --- START: Process Document Context ---
        final_document_context_str = "No document context was retrieved or searched for."
        if retrieved_document_dicts:
            logger.debug(f"Processing {len(retrieved_document_dicts)} retrieved document dictionaries for context.")
            document_context_parts = []
            for i, doc in enumerate(retrieved_document_dicts):
                content = doc.get('content', '') # Assuming 'content' key holds the text
                truncated_content = truncate_text_by_tokens(content, tokenizer_model, MAX_DOCUMENT_CONTEXT_CHARS // 3) # Rough token to char conversion
                # Alternative: truncate by characters directly if MAX_DOCUMENT_CONTEXT_CHARS is char based
                # truncated_content = content[:MAX_DOCUMENT_CONTEXT_CHARS] + ("...[TRUNCATED]" if len(content) > MAX_DOCUMENT_CONTEXT_CHARS else "")

                source_info = doc.get('metadata', {}).get('source', f"Document {i+1}") # Example: get source from metadata
                score = doc.get('score', 'N/A')
                doc_entry = f"Source: {source_info} (Score: {score})\nContent:\n{truncated_content}"
                document_context_parts.append(doc_entry)
            
            if document_context_parts:
                final_document_context_str = "<Retrieved Document Context>\n" + "\n\n---\n\n".join(document_context_parts) + "\n</Retrieved Document Context>"
            else:
                final_document_context_str = "Retrieved documents had no content to process."
                logger.info("Retrieved document dictionaries were empty or had no processable content.")
        else:
            logger.info("No document dictionaries were retrieved to process for context.")
        # --- END: Process Document Context ---


        # Token Budgeting & Context Construction
        logger.info("Starting token budgeting and context construction...")
        system_prompt_template = _build_system_prompt() # Get the template which includes placeholder
        # Format chat history, applying token limit
        formatted_history = _format_chat_history(chat_history, model=tokenizer_model, max_tokens=MAX_CHAT_HISTORY_TOKENS)
        
        base_prompt_tokens = count_tokens(system_prompt_template.replace("<RAG_CONTEXT_PLACEHOLDER>", ""), tokenizer_model)
        history_tokens = count_tokens(formatted_history, tokenizer_model)
        query_tokens = count_tokens(message, tokenizer_model)
        
        # Calculate remaining tokens for RAG context
        remaining_tokens_for_rag = MAX_TOTAL_TOKENS - (base_prompt_tokens + history_tokens + query_tokens + RESPONSE_BUFFER_TOKENS)
        logger.info(f"Token budget: Total={MAX_TOTAL_TOKENS}, BasePrompt={base_prompt_tokens}, History={history_tokens}, Query={query_tokens}, ResponseBuffer={RESPONSE_BUFFER_TOKENS} => Remaining for RAG: {remaining_tokens_for_rag}")

        context_parts = []
        current_rag_tokens = 0

        # Add Document Context First (often more general, can be prioritized or ordered based on strategy)
        if remaining_tokens_for_rag > 0 and final_document_context_str and final_document_context_str != "No document context was retrieved or searched for." and final_document_context_str != "Retrieved documents had no content to process.":
            doc_tokens = count_tokens(final_document_context_str, tokenizer_model)
            if doc_tokens <= remaining_tokens_for_rag:
                context_parts.append(final_document_context_str)
                current_rag_tokens += doc_tokens
                remaining_tokens_for_rag -= doc_tokens
                logger.info(f"Added document context ({doc_tokens} tokens). Remaining for RAG: {remaining_tokens_for_rag}")
            else:
                truncated_doc_context = truncate_text_by_tokens(final_document_context_str, tokenizer_model, remaining_tokens_for_rag)
                context_parts.append(truncated_doc_context)
                truncated_doc_tokens = count_tokens(truncated_doc_context, tokenizer_model)
                current_rag_tokens += truncated_doc_tokens
                remaining_tokens_for_rag -= truncated_doc_tokens
                logger.warning(f"Truncated document context from {doc_tokens} to {truncated_doc_tokens} tokens due to budget. Remaining for RAG: {remaining_tokens_for_rag}")
        
        # Add Email Context
        if remaining_tokens_for_rag > 0 and final_email_context_str and final_email_context_str != "No email context was retrieved or searched for.":
            email_tokens = count_tokens(final_email_context_str, tokenizer_model)
            if email_tokens <= remaining_tokens_for_rag:
                context_parts.append(final_email_context_str)
                current_rag_tokens += email_tokens
                # remaining_tokens_for_rag -= email_tokens # Not strictly needed to track beyond here for this var
                logger.info(f"Added email context ({email_tokens} tokens).")
            else:
                truncated_email_context = truncate_text_by_tokens(final_email_context_str, tokenizer_model, remaining_tokens_for_rag)
                context_parts.append(truncated_email_context)
                truncated_email_tokens = count_tokens(truncated_email_context, tokenizer_model)
                current_rag_tokens += truncated_email_tokens
                logger.warning(f"Truncated email context from {email_tokens} to {truncated_email_tokens} tokens due to budget.")

        rag_context_str = "\n\n".join(context_parts) if context_parts else "No context could be provided within token limits."
        if not context_parts:
             logger.warning("No RAG context could be assembled within token limits or none was retrieved.")
        
        final_system_prompt = system_prompt_template.replace("<RAG_CONTEXT_PLACEHOLDER>", rag_context_str)
        
        logger.debug(f"Final System Prompt (excluding history/query, first 200 chars):\n{final_system_prompt[:200]}...")
        final_prompt_messages = [{"role": "system", "content": final_system_prompt}]
        if formatted_history: # Add history if it exists
            final_prompt_messages.append({"role": "user", "content": f"Previous conversation history:\n{formatted_history}"}) # Simplistic history injection
            # A more robust approach would interleave user/assistant turns correctly.
            # For now, just prepend it.
        final_prompt_messages.append({"role": "user", "content": message}) # Current user message

        # --- Final LLM Call ---
        logger.info(f"Making final LLM call to {provider}/{chat_model} with {len(final_prompt_messages)} messages.")
        # Log total tokens being sent to LLM for debugging
        total_final_prompt_tokens = sum(count_tokens(msg["content"], tokenizer_model) for msg in final_prompt_messages)
        logger.info(f"Estimated total tokens in final prompt to LLM: {total_final_prompt_tokens} (Max allowed: {MAX_TOTAL_TOKENS})")
        if total_final_prompt_tokens > MAX_TOTAL_TOKENS:
            logger.error(f"CRITICAL: Final prompt token count ({total_final_prompt_tokens}) EXCEEDS model max tokens ({MAX_TOTAL_TOKENS}). LLM call will likely fail.")
            # This indicates a flaw in budgeting logic if it happens.

        try:
            llm_response = await user_client.chat.completions.create(
                model=chat_model,
                messages=final_prompt_messages,
                temperature=float(getattr(settings, 'OPENAI_TEMPERATURE', 0.1)), # Make temperature configurable
                max_tokens=RESPONSE_BUFFER_TOKENS  # Ensure LLM has enough buffer to respond
            )
            response_content = llm_response.choices[0].message.content.strip()
            logger.info(f"RAG response generated successfully by {chat_model}.")
            logger.debug(f"LLM Response (first 100 chars): {response_content[:100]}...")
            return response_content
        except RateLimitError as rle:
            logger.error(f"OpenAI Rate Limit Error during RAG generation: {rle}", exc_info=True)
            # Consider more specific user feedback for rate limits
            return "I'm currently experiencing high demand. Please try again in a few moments."
        except Exception as llm_call_err:
            logger.error(f"Error during final LLM call for RAG: {llm_call_err}", exc_info=True)
            return fallback_response # Return fallback for LLM call errors

    except HTTPException as http_exc: # Catch HTTPExceptions from setup or elsewhere
        logger.error(f"RAG: Caught HTTPException, re-raising: {http_exc.detail}", exc_info=True)
        raise http_exc # Re-raise to be handled by FastAPI
    except Exception as e: # General catch-all for unexpected errors in the main logic
        logger.error(f"Unexpected error in generate_openai_rag_response: {e}", exc_info=True)
        return fallback_response # Return fallback for any other unhandled error
    # Ensure a string is always returned (though covered by above, defensive)
    # This line should ideally not be reached if logic is correct.
    logger.error("RAG function reached unexpected end. Returning fallback.")
    return fallback_response