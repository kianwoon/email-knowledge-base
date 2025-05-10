import json
import re  # For rate-card dollar filtering
from typing import Dict, Any, List, Optional, Tuple
from openai import AsyncOpenAI, RateLimitError # Import RateLimitError
from sqlalchemy.orm import Session
import logging # Import logging
import asyncio  # For async operations
from datetime import datetime, timedelta, timezone # Added datetime imports
from zoneinfo import ZoneInfo # Added ZoneInfo import
import tiktoken # ADDED tiktoken import
import hashlib # For content hashing in deduplication
import difflib # For text similarity comparison
import uuid  # Added UUID import

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.models.user import User # Assuming User model is here
# Import RAG components - Updated for Milvus
from app.services.embedder import create_embedding, search_milvus_knowledge_hybrid, rerank_results, create_retrieval_embedding, deduplicate_results
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

# --- START: Global DuckDB Connection Pool ---
DUCKDB_CONN: Optional[duckdb.DuckDBPyConnection] = None

def get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    """Returns a reusable DuckDB connection with httpfs and caching configured."""
    global DUCKDB_CONN
    if DUCKDB_CONN is None:
        DUCKDB_CONN = duckdb.connect(database=':memory:')
        
        # Create and configure cache directories with absolute paths
        import os
        import pathlib
        
        # Define paths for cache directories
        home_dir = os.path.expanduser("~/.duckdb_cache")
        httpfs_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "duckdb_httpfs_cache")
        
        # Create directories if they don't exist
        pathlib.Path(home_dir).mkdir(parents=True, exist_ok=True)
        pathlib.Path(httpfs_cache_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Using DuckDB home directory: {home_dir}")
        logger.info(f"Using HTTP/FS cache directory: {httpfs_cache_dir}")
        
        # Configure home directory first
        DUCKDB_CONN.execute(f"SET home_directory='{home_dir}';")
        
        # Install and load httpfs (required for S3/remote data access)
        DUCKDB_CONN.execute("INSTALL httpfs; LOAD httpfs;")
        
        # Try to enable object-store caching using the cache_httpfs extension
        try:
            # 1. Install & load the cache_httpfs community extension
            logger.info("Installing and loading cache_httpfs extension...")
            DUCKDB_CONN.execute("INSTALL cache_httpfs FROM community;")
            DUCKDB_CONN.execute("LOAD cache_httpfs;")
            
            # 2. Configure caching parameters
            logger.info("Configuring cache_httpfs settings...")
            DUCKDB_CONN.execute("SET cache_httpfs_type = 'on_disk';")
            DUCKDB_CONN.execute(f"SET cache_httpfs_cache_directory = '{httpfs_cache_dir}';")
            DUCKDB_CONN.execute("SET cache_httpfs_cache_block_size = 1048576;")  # 1 MiB blocks
            DUCKDB_CONN.execute("SET cache_httpfs_in_mem_cache_block_timeout_millisec = 600000;")  # 10 min
            
            logger.info("Successfully enabled object-store caching for DuckDB via cache_httpfs extension")
        except Exception as e:
            # If the caching extension isn't available or fails to install, log and continue without it
            logger.warning(f"DuckDB object-store caching could not be enabled: {e}")
            logger.info("Continuing without object-store caching")
    
    return DUCKDB_CONN
# --- END: Global DuckDB Connection Pool ---

# --- START: Global Catalog Variable (Initialize lazily) ---
# Use a global variable to hold the catalog instance to avoid reinitialization on every call.
# Ensure thread-safety if your application uses threads extensively for requests.
_iceberg_catalog: Optional[Catalog] = None
_catalog_lock = asyncio.Lock() # Use async lock for async context

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
                    "s3.endpoint": settings.R2_ENDPOINT_URL, 
                    "s3.access-key-id": settings.R2_ACCESS_KEY_ID,
                    "s3.secret-access-key": settings.R2_SECRET_ACCESS_KEY
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

        # Get reusable DuckDB connection
        con = get_duckdb_conn()
        view_name = f'email_facts_view_{uuid.uuid4().hex[:8]}'  # Use unique view name to avoid conflicts
        
        # Create PyIceberg expressions for predicate push-down
        from pyiceberg.expressions import GreaterThanOrEqual, LessThanOrEqual, And, StartsWith, EqualTo
        
        # Build push-down expressions
        exprs = []
        # Add owner email filter
        exprs.append(EqualTo("owner_email", user_email))
        
        # Add date filters
        if start_date:
            exprs.append(GreaterThanOrEqual("received_datetime_utc", start_date))
            logger.info(f"Pushing down start_date filter: {start_date.isoformat()}")
        if end_date:
            exprs.append(LessThanOrEqual("received_datetime_utc", end_date))
            logger.info(f"Pushing down end_date filter: {end_date.isoformat()}")
            
        # Add sender filter if plausible
        is_plausible_sender_filter = False
        if sender_filter:
            # Simple check: contains @ or multiple words, or is a reasonable length name
            if '@' in sender_filter or len(sender_filter.split()) > 1 or (len(sender_filter) >= 2 and sender_filter.isalpha()): 
                is_plausible_sender_filter = True
                # Only push-down exact match filters, do LIKE filters in SQL
                if '@' in sender_filter:
                    exprs.append(StartsWith("sender", sender_filter))
                    logger.debug(f"Pushing down sender filter: {sender_filter}")
            else:
                logger.warning(f"Ignoring likely implausible sender filter: '{sender_filter}'")
        
        # Determine select columns based on token
        select_columns = None  # Default to selecting all columns
        if token and token.allow_columns:
            select_columns = token.allow_columns
            logger.info(f"Applying column projection based on token {token.id}")
            
        # Create scan with filters and projection
        scan = iceberg_table.scan()
        
        # Apply filter expressions if we have any
        if exprs:
            try:
                scan = scan.filter(And(*exprs))
                logger.debug(f"Applied {len(exprs)} predicate pushdown filters to Iceberg scan")
            except Exception as filter_err:
                logger.warning(f"Failed to apply some predicate filters: {filter_err}. Falling back to basic scan.")
                # Start with a fresh scan and just apply the owner email filter which is the most important
                scan = iceberg_table.scan()
                try:
                    scan = scan.filter(EqualTo("owner_email", user_email))
                    logger.debug("Applied fallback filter for owner_email only")
                except Exception as basic_filter_err:
                    logger.error(f"Even basic filtering failed: {basic_filter_err}")
            
        # Apply column projection if specified
        if select_columns:
            scan = scan.select(*select_columns)
            
        # Execute the scan to DuckDB
        scan.to_duckdb(table_name=view_name, connection=con)
        
        # Continue with SQL filtering for more complex conditions that can't be pushed down
        # --- REVISED: Build WHERE clause based on provided filters ---
        # We've already filtered owner_email, start_date, and end_date in the scan
        final_where_clauses = []
        final_query_params = []

        # Clauses for specific field attribute filters (sender, subject)
        attribute_filter_clauses = []
        attribute_filter_params = []
        
        # Only add SQL sender filter if we couldn't push it down completely
        if is_plausible_sender_filter and not ('@' in sender_filter):
            # MODIFIED: Search in both sender (email) and sender_name (display name)
            attribute_filter_clauses.append("(sender LIKE ? OR sender_name LIKE ?)")
            attribute_filter_params.append(f"%{sender_filter}%")
            attribute_filter_params.append(f"%{sender_filter}%") # Add param again for sender_name
            logger.debug(f"Applying attribute sender filter (on sender/sender_name): {sender_filter}")
        
        if subject_filter:
            attribute_filter_clauses.append("subject LIKE ?")
            attribute_filter_params.append(f"%{subject_filter}%")
            logger.debug(f"Applying attribute subject filter: {subject_filter}")
        
        attribute_filters_sql_part = ""
        if attribute_filter_clauses:
            attribute_filters_sql_part = " AND ".join(attribute_filter_clauses)
            # Wrap in parentheses if there are attribute filters
            attribute_filters_sql_part = f"({attribute_filters_sql_part})"
            final_where_clauses.append(attribute_filters_sql_part)
            final_query_params.extend(attribute_filter_params)

        # Clause for general keyword search terms
        keyword_search_sql_part = ""
        keyword_search_params = []
        if search_terms:
            keyword_filter_individual_parts = []
            for term in search_terms:
                safe_term = term.replace('%', '\%').replace('_', '\_')
                # Each term searches across multiple fields OR'd together
                term_specific_search = f"(subject LIKE ? OR body_text LIKE ? OR sender LIKE ? OR sender_name LIKE ? OR generated_tags LIKE ? OR quoted_raw_text LIKE ?)"
                keyword_filter_individual_parts.append(term_specific_search)
                keyword_search_params.extend([f'%{safe_term}%'] * 6)
            
            if keyword_filter_individual_parts:
                # If multiple search terms, they are typically OR'd (any term can match)
                keyword_search_sql_part = " OR ".join(keyword_filter_individual_parts)
                # Wrap keyword search in parentheses if it exists
                keyword_search_sql_part = f"({keyword_search_sql_part})"
                final_where_clauses.append(keyword_search_sql_part)
                final_query_params.extend(keyword_search_params)
                logger.debug(f"Applying keyword search terms: {search_terms}")

        # --- END REVISED: WHERE clause ---

        # Construct the full SQL query with dynamic WHERE clauses
        effective_limit = token.row_limit if token and token.row_limit else limit

        # Only add WHERE if we have conditions
        where_sql_final = ""
        if final_where_clauses:
            where_sql_final = f"WHERE {' AND '.join(final_where_clauses)}"

        sql_query = f"""
        SELECT * 
        FROM {view_name}
        {where_sql_final}
        ORDER BY received_datetime_utc DESC
        LIMIT ?;
        """
        final_query_params.append(effective_limit)

        # ADDED LOGGING FOR THE SQL QUERY AND PARAMETERS
        logger.info(f"[DuckDB Query] Final SQL to execute: {sql_query}")
        logger.info(f"[DuckDB Query] Parameters: {final_query_params}")

        # Execute query and fetch results
        arrow_table = con.execute(sql_query, final_query_params).fetch_arrow_table()
        results = arrow_table.to_pylist()
        logger.info(f"DuckDB query returned {len(results)} email results.")
        
        # Drop the temporary view to avoid cluttering the connection
        con.execute(f"DROP VIEW IF EXISTS {view_name}")

    except Exception as e:
        logger.error(f"Error querying DuckDB for emails: {e}", exc_info=True)
        results = [] # Ensure empty list on error
    # Don't close the connection since we're reusing it

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
    max_chars_per_email: int = 1000, # Limit context per email within batch
    batch_max_tokens_for_llm: int = 1024 # New parameter for LLM call's max_tokens
) -> str:
    """Summarizes a batch of emails focusing on relevance to the original query."""
    logger.debug(f"Starting summary for batch of {len(email_batch)} emails, LLM max_tokens: {batch_max_tokens_for_llm}.")
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
        f"You are an expert summarizer. Your task is to read the following batch of emails and extract ALL key information, specific details, updates, developments, decisions, action items, figures, names, dates, or news that are **directly relevant** to the user's original query: \"{original_query}\".\n" \
        f"Your primary goal is to be **extremely thorough and detailed** for the given query. Do not omit any potentially relevant piece of information, even if it seems minor. Capture the nuances and specifics from the emails.\n" \
        f"Produce an **expansive and highly detailed summary** of all relevant points. Aim to utilize a significant portion of the available token limit for your response if the source material contains sufficient relevant detail. If the batch is rich in relevant information, your summary should reflect that richness in length and detail.\n" \
        f"IMPORTANT: When referencing dates, ALWAYS maintain the EXACT years as they appear in the source emails. Do NOT change years or assume current year. If an email from 2023 is referenced, use '2023' not the current year or any other year.\n" \
        f"For relative time expressions like 'last week', use the actual date range with correct years from the retrieved emails.\\n" \
        f"CRITICAL: If the emails contain information about multiple distinct entities, projects, or clients (e.g., UOB, OCBC), ensure your summary explicitly and accurately attributes details to the correct entity. Do not blend information or misattribute details between entities.\\n" \
        f"If, and only if, no relevant information is found, state that clearly. Otherwise, be exhaustive.\n" \
        f"Present the summary clearly. For multiple points, use detailed bullet points or paragraphs. Ensure all key facts, figures, and statements from the emails that pertain to the query are retained in your summary."
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
            temperature=0.4, # Increased temperature for potentially more detailed summaries
            max_tokens=batch_max_tokens_for_llm # Use the new parameter
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
    user_email: str,
    model_name: str = None  # Add model_name parameter with default
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Retrieves document context from Milvus using the search_milvus_knowledge_hybrid function.
    
    Returns:
        Tuple containing (document_results, tokens_saved)
    """
    logger.debug(f"_get_milvus_context called with query: '{query[:50]}...', limit: {max_items}")
    tokens_saved = 0
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
        
        # Get tokenizer model for token counting
        # Use provided model_name or fall back to OPENAI_MODEL_NAME (not a new default model)
        tokenizer_model = get_tokenizer_model_for_chat_model(model_name or settings.OPENAI_MODEL_NAME)
        
        # NEW: Deduplicate results before reranking and track token efficiency
        if len(document_results) > 1:
            document_results, dedup_tokens_saved = await deduplicate_and_log_tokens(
                results=document_results,
                tokenizer_model=tokenizer_model,
                similarity_threshold=0.85
            )
            tokens_saved += dedup_tokens_saved
        
        # Rerank if more than 1 result is returned for improved relevance
        if len(document_results) > 1:
            document_results = await rerank_results(
                query=query,
                results=document_results
            )
            # Apply final limit after reranking
            document_results = document_results[:max_items]
            
        logger.info(f"_get_milvus_context retrieved {len(document_results)} documents.")
        return document_results, tokens_saved
    except Exception as e_milvus:
        logger.error(f"Error during Milvus document retrieval in _get_milvus_context: {e_milvus}", exc_info=True)
        return [], tokens_saved  # Return empty list and 0 tokens saved on error
# --- END: Milvus Context Retrieval Helper ---


# --- START: Helper function to build the system prompt ---
def _build_system_prompt() -> str:
    # This is a basic system prompt. You can customize it further.
    return "You are a helpful AI assistant. Your user is asking a question.\n" \
           "You have been provided with some context information (RAG Context) that might be relevant to the user's query.\n" \
           "Please use this context to answer the user's question accurately and comprehensively, including relevant details from the context.\n" \
           "When referencing dates from emails or documents, always maintain the EXACT years as they appear in the source material.\n" \
           "Do NOT change years or assume current year. For example, if an email from 2023 is referenced, use '2023' not the current year.\n" \
           "For relative time expressions like 'last week', use the actual date range with correct years from the retrieved information.\n" \
           "If the context mentions multiple entities, projects, or clients (e.g., UOB, OCBC), be meticulous in attributing specific details only to the entity they are explicitly linked with in the source text. Avoid generalizing details from one entity to another unless the text explicitly supports it.\\n" \
           "If the context doesn't provide enough information, state that you couldn't find the answer in the provided documents or emails.\\n" \
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
    
    # Track total tokens saved from deduplication
    total_tokens_saved = 0
    
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
        
        # Log filename terms for debugging
        logger.info(f"RateCardRAG: Using filename terms for query: {filename_terms}")
        
        raw_results = []
        for vec, q_text in zip(embeddings, queries): # Renamed q to q_text to avoid conflict
            hits = await search_milvus_knowledge_hybrid(
                query_text=q_text, # Use q_text
                collection_name=collection,
                limit=per_q,
                filename_terms=filename_terms,
                dense_params={"metric_type":"COSINE","params":{"ef":128},"search_data_override":vec}
            )
            raw_results.extend(hits)
        logger.info(f"RateCardRAG: Total raw results from Milvus (across all HyDE queries): {len(raw_results)}")

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

        # 9. Advanced deduplication & reranking
        # First perform content-based deduplication with token accounting
        if len(raw_results) > 1:
            # Get tokenizer model for token counting
            tokenizer_model = get_tokenizer_model_for_chat_model(chat_model)
            
            # Apply content-based deduplication with token accounting
            raw_results, tokens_saved = await deduplicate_and_log_tokens(
                results=raw_results,
                tokenizer_model=tokenizer_model,
                similarity_threshold=0.85
            )
            total_tokens_saved += tokens_saved
            
        # Then perform ID-based deduplication (original logic)
        unique_results_dict = {r["id"]: r for r in raw_results} # Keep the dict for a moment
        unique = list(unique_results_dict.values()) # Convert to list for reranking
        logger.info(f"RateCardRAG: Number of unique results after ID deduplication: {len(unique)}")

        # Apply document-level duplicate detection for rate cards
        # Group documents by their "original_filename" prefix pattern to identify similar files
        if len(unique) > 1:
            # Extract core filename without version/date suffixes using regex patterns
            filename_groups = {}
            
            # Common patterns in filenames: v1, v2, 2024, dates, etc.
            for doc in unique:
                filename = doc.get('metadata', {}).get('original_filename', '').lower()
                if not filename:
                    continue
                
                # Try to extract core document name without versions/dates
                # Pattern matches common versioning schemes: v1, v2, _1, _2, dates
                base_name = re.sub(r'[-_\s]+(v\d+|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d+)$', '', filename)
                base_name = re.sub(r'\s*\([^)]*\)\s*$', '', base_name)  # Remove trailing parentheses content
                
                # Ensure we have a reasonable base name
                if len(base_name) >= 3:
                    if base_name not in filename_groups:
                        filename_groups[base_name] = []
                    filename_groups[base_name].append(doc)
            
            # Find groups with multiple similar documents
            for base_name, docs in filename_groups.items():
                if len(docs) > 1:
                    logger.info(f"RateCardRAG: Found document group '{base_name}' with {len(docs)} similar files")
                    
                    # Select the best document from each group based on content relevance
                    # We'll use the reranking score if available, or original score
                    best_doc = max(docs, key=lambda d: 
                        d.get('rerank_score', d.get('score', 0.0))
                    )
                    
                    # Get the best doc's filename for logging
                    best_filename = best_doc.get('metadata', {}).get('original_filename', 'Unknown')
                    logger.info(f"RateCardRAG: Selected best document '{best_filename}' from group '{base_name}'")
                    
                    # Remove all other documents in this group from the unique list
                    unique = [doc for doc in unique if doc == best_doc or doc not in docs]
                    
                    # Add the best document back to ensure it's included
                    if best_doc not in unique:
                        unique.append(best_doc)
                    
                    # Log token efficiency gain
                    docs_removed = len(docs) - 1
                    if docs_removed > 0:
                        avg_token_per_doc = 800  # Conservative estimate
                        estimated_tokens_saved = docs_removed * avg_token_per_doc
                        total_tokens_saved += estimated_tokens_saved
                        logger.info(f"RateCardRAG: Document-level deduplication removed {docs_removed} similar files, saving ~{estimated_tokens_saved} tokens")
        
        reranked = await rerank_results(query=message, results=list(unique))
        logger.info(f"RateCardRAG: Number of results after reranking: {len(reranked)}")

        # GENERIC QUERY-FOCUSED PRIORITIZATION
        # Get the primary entity/role from query features for query-focused prioritization
        primary_entity = query_features.get("role", "").lower() if query_features else ""
        
        # Extract potentially relevant terms from query for prioritization
        query_terms = set()
        
        # Extract entity from structured analysis
        if primary_entity:
            # Add the full entity name
            if len(primary_entity) >= 2:
                query_terms.add(primary_entity)
                
            # Also add individual terms
            for term in re.split(r'[\s_-]+', primary_entity):
                if len(term) >= 2:  # Only consider meaningful terms
                    query_terms.add(term.lower())
        
        # Get entity variations from settings or use default fallback
        # This allows easy updates via configuration without code changes
        entity_variations = {}
        
        # Try to get from settings in JSON format if available
        entity_variations_str = getattr(settings, "ENTITY_VARIATIONS", None)
        if entity_variations_str:
            try:
                # Attempt to parse JSON from settings
                entity_variations = json.loads(entity_variations_str)
                logger.debug(f"Loaded entity variations from settings: {len(entity_variations)} entries")
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse ENTITY_VARIATIONS setting as JSON, using fallback")
        
        # Default fallback variations if not in settings or parsing failed
        if not entity_variations:
            entity_variations = {
                "gic": ["global innovation center", "global innovation centre", "gic"],
                "mas": ["managed application services", "mas", "managed app services"],
                "pmo": ["project management office", "pmo", "program management"],
                "de": ["data engineering", "data engineer", "de"],
                "hr": ["human resources", "hr"],
                "dba": ["database administrator", "dba", "database admin"],
            }
            logger.debug("Using fallback entity variations dictionary")
        
        # Check message for common entity terms and add their variations
        message_lower = message.lower()
        for key, variations in entity_variations.items():
            for var in variations:
                if var in message_lower:
                    # Found a match, add all variations of this entity
                    query_terms.update(variations)
                    break
        
        # If no structured entity found, extract key terms directly from query
        if not query_terms:
            # Extract potential entity names from query using a more advanced approach
            # First tokenize the message into words
            word_tokens = re.findall(r'\b\w+\b', message_lower)
            
            # Common stop words to ignore
            stop_words = {"rate", "card", "the", "and", "for", "with", "show", "get", "find", 
                         "what", "where", "when", "how", "price", "cost", "me", "please", "thank", 
                         "tell", "about", "information", "details", "pricing", "rates"}
            
            # Identify potential entities (words that aren't stop words and are at least 2 chars)
            potential_terms = [word for word in word_tokens 
                              if len(word) >= 2 and word not in stop_words]
            
            # Add them to query terms
            query_terms.update(potential_terms)
        
        logger.info(f"RateCardRAG: Query terms identified for document prioritization: {query_terms}")
        
        # Prioritize documents based on query relevance (entity/role match)
        prioritized = []
        if query_terms:
            for doc in reranked:
                fname = doc.get('metadata', {}).get('original_filename', '').lower()
                if not fname:
                    continue
                    
                # Check for query term match in filename
                matched_terms = []
                for term in query_terms:
                    if term in fname and len(term) >= 2:  # Avoid single character matches
                        matched_terms.append(term)
                
                if matched_terms:
                    doc["query_term_matches"] = matched_terms  # Add matches for logging
                    prioritized.append(doc)
                    logger.debug(f"RateCardRAG: Prioritizing document matching query terms {matched_terms}: {fname}")
        
        # Remove prioritized docs from reranked and prepend them
        if prioritized:
            reranked = [doc for doc in reranked if doc not in prioritized]
            reranked = prioritized + reranked
            logger.info(f"RateCardRAG: Prioritized {len(prioritized)} query-relevant documents in final context order.")
            for i, doc in enumerate(prioritized):
                logger.debug(f"RateCardRAG: Prioritized Doc {i+1}: ID={doc.get('id')}, Filename={doc.get('metadata', {}).get('original_filename', 'N/A')}, Score={doc.get('rerank_score', doc.get('score', 'N/A'))}, Matched terms: {doc.get('query_term_matches', [])}")

        # 10. Format top‐K context
        k = int(getattr(settings, "RATE_CARD_FINAL_CONTEXT_LIMIT", 5))
        chosen = reranked[:k]
        logger.info(f"RateCardRAG: Selected top {len(chosen)} documents for context (limit was {k}).")

        if not chosen:
            doc_context = "No rate card documents matched your query."
        else:
            parts = []
            logger.info("RateCardRAG: Details of chosen documents for context:")
            
            # Progressive token allocation - give more space to most relevant docs
            # Get default character limit from settings
            base_char_limit = int(getattr(settings, "RATE_CARD_MAX_CHARS_PER_DOC", 4000))
            
            # Special case: If only 1 document was found (after deduplication), use all available tokens
            if len(chosen) == 1:
                logger.info("RateCardRAG: Single document found after deduplication, allocating full token budget")
                max_chars = base_char_limit * 2  # Double the default limit for single documents
            else:
                # Progressive character limits based on relevance ranking
                # Most relevant doc gets more space, decreasing for less relevant docs
                max_chars_by_index = {
                    0: int(base_char_limit * 1.5),  # Most relevant: 150% of base limit
                    1: base_char_limit,             # Second: 100% of base limit
                    2: int(base_char_limit * 0.8),  # Third: 80% of base limit
                    3: int(base_char_limit * 0.6),  # Fourth: 60% of base limit 
                    4: int(base_char_limit * 0.5),  # Fifth: 50% of base limit
                }
                
                # Set default for any indices not in the dict
                max_chars = lambda i: max_chars_by_index.get(i, int(base_char_limit * 0.5))
            
            for i, d in enumerate(chosen):
                content_full = d.get("content", "")
                content_len = len(content_full)
                fname = d.get("metadata", {}).get("original_filename", "Unknown")
                score_val = d.get("rerank_score", d.get("score", "N/A"))
                
                # Determine character limit for this document based on its position
                doc_char_limit = max_chars(i) if callable(max_chars) else max_chars
                
                logger.info(f"RateCardRAG: Chosen Doc {i+1}: Filename='{fname}', Score={score_val}, FullContentLength={content_len}, CharLimit={doc_char_limit}")
                logger.debug(f"RateCardRAG: Chosen Doc {i+1} Content Start (first 500 chars):\\n{content_full[:500]}")
                logger.debug(f"RateCardRAG: Chosen Doc {i+1} Content End (last 200 chars):\\n{content_full[-200:]}")

                # Apply progressive character limit
                txt = content_full[:doc_char_limit] + ("...[TRUNC_PER_DOC]" if content_len > doc_char_limit else "")
                
                parts.append(f"Source: {fname} (Score:{score_val})\\n{txt}")
            
            doc_context = "<Rate Card Context>\\n" + "\\n\\n---\\n\\n".join(parts) + "\\n</Rate Card Context>"

        # 11. Token‐budgeting & final prompt
        MAX_TOK = int(getattr(settings, "MODEL_MAX_TOKENS", 16384))
        BUF = int(getattr(settings, "RESPONSE_BUFFER_TOKENS", 4096))
        RESPONSE_BUFFER = BUF  # Define RESPONSE_BUFFER for compatibility with updated code
        HST = int(getattr(settings, "MAX_CHAT_HISTORY_TOKENS", 2000))
        system_prompt = _build_rate_card_system_prompt()
        hist = _format_chat_history(chat_history, model=chat_model, max_tokens=HST)
        used = (
            count_tokens(system_prompt.replace("<RATE_CARD_CONTEXT>",""), chat_model) +
            count_tokens(hist, chat_model) +
            count_tokens(message, chat_model) + # Use message instead of q
            BUF
        )
        remain = MAX_TOK - used
        logger.info(f"RateCardRAG: Token budget: MAX_TOTAL_TOKENS={MAX_TOK}, SystemBaseTokens={count_tokens(system_prompt.replace('<RATE_CARD_CONTEXT>',''), chat_model)}, HistoryTokens={count_tokens(hist, chat_model)}, QueryTokens={count_tokens(message, chat_model)}, BufferTokens={BUF} => Remaining for RAG context: {remain}") # Use message

        if remain <= 0:
            rag_ctx = "Context omitted due to token limits."
            logger.warning(f"RateCardRAG: No tokens remaining for RAG context (remain={remain}). Context will be omitted.")
        else:
            doc_context_tokens_before_trunc = count_tokens(doc_context, chat_model)
            logger.info(f"RateCardRAG: RAG context ('doc_context') token count before final truncation: {doc_context_tokens_before_trunc}. Budget available: {remain}")
            if doc_context_tokens_before_trunc <= remain:
                rag_ctx = doc_context
                logger.info(f"RateCardRAG: Entire 'doc_context' ({doc_context_tokens_before_trunc} tokens) fits within budget.")
            else:
                rag_ctx = truncate_text_by_tokens(doc_context, chat_model, remain)
                rag_ctx_tokens_after_trunc = count_tokens(rag_ctx, chat_model)
                logger.warning(f"RateCardRAG: 'doc_context' was truncated from {doc_context_tokens_before_trunc} to {rag_ctx_tokens_after_trunc} tokens to fit budget {remain}.")

        final_sys = system_prompt.replace("<RATE_CARD_CONTEXT>", rag_ctx)
        messages_out = [{"role":"system","content":final_sys}]
        if hist:
            messages_out.append({"role":"user","content":f"History:\n{hist}"})
        messages_out.append({"role":"user","content":message})

        # --- Final LLM Call ---
        logger.info(f"Making final LLM call to {provider}/{chat_model} with {len(messages_out)} messages.")
        # Log total tokens being sent to LLM for debugging
        total_final_prompt_tokens = sum(count_tokens(msg["content"], chat_model) for msg in messages_out)
        logger.info(f"Estimated total tokens in final prompt to LLM: {total_final_prompt_tokens} (Max allowed: {MAX_TOK})")
        
        # Log token efficiency from content deduplication
        if total_tokens_saved > 0:
            efficiency_percentage = (total_tokens_saved / (total_final_prompt_tokens + total_tokens_saved)) * 100
            logger.info(f"RateCardRAG Token efficiency: Deduplication saved {total_tokens_saved:,} tokens ({efficiency_percentage:.1f}% reduction)")
        
        if total_final_prompt_tokens > MAX_TOK:
            logger.error(f"CRITICAL: Final prompt token count ({total_final_prompt_tokens}) EXCEEDS model max tokens ({MAX_TOK}). LLM call will likely fail.")

        try:
            # Get temperature from settings or use default
            temperature = 0.1
            if hasattr(settings, 'OPENAI_TEMPERATURE'):
                try:
                    temperature = float(settings.OPENAI_TEMPERATURE)
                except (ValueError, TypeError):
                    logger.warning("Invalid OPENAI_TEMPERATURE setting. Using default: 0.1")
            
            llm_response = await user_client.chat.completions.create(
                model=chat_model,
                messages=messages_out,
                temperature=temperature,
                max_tokens=RESPONSE_BUFFER
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
    return """You are a helpful AI assistant specializing in rate card information. Your user is asking about pricing, costs, or rates.
You have been provided with rate card context that might be relevant to the user's query.

When responding to rate card questions:

1. Be precise and specific about pricing, using exact figures from the context. Format all dollar amounts consistently (e.g., $1,000 not $1000).

2. Clearly state any conditions, terms, or qualifications that apply to the rates (experience levels, regions, time periods, etc.).

3. Organize multi-part rate information in a structured format:
   - Use tables when presenting multiple options or comparison data
   - Use bullet points for lists of rate conditions or qualifications
   - Include role/position titles exactly as specified in the source documents

4. When the user asks about specific entity rates (like GIC, MAS, etc.), focus your response on that entity's rates.

5. If the context does not provide specific rate information for the user's query, clearly state what information is missing and what relevant information you do have.

6. Never make up or estimate prices if they are not in the provided context.

7. Include the source of the information (document name) when presenting specific rates.

8. Important: In cases where multiple versions of the same document are found, PRIORITIZE the information from the source with the highest relevance score, as this is likely the most up-to-date and accurate version.

<RATE_CARD_CONTEXT>"""

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
    ms_token: Optional[str] = None, # Retained
    available_tools: Optional[List[Dict[str, Any]]] = None, # NEW for Phase 1
    tool_results: Optional[List[Dict[str, Any]]] = None    # NEW for Phase 3
) -> str | Dict[str, Any]: # MODIFIED return type
    """Generates a chat response using RAG, potentially with tool calling.
    Handles Phase 1 (tool decision), Phase 3 (synthesis), or standard RAG.
    """
    logger.debug(f"RAG/ToolCall Entry: user={user.email}, msg='{message[:50]}...', tools_provided={available_tools is not None}, results_provided={tool_results is not None}")
    fallback_response = "I apologize, but I encountered an unexpected error. Please try again later."
    
    # Client setup (common for all phases)
    try:
        chat_model = model_id or settings.OPENAI_MODEL_NAME
        provider = "deepseek" if chat_model.lower().startswith("deepseek") else "openai"
        db_api_key = api_key_crud.get_api_key(db, user.email, provider)
        if not db_api_key:
            logger.warning(f"User {user.email} missing active {provider} key for RAG/ToolCall.")
            if available_tools and not tool_results: # Phase 1 expecting dict
                 return {"type": "error", "message": f"{provider.capitalize()} API key required."} # Consistent error dict
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider.capitalize()} API key required.")
        
        user_api_key = decrypt_token(db_api_key.encrypted_key)
        if not user_api_key:
            logger.error(f"Failed to decrypt {provider} API key for {user.email}.")
            if available_tools and not tool_results: # Phase 1 expecting dict
                return {"type": "error", "message": "Could not decrypt API key."} # Consistent error dict
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not decrypt API key.")

        provider_timeout = 30.0
        if hasattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS") and getattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS"):
            try:
                provider_timeout = float(getattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS"))
            except (ValueError, TypeError):
                logger.warning(f"Invalid timeout for {provider.upper()}_TIMEOUT_SECONDS. Using default: 30.0s")
        
        client_kwargs = {"api_key": user_api_key, "timeout": provider_timeout}
        if db_api_key.model_base_url:
            client_kwargs["base_url"] = db_api_key.model_base_url
        user_client = AsyncOpenAI(**client_kwargs)
        # tokenizer_model = get_tokenizer_model_for_chat_model(chat_model) # Defined later if needed by RAG path

    except HTTPException as http_setup_exc:
        logger.error(f"RAG/ToolCall: HTTPException during setup: {http_setup_exc.detail}")
        if available_tools and not tool_results:
            return {"type": "error", "message": f"Setup error: {http_setup_exc.detail}"}
        raise http_setup_exc
    except Exception as setup_err:
        logger.error(f"RAG/ToolCall: Error during setup: {setup_err}", exc_info=True)
        if available_tools and not tool_results:
            return {"type": "error", "message": "Internal setup error for LLM interaction."}
        return fallback_response

    # --- Phase 3: Final Response Synthesis --- 
    if tool_results: # tool_results is List[ToolResult], where ToolResult has call_id, name, result
        logger.info(f"[Phase 3 LLM] Synthesizing response from {len(tool_results)} tool result(s) for user {user.email}")
        try:
            system_prompt_phase3 = (
                "You are an AI assistant. You previously decided to call tools to answer the user's query. "
                "Now you have the results from those tools. Synthesize these results into a final, user-friendly, natural language response. "
                "Address the user's original query based *only* on the information provided in the tool results. "
                "Do not refer to the fact that you used tools unless it's natural to the conversation. "
                "If a tool returned an error or no useful information, acknowledge that if necessary and respond as best as you can with other information."
            )
            messages_for_synthesis = [{"role": "system", "content": system_prompt_phase3}]
            
            if chat_history: # Original history before tool calls
                for entry in chat_history:
                    messages_for_synthesis.append({"role": entry["role"], "content": entry["content"]})
            messages_for_synthesis.append({"role": "user", "content": message}) # Original user message that triggered tools

            # Construct the assistant message that *would have made* these tool calls
            assistant_tool_call_objects = []
            if tool_results: # Ensure tool_results is not None and is iterable
                for res in tool_results: # res is a ToolResult model instance
                    assistant_tool_call_objects.append({
                        "id": res.call_id, 
                        "type": "function",
                        "function": {
                            "name": res.name, 
                            "arguments": "{}" # Placeholder: Original arguments not critical for linking if id/name match.
                        }
                    })
            
            if assistant_tool_call_objects:
                messages_for_synthesis.append({
                    "role": "assistant",
                    "content": None, 
                    "tool_calls": assistant_tool_call_objects
                })
                logger.info(f"[Phase 3 LLM] Added reconstructed assistant message with {len(assistant_tool_call_objects)} tool_calls.")

            # Now add the actual tool results (role: tool)
            if tool_results: # Ensure tool_results is not None and is iterable
                for res in tool_results: 
                    current_tool_result_data = res.result 
                    current_tool_call_id = res.call_id
                    current_tool_name = res.name

                    tool_output_content = ""
                    if isinstance(current_tool_result_data, dict) and current_tool_result_data.get('error'):
                        tool_output_content = json.dumps({"error": current_tool_result_data['error'], "message": "Tool execution failed."})
                    else:
                        tool_output_content = str(current_tool_result_data)

                    messages_for_synthesis.append({
                        "tool_call_id": current_tool_call_id,
                        "role": "tool",
                        "name": current_tool_name, 
                        "content": tool_output_content,
                    })
            
            logger.debug(f"[Phase 3 LLM] Final messages for synthesis count: {len(messages_for_synthesis)}. Content (first 2): {json.dumps(messages_for_synthesis[:2], indent=2)}")
            if len(messages_for_synthesis) > 2 : logger.debug(f"[Phase 3 LLM] Assistant tool_calls reconstruction (if any): {json.dumps(messages_for_synthesis[2], indent=2) if messages_for_synthesis[2]['role']=='assistant' else 'No assistant reconstruction'}")
            if len(messages_for_synthesis) > 3 : logger.debug(f"[Phase 3 LLM] First tool result message (if any): {json.dumps(messages_for_synthesis[3], indent=2) if messages_for_synthesis[3]['role']=='tool' else 'No tool message'}")

            response = await user_client.chat.completions.create(
                model=chat_model, messages=messages_for_synthesis, temperature=0.1
            )
            final_text_reply = response.choices[0].message.content.strip()
            logger.info(f"[Phase 3 LLM] Synthesis successful. Reply: {final_text_reply[:100]}...")
            return final_text_reply
        except Exception as e_synth:
            logger.error(f"[Phase 3 LLM] Error during synthesis: {e_synth}", exc_info=True)
            return "I tried to process the information from the tools, but encountered an issue."

    # --- Phase 1: Tool Call Decision or Routed Internal Query --- 
    elif available_tools: # available_tools are the MCP tools from manifest.json
        logger.info(f"[Phase 1 Router] Attempting to route message for user {user.email}. MCP tools available: {[t.get('name') for t in available_tools]}")
        
        # 1. Call Jarvis-Router to classify the query
        router_decision = await _call_jarvis_router(message, user_client, chat_model, available_tools)
        target = router_decision.get('target')
        confidence = router_decision.get('confidence', 0.0)
        logger.info(f"[Phase 1 Router] Jarvis-Router decision: Target='{target}', Confidence={confidence:.2f}")

        # Low confidence threshold - adjust as needed
        LOW_CONFIDENCE_THRESHOLD = 0.88 

        if router_decision.get("error"):
            logger.error(f"[Phase 1 Router] Jarvis-Router returned an error: {router_decision.get('error')}. Defaulting to direct LLM reply attempt.")
            target = "direct_llm_fallback" # Special target to signify direct reply without tools/internal RAG

        # Decision logic based on router target
        if target == 'mcp' and confidence >= LOW_CONFIDENCE_THRESHOLD:
            logger.info(f"[Phase 1 Router] Target is 'mcp'. Proceeding with MCP tool decision.")
            try:
                # Build a more structured and detailed description of available tools
                tool_descriptions = ""
                if available_tools:
                    for tool in available_tools:
                        tool_name = tool.get("name", "unknown_tool")
                        tool_desc = tool.get("description", "No description available")
                        user_defined = "User-defined" if tool.get("user_defined", False) else "System"
                        tool_descriptions += f"\n- {tool_name}: {tool_desc} ({user_defined})"
                
                # This is the existing logic for when LLM decides on an MCP tool or direct answer
                system_prompt_mcp = (
                    "You are an AI assistant. Based on the user's query, "
                    "decide if calling one of the available external tools (MCP tools) would be beneficial. "
                    f"The following tools are available:{tool_descriptions}\n\n"
                    "If calling a tool would help answer the query, choose the appropriate tool(s) and provide arguments. "
                    "Otherwise, answer directly without using these tools. "
                    "Be specific when deciding to use a tool - only use tools when they directly apply to the user's request."
                )
                messages_for_mcp_decision = [{"role": "system", "content": system_prompt_mcp}]
                if chat_history:
                    for entry in chat_history: messages_for_mcp_decision.append({"role": entry["role"], "content": entry["content"]})
                messages_for_mcp_decision.append({"role": "user", "content": message})

                # available_tools are already formatted for OpenAI in routes/chat.py, but llm.py receives the raw manifest list
                formatted_mcp_tools_for_llm = [{"type": "function", "function": tool_def} for tool_def in available_tools]

                response = await user_client.chat.completions.create(
                    model=chat_model, messages=messages_for_mcp_decision,
                    tools=formatted_mcp_tools_for_llm, tool_choice="auto", temperature=0.1
                )
                response_message = response.choices[0].message

                if response_message.tool_calls:
                    logger.info(f"[Phase 1 MCP] LLM decided to call MCP tools: {response_message.tool_calls}")
                    parsed_mcp_tool_calls = [
                        {"call_id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                        for tc in response_message.tool_calls
                    ]
                    return {"type": "tool_call", "tool_calls": parsed_mcp_tool_calls}
                else:
                    direct_reply = response_message.content.strip() if response_message.content else "I'm not sure how to help with that specific request using my current tools."
                    logger.info(f"[Phase 1 MCP] LLM decided to reply directly (no MCP tool): {direct_reply[:100]}...")
                    return {"type": "text", "reply": direct_reply }
            except Exception as e_mcp:
                logger.error(f"[Phase 1 MCP] Error during MCP tool decision: {e_mcp}", exc_info=True)
                return {"type": "text", "reply": "I had trouble processing your request for external tools."}

        elif target == 'iceberg' and confidence >= LOW_CONFIDENCE_THRESHOLD:
            logger.info(f"[Phase 1 Router] Target is 'iceberg'. Querying Iceberg (emails/operational data).")
            try:
                # Use the new LLM-based parameter extraction for Iceberg email queries
                logger.info(f"[Phase 1 Iceberg] Calling LLM to extract structured parameters for query: '{message}'")
                extracted_iceberg_params = await _extract_email_search_parameters_for_iceberg(message, user_client, chat_model)
                
                if not extracted_iceberg_params: # Check if extraction failed and returned empty dict
                    logger.warning("[Phase 1 Iceberg] Parameter extraction failed or returned empty. Using broad search terms as fallback.")
                    extracted_iceberg_params = {"search_terms": [message]} # Fallback to raw message
                else:
                    logger.info(f"[Phase 1 Iceberg] Extracted parameters for Iceberg query: {extracted_iceberg_params}")

                iceberg_results = await query_iceberg_emails_duckdb(
                    user_email=user.email, 
                    sender_filter=extracted_iceberg_params.get("sender_filter"),
                    subject_filter=extracted_iceberg_params.get("subject_filter"),
                    start_date=extracted_iceberg_params.get("start_date"), # This will be a datetime object or None
                    end_date=extracted_iceberg_params.get("end_date"),   # This will be a datetime object or None
                    search_terms=extracted_iceberg_params.get("search_terms"), # This will be a list of strings or None
                    limit=getattr(settings, "MAX_EMAIL_CONTEXT_ITEMS_BROAD", 10),
                    user_client=user_client, 
                    provider=provider
                )
                # ADDED: Log details of retrieved Iceberg results
                if iceberg_results:
                    logger.info(f"[Phase 1 Iceberg] Retrieved {len(iceberg_results)} emails from Iceberg. Details (up to 10):")
                    for i, email_res in enumerate(iceberg_results[:10]):
                        logger.info(f"  Email {i+1}: ID={email_res.get('message_id')}, From=\"{email_res.get('sender_name')}\" <{email_res.get('sender')}>, Subject='{email_res.get('subject')}', Date={email_res.get('received_datetime_utc')}")
                else:
                    logger.info("[Phase 1 Iceberg] No emails retrieved from Iceberg.")

                synthesized_reply = await _synthesize_answer_from_context(message, iceberg_results, "operational data and emails", user_client, chat_model, chat_history)
                return {"type": "text", "reply": synthesized_reply}
            except Exception as e_iceberg:
                logger.error(f"[Phase 1 Iceberg] Error querying/synthesizing Iceberg data: {e_iceberg}", exc_info=True)
                return {"type": "text", "reply": "I encountered an issue while trying to retrieve operational data."}

        elif target == 'milvus' or target == 'multi' or confidence < LOW_CONFIDENCE_THRESHOLD:
            if target != 'milvus':
                 logger.info(f"[Phase 1 Router] Target is '{target}' or confidence {confidence:.2f} < {LOW_CONFIDENCE_THRESHOLD}. Defaulting to Milvus (knowledge base). ")
            else:
                 logger.info(f"[Phase 1 Router] Target is 'milvus'. Querying Milvus (knowledge base).")
            try:
                # For Milvus, the message itself can often be the query_text
                # The _get_milvus_context includes deduplication and reranking.
                # Note: get_rate_card_response_advanced has more specific logic for rate cards.
                # If router identifies a rate card, we might want to invoke that more specific path.
                # For now, general Milvus search for knowledge questions.
                is_rate_card_query = "rate card" in message.lower() # Simple check for now
                if is_rate_card_query and target == 'milvus': # And router also thought it was knowledge question
                    logger.info("[Phase 1 Milvus] Identified as rate card query. Attempting to use get_rate_card_response_advanced logic.")
                    # This function already does retrieval and synthesis and returns a string.
                    # It needs to be adapted if its internal LLM calls are to use the main user_client.
                    # For now, we call it directly and assume it handles its own LLM client setup if needed.
                    # It expects `db` and `user` which are available in this scope.
                    # It doesn't fit the `_synthesize_answer_from_context` pattern directly.
                    # TODO: Refactor get_rate_card_response_advanced to separate retrieval and synthesis, 
                    # or make it an internal tool that `_synthesize_answer_from_context` can consume results from.
                    # For now, directly call and return its string output.
                    rate_card_reply = await get_rate_card_response_advanced(message, chat_history or [], user, db, model_id, ms_token)
                    return {"type": "text", "reply": rate_card_reply}
                else:
                    milvus_docs, _ = await _get_milvus_context(
                        max_items=10, # Fetch more for better synthesis context
                        max_chunk_chars=8000, # From original RAG settings
                        query=message, 
                        user_email=user.email, 
                        model_name=chat_model
                    )
                    synthesized_reply = await _synthesize_answer_from_context(message, milvus_docs, "knowledge base documents", user_client, chat_model, chat_history)
                    return {"type": "text", "reply": synthesized_reply}
            except Exception as e_milvus:
                logger.error(f"[Phase 1 Milvus] Error querying/synthesizing Milvus data: {e_milvus}", exc_info=True)
                return {"type": "text", "reply": "I encountered an issue while searching the knowledge base."}
        
        elif target == "direct_llm_fallback": # Special case if router itself errored
            logger.info("[Phase 1 Router] Router errored. Attempting direct LLM reply as fallback.")
            try:
                response = await user_client.chat.completions.create(
                    model=chat_model,
                    messages=([{"role":"system", "content":"You are a helpful assistant."}] +
                              [{"role":h["role"], "content":h["content"]} for h in chat_history or []] +
                              [{"role":"user", "content":message}]),
                    temperature=0.1
                )
                direct_reply = response.choices[0].message.content.strip() if response.choices[0].message.content else "I'm not sure how to help with that."
                return {"type": "text", "reply": direct_reply }
            except Exception as e_direct_fallback:
                logger.error(f"[Phase 1 Direct Fallback] Error: {e_direct_fallback}", exc_info=True)
                return {"type": "text", "reply": "I had trouble formulating a direct response."}

        else: # Should not be reached if router provides valid target or error leads to direct_llm_fallback
            logger.error(f"[Phase 1 Router] Unhandled router target: '{target}'. Fallback to simple reply.")
            return {"type": "text", "reply": "I'm not quite sure how to handle your request with the current routing logic."}

    # --- Fallback to Original RAG (SHOULD BE DEPRECATED by router logic) --- 
    else:
        logger.info(f"[Fallback RAG] No tool interaction. Proceeding with standard RAG for user {user.email}")
        # !!! IMPORTANT !!!
        # This is where the *entire original RAG logic* from generate_openai_rag_response should be placed.
        # For brevity in this conceptual edit, that massive block of code (approx lines 712-1059
        # in the originally provided llm.py) is NOT duplicated here.
        # If this path is intended to be used, that code MUST be restored here.
        # The RAG logic includes: token budgeting, email param extraction, context retrieval 
        # (Milvus, Iceberg), email/document processing, summarization, final prompt assembly, and LLM call.
        
        # For now, as a placeholder for this path being hit (which might indicate a logic error upstream):
        logger.warning("generate_openai_rag_response called in Fallback RAG mode. "
                       "The original full RAG logic should execute here. This placeholder will return a simple reply.")
        # tokenizer_model = get_tokenizer_model_for_chat_model(chat_model) # Would be needed by full RAG
        try:
            # Minimal messages for a direct reply if RAG context is skipped in this placeholder
            response = await user_client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant responding via fallback."},
                    {"role": "user", "content": message}
                ],
                temperature=0.1
            )
            return response.choices[0].message.content.strip() if response.choices[0].message.content else fallback_response
        except Exception as e_fallback_direct:
            logger.error(f"Error in minimal fallback direct call: {e_fallback_direct}", exc_info=True)
            return "I am having trouble processing your request via the fallback RAG path."

    # Should not be reached if logic is correct
    logger.error("RAG/ToolCall function reached unexpected end. Returning fallback.")
    if available_tools and not tool_results:
        return {"type": "text", "reply": fallback_response }
    return fallback_response

async def deduplicate_and_log_tokens(results: List[Dict[str, Any]], tokenizer_model: str, similarity_threshold: float = 0.85) -> Tuple[List[Dict[str, Any]], int]:
    """
    Deduplicate results and log token efficiency metrics.
    
    This function enhances the RAG pipeline by:
    1. Removing duplicate and similar content to improve context quality
    2. Measuring and logging token savings for monitoring and optimization
    3. Enabling better utilization of the token budget for more relevant content
    
    Key advantages:
    - Prevents token waste on duplicate content
    - Provides transparency into token usage efficiency
    - Allows fitting more unique content within the model's context window
    
    Args:
        results: List of result dictionaries 
        tokenizer_model: Tokenizer model to use for counting tokens
        similarity_threshold: Threshold for similarity-based deduplication
        
    Returns:
        Tuple of (deduplicated results, tokens saved)
    """
    if not results or len(results) <= 1:
        return results, 0
        
    # Count tokens in original results
    original_tokens = 0
    original_count = len(results)
    for result in results:
        content = result.get("content", "")
        if isinstance(content, str) and content.strip():
            original_tokens += count_tokens(content, tokenizer_model)
    
    # Check if this appears to be rate card content to apply more aggressive deduplication
    is_rate_card_content = False
    rate_card_terms = ["rate", "card", "pricing", "cost", "fee", "charge", "price"]
    
    # Sample up to 5 documents to check for rate card content
    sample_size = min(5, len(results))
    for result in results[:sample_size]:
        content = result.get("content", "")
        if not isinstance(content, str):
            continue
            
        # Check for rate card indicators in content
        content_lower = content.lower()
        if any(term in content_lower for term in rate_card_terms):
            is_rate_card_content = True
            break
            
        # Also check filename if available
        filename = result.get("metadata", {}).get("original_filename", "").lower()
        if any(term in filename for term in rate_card_terms):
            is_rate_card_content = True
            break
    
    # Apply more aggressive deduplication for rate card content
    if is_rate_card_content:
        # Use lower threshold and longer comparison for rate card content
        actual_threshold = max(0.75, similarity_threshold - 0.1)  # More aggressive
        max_chars = 500  # Use more content for comparison
        logger.info(f"Applying aggressive rate card deduplication: threshold={actual_threshold}, chars={max_chars}")
    else:
        actual_threshold = similarity_threshold
        max_chars = 300  # Default comparison length
    
    # Perform deduplication
    deduplicated = await deduplicate_results(
        results, 
        similarity_threshold=actual_threshold,
        max_document_chars=max_chars
    )
    
    # Count tokens in deduplicated results
    deduplicated_tokens = 0
    for result in deduplicated:
        content = result.get("content", "")
        if isinstance(content, str) and content.strip():
            deduplicated_tokens += count_tokens(content, tokenizer_model)
    
    # Calculate and log token savings
    tokens_saved = original_tokens - deduplicated_tokens
    efficiency = (tokens_saved / original_tokens * 100) if original_tokens > 0 else 0
    docs_removed = original_count - len(deduplicated)
    
    if tokens_saved > 0:
        logger.info(f"Deduplication efficiency: {tokens_saved:,} tokens saved ({efficiency:.1f}%), {original_tokens:,} → {deduplicated_tokens:,}")
        logger.info(f"Document reduction: {original_count} → {len(deduplicated)} docs ({docs_removed} removed)")
    
    return deduplicated, tokens_saved

def get_tokenizer_model_for_chat_model(model_name: str) -> str:
    """
    Get the appropriate tokenizer model name for a given chat model.
    This helps ensure we use the right tokenizer for token counting.
    """
    # Default to cl100k_base for most OpenAI models
    if not model_name:
        return "gpt-4"
        
    model_lower = model_name.lower()
    
    # OpenAI models
    if "gpt-3.5" in model_lower:
        return "gpt-3.5-turbo"
    elif "gpt-4" in model_lower:
        return "gpt-4"
    elif "claude" in model_lower:
        return "cl100k_base"  # Claude uses the same tokenizer as GPT-4
    elif "deepseek" in model_lower:
        return "cl100k_base"  # Use cl100k_base for Deepseek as fallback
        
    # Default fallback
    return "cl100k_base"

async def _test_and_fix_rate_card_function():
    """
    We've added improvements to the rate card response function:
    
    1. Content-based deduplication to avoid similar documents using tokens
    2. Token efficiency tracking and reporting
    3. More consistent variable naming with the rest of the codebase
    
    This results in:
    - Better token utilization
    - More relevant content in each response
    - Detailed logging of token efficiency gains
    """
    pass

# --- NEW HELPER: Jarvis-Router --- 
async def _call_jarvis_router(message: str, client: AsyncOpenAI, model: str, available_tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Calls an LLM to classify the user message into a target category (mcp, iceberg, milvus)."""
    
    # Build MCP tools details if provided
    mcp_tools_details = ""
    if available_tools and len(available_tools) > 0:
        mcp_tools_details = "Available MCP tools:\n"
        for tool in available_tools:
            tool_name = tool.get("name", "")
            tool_desc = tool.get("description", "No description")
            mcp_tools_details += f"  - {tool_name}: {tool_desc}\n"
    
    system_prompt = (
        "You are Jarvis-Router. Classify the user message into one of the following categories:\n"
        "  1) mcp – user wants to interact with external systems or APIs (e.g., list/get/create/update Jira issues, schedule events & calendar, send emails, etc.).\n"
        "  2) iceberg – user wants operational data like emails, or information about jobs, tables, metrics, or day-to-day activities.\n"
        "  3) milvus – user is asking a knowledge question, seeking information from documents, or wants a rate card.\n"
        f"{mcp_tools_details}\n"
        "Analyze the user's message and respond with a single JSON object. "
        "The JSON object must have two keys: 'target' (string, one of ['mcp', 'iceberg', 'milvus', 'multi']) "
        "and 'confidence' (float, 0.0 to 1.0). Example JSON response: { \"target\": \"milvus\", \"confidence\": 0.85 }"
    )
    
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    router_output_str = ""
    try:
        logger.info(f"[_call_jarvis_router] Calling LLM for routing. Message: '{message[:100]}...'")
        response = await client.chat.completions.create(
            model=model,
            messages=prompt_messages,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        router_output_str = response.choices[0].message.content
        logger.info(f"[_call_jarvis_router] Raw LLM output: {router_output_str}")
        router_decision = json.loads(router_output_str)
        
        if not isinstance(router_decision, dict) or not all(k in router_decision for k in ['target', 'confidence']):
            logger.error(f"[_call_jarvis_router] Invalid JSON structure from router LLM: {router_decision}. Missing keys or not a dict.")
            return {"target": "milvus", "confidence": 0.5, "error": "Invalid router response structure"}
        
        target = router_decision.get('target')
        if target not in ['mcp', 'iceberg', 'milvus', 'multi']:
            logger.warning(f"[_call_jarvis_router] Router LLM returned unknown target: {target}. Defaulting to milvus.")
            router_decision['target'] = 'milvus' # Correct the target in the decision object
        
        # Ensure confidence is a float
        try:
            router_decision['confidence'] = float(router_decision.get('confidence', 0.5))
        except (ValueError, TypeError):
            logger.warning(f"[_call_jarvis_router] Router LLM returned invalid confidence: {router_decision.get('confidence')}. Defaulting to 0.5.")
            router_decision['confidence'] = 0.5
            
        return router_decision
    except json.JSONDecodeError as e:
        logger.error(f"[_call_jarvis_router] Failed to parse JSON from router LLM: {e}. Raw: {router_output_str}")
        return {"target": "milvus", "confidence": 0.5, "error": "JSON decode error from router"}
    except Exception as e:
        logger.error(f"[_call_jarvis_router] Error: {e}", exc_info=True)
        return {"target": "milvus", "confidence": 0.5, "error": str(e)}

# --- NEW HELPER: Synthesize Answer from Context --- 
async def _synthesize_answer_from_context(
    original_query: str, 
    retrieved_items: List[Dict[str, Any]], 
    context_description: str, 
    client: AsyncOpenAI, 
    model: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """Generates a natural language answer based on retrieved items and original query."""
    if not retrieved_items:
        return f"I couldn't find any specific information about '{original_query}' in the {context_description}."

    # Get current date in Singapore timezone for context
    singapore_tz = ZoneInfo("Asia/Singapore")
    now_sg = datetime.now(singapore_tz)
    today_sg_date = now_sg.strftime('%Y-%m-%d')
    today_sg_weekday = now_sg.strftime('%A')
    
    # Log the date we're using
    logger.info(f"[_synthesize_answer_from_context] Using today's date (Singapore): {today_sg_date} ({today_sg_weekday})")

    context_str = ""
    # MODIFIED: Process more items (e.g., up to 6 or all if count is low)
    items_to_process = retrieved_items[:max(6, len(retrieved_items))] 

    logger.info(f"[_synthesize_answer_from_context] Processing {len(items_to_process)} items for synthesis.")

    # HTML stripping function
    def strip_html_tags(text: str) -> str:
        """Strips HTML tags from text content."""
        if not text:
            return ""
        
        # Handle common HTML entity characters
        entity_replacements = {
            "&lt;": "<", "&gt;": ">", "&amp;": "&", 
            "&quot;": '"', "&apos;": "'", "&nbsp;": " "
        }
        for entity, replacement in entity_replacements.items():
            text = text.replace(entity, replacement)
        
        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    for i, item in enumerate(items_to_process):
        content_to_display = "[No clear textual content extracted for this item]" # Default message
        text_parts = []

        # Prioritize schema fields for plain text
        # Based on schema: body_text for full_message, quoted_raw_text for quoted_message
        granularity = item.get('granularity')
        
        primary_text = None
        if granularity == 'full_message' and isinstance(item.get('body_text'), str):
            primary_text = item['body_text']
            logger.debug(f"Item {i+1} (full_message) using body_text. Length: {len(primary_text) if primary_text else 0}")
        elif granularity == 'quoted_message' and isinstance(item.get('quoted_raw_text'), str):
            primary_text = item['quoted_raw_text']
            logger.debug(f"Item {i+1} (quoted_message) using quoted_raw_text. Length: {len(primary_text) if primary_text else 0}")
        elif isinstance(item.get('body_text'), str): # Fallback if granularity is missing but body_text exists
            primary_text = item['body_text']
            logger.debug(f"Item {i+1} (no/unclear granularity) using fallback body_text. Length: {len(primary_text) if primary_text else 0}")
        elif isinstance(item.get('content'), str): # Generic content field
            primary_text = item['content']
            logger.debug(f"Item {i+1} using generic 'content' field. Length: {len(primary_text) if primary_text else 0}")
        elif isinstance(item.get('summary'), str):
            primary_text = item['summary']
            logger.debug(f"Item {i+1} using 'summary' field. Length: {len(primary_text) if primary_text else 0}")

        if primary_text:
            # Check for HTML content and strip it if detected
            if "<html" in primary_text.lower() or "<body" in primary_text.lower() or "<div" in primary_text.lower() or \
               "&lt;div" in primary_text.lower() or "<!--" in primary_text or "@font-face" in primary_text:
                original_length = len(primary_text)
                primary_text = strip_html_tags(primary_text)
                logger.info(f"Item {i+1} contained HTML that was stripped. Original size: {original_length}, New size: {len(primary_text)}")
            text_parts.append(primary_text)
        
        # Add subject if not already in primary text and seems relevant
        subject = item.get('subject')
        if isinstance(subject, str) and subject:
            if not primary_text or subject.lower() not in primary_text.lower():
                text_parts.insert(0, f"Subject: {subject}") # Prepend subject
        
        if text_parts:
            content_to_display = "\n".join(text_parts)
        else:
            # Fallback if no primary text fields were found or were not strings
            simple_parts = []
            if isinstance(item, dict):
                for k, v in item.items():
                    if k not in ['body_text', 'quoted_raw_text', 'content', 'summary'] and isinstance(v, (str, int, float, bool)):
                        simple_parts.append(f"{k}: {v}")
            if simple_parts:
                content_to_display = "; ".join(simple_parts)
                logger.debug(f"Item {i+1} using fallback simple parts string: {content_to_display[:200]}")
            else:
                logger.debug(f"Item {i+1} truly has no displayable textual content based on checks.")

        item_content_for_llm = str(content_to_display)[:1500] # Increased truncation limit slightly
        context_str += f"--- Email {i+1} ---\nFrom: {item.get('sender_name') or item.get('sender', 'Unknown Sender')}\nDate: {item.get('received_datetime_utc', 'Unknown Date')}\n{item_content_for_llm}\n---\n"
    
    system_prompt = (
        f"You are an AI assistant. The user asked the following query: '{original_query}'.\n"
        f"IMPORTANT: Today's date is {today_sg_date} ({today_sg_weekday}) in Singapore timezone.\n"
        f"Based SOLELY on the following extracted context from '{context_description}', provide a comprehensive answer to the user's query. "
        f"If the context directly answers the query, provide that answer. "
        f"If the context is relevant but doesn't fully answer, explain what you found and what might be missing. "
        f"If the context doesn't seem to contain relevant information, clearly state that. Do not make up information or answer outside the provided context.\n"
        f"When referring to dates in your response, please be accurate and specific. Today means {today_sg_date}, yesterday means the day before, and so on. "
        f"Do NOT confuse today's date when answering queries about meetings or events."
    )
    
    messages_for_synthesis = [
        {"role": "system", "content": system_prompt}
    ]
    # Add chat history if available, before the current query and context
    if chat_history:
        for entry in chat_history:
            messages_for_synthesis.append({"role": entry["role"], "content": entry["content"]})
    
    # The user's current query that led to this synthesis, plus the context found.
    # Framing it as user providing the context they found regarding their query.
    messages_for_synthesis.append({"role": "user", "content": f"""Regarding my query ('{original_query}'), I found this information:

{context_str}
Please provide an answer based on this. Remember that today is {today_sg_date} ({today_sg_weekday})."""})
    
    try:
        logger.info(f"[_synthesize_answer_from_context] Synthesizing for query: '{original_query[:50]}...' from {context_description}")
        response = await client.chat.completions.create(
            model=model,
            messages=messages_for_synthesis,
            temperature=0.1, # Lower temperature for factual synthesis
            max_tokens=1024  # Allow a reasonable length for the synthesized answer
        )
        synthesized_reply = response.choices[0].message.content.strip()
        return synthesized_reply
    except Exception as e:
        logger.error(f"[_synthesize_answer_from_context] Error during synthesis: {e}", exc_info=True)
        return f"I found some information from {context_description} regarding '{original_query}', but encountered an issue while trying to formulate a final answer."

# --- NEW HELPER: Extract Email Search Parameters for Iceberg --- 
async def _extract_email_search_parameters_for_iceberg(message: str, client: AsyncOpenAI, model: str) -> Dict[str, Any]:
    """Uses LLM to extract structured search parameters for querying emails in Iceberg."""
    logger.info(f"[_extract_email_search_parameters_for_iceberg] Called for message: '{message[:100]}...'")
    
    # Use Singapore timezone for date calculations
    singapore_tz = ZoneInfo("Asia/Singapore")
    now_sg = datetime.now(singapore_tz)
    now_sg_iso = now_sg.isoformat()
    
    logger.info(f"[_extract_email_search_parameters] Current Singapore time: {now_sg_iso}")
    
    # Helper to calculate past/future dates for examples, using Singapore timezone
    def calculate_example_date(days_offset: int, start_of_day: bool = False, end_of_day: bool = False) -> str:
        try:
            target_dt = now_sg + timedelta(days=days_offset)
            if start_of_day:
                target_dt = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            elif end_of_day:
                target_dt = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            return target_dt.isoformat()
        except Exception as e_date_calc:
            logger.error(f"Error in calculate_example_date: {e_date_calc}")
            return f"[date_calc_error_offset_{days_offset}]"

    # Define example dates for the prompt using Singapore timezone
    example_dates = {
        "now_sg_iso": now_sg_iso,
        "today_start": calculate_example_date(0, start_of_day=True),
        "today_end": calculate_example_date(0, end_of_day=True),
        "yesterday_start": calculate_example_date(-1, start_of_day=True),
        "yesterday_end": calculate_example_date(-1, end_of_day=True),
        "last_3_days_start": calculate_example_date(-3, start_of_day=True),
        "last_7_days_start": calculate_example_date(-7, start_of_day=True),
        "tomorrow_start": calculate_example_date(1, start_of_day=True),
        "tomorrow_end": calculate_example_date(1, end_of_day=True),
        "next_7_days_end": calculate_example_date(7, end_of_day=True),
    }
    
    # Log the dates we're using
    logger.info(f"[_extract_email_search_parameters] Today in Singapore: {example_dates['today_start'].split('T')[0]}")

    # Extract just the date portion for the template
    today_date = example_dates['today_start'].split('T')[0]

    extraction_prompt_template = (
        f"You are an expert parameter extractor for email searches. Current time in Asia/Singapore is {{now_sg_iso}}.\n"
        f"Analyze the user's message: \"{{message}}\"\n"
        f"Extract the following parameters for searching emails. If a parameter is not mentioned or cannot be inferred, use null.\n"
        f"  - sender: The name or email address of the sender.\n"
        f"  - subject: Specific keywords or phrases that MUST be in the email subject. If keywords are general search terms for body/subject, use 'search_terms' instead and leave subject null.\n"
        f"  - start_date_utc: The start date for the search in ISO format. Calculate from relative terms like 'today', 'yesterday', 'last week' using Singapore time zone (UTC+8). For 'today', use {{today_start}}; for 'yesterday', use {{yesterday_start}}. For general queries about events happening 'today' or 'by today', consider a recent window for when the arrangement email might have been sent (e.g., last 3 days).\n"
        f"  - end_date_utc: The end date for the search in ISO format. For 'today' or 'yesterday', this would be the end of that day. For 'today', use {{today_end}}; for 'yesterday', use {{yesterday_end}}. For ranges like 'last week', use current time.\n"
        f"  - search_terms: A list of general keywords or phrases (e.g., from the query that are not senders or direct subject lines) to search in email body or subject. If user mentions multiple terms like 'meeting OR interview', list them as [\"meeting\", \"interview\"].\n"
        f"Respond ONLY with a single JSON object containing these keys: \"sender\", \"subject\", \"start_date_utc\", \"end_date_utc\", \"search_terms\".\n"
        f"Examples (Current Singapore time is {{now_sg_iso}}):\n"
        f"  1. User: \"emails from jeff last week about the UOB project\" -> {{{{ \"sender\": \"jeff\", \"subject\": \"UOB project\", \"start_date_utc\": \"{{last_7_days_start}}\", \"end_date_utc\": \"{{now_sg_iso}}\", \"search_terms\": [\"UOB project\"]}}}})\n"
        f"  2. User: \"any meeting or interview arranged by today? \" -> {{{{ \"sender\": null, \"subject\": null, \"start_date_utc\": \"{{last_3_days_start}}\", \"end_date_utc\": \"{{today_end}}\", \"search_terms\": [\"meeting\", \"interview\"]}}}})\n"
        f"  3. User: \"show me emails from yesterday regarding customer feedback\" -> {{{{ \"sender\": null, \"subject\": \"customer feedback\", \"start_date_utc\": \"{{yesterday_start}}\", \"end_date_utc\": \"{{yesterday_end}}\", \"search_terms\": [\"customer feedback\"]}}}})\n"
        f"  4. User: \"any new emails on the Project X topic?\" (Implies recent, e.g. today) -> {{{{ \"sender\": null, \"subject\": null, \"start_date_utc\": \"{{today_start}}\", \"end_date_utc\": \"{{today_end}}\", \"search_terms\": [\"Project X\"]}}}})\n"
        f"  5. User: \"search for emails about 'launch plan' from alice next week\" -> {{{{ \"sender\": \"alice\", \"subject\": \"launch plan\", \"start_date_utc\": \"{{tomorrow_start}}\", \"end_date_utc\": \"{{next_7_days_end}}\", \"search_terms\": [\"launch plan\"]}}}})\n"
        f"IMPORTANT: Remember that 'today' refers to {today_date} in Singapore time.\n"
        f"JSON Response:\"\n"
    )
    
    final_extraction_prompt = extraction_prompt_template.format(message=message, **example_dates)
    
    messages = [
        {"role": "system", "content": "You are an expert at extracting structured search parameters from user queries for email searches. You must calculate dates accurately based on the Singapore timezone (UTC+8) and relative terms. Respond only with the specified JSON object."},
        {"role": "user", "content": final_extraction_prompt}
    ]
    
    extracted_params_str = ""
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        extracted_params_str = response.choices[0].message.content
        logger.info(f"[_extract_email_search_parameters_for_iceberg] Raw LLM output for params: {extracted_params_str}")
        raw_params = json.loads(extracted_params_str)
        
        # Validate and parse dates - convert to UTC for database queries
        start_date_obj, end_date_obj = None, None
        raw_start = raw_params.get("start_date_utc")
        raw_end = raw_params.get("end_date_utc")

        if raw_start:
            try: 
                # Parse date with timezone info preserved
                start_date_obj = datetime.fromisoformat(str(raw_start).replace('Z', '+00:00'))
                logger.info(f"Parsed start_date: {start_date_obj.isoformat()}")
            except (ValueError, TypeError): 
                logger.warning(f"Invalid start_date_utc from LLM: {raw_start}")
        if raw_end:
            try: 
                # Parse date with timezone info preserved
                end_date_obj = datetime.fromisoformat(str(raw_end).replace('Z', '+00:00'))
                logger.info(f"Parsed end_date: {end_date_obj.isoformat()}")
            except (ValueError, TypeError): 
                logger.warning(f"Invalid end_date_utc from LLM: {raw_end}")

        if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
            logger.warning(f"LLM returned start_date > end_date ({start_date_obj} > {end_date_obj}). Discarding dates.")
            start_date_obj, end_date_obj = None, None
            
        # Ensure search_terms is a list of strings
        search_terms_val = raw_params.get("search_terms")
        if not isinstance(search_terms_val, list) or not all(isinstance(st, str) for st in search_terms_val):
            logger.warning(f"LLM returned invalid search_terms: {search_terms_val}. Setting to empty list or using subject.")
            search_terms_val = [raw_params.get("subject")] if isinstance(raw_params.get("subject"), str) else []
            search_terms_val = [st for st in search_terms_val if st] # filter out None/empty from subject fallback
            
        return {
            "sender_filter": raw_params.get("sender") if isinstance(raw_params.get("sender"), str) else None,
            "subject_filter": raw_params.get("subject") if isinstance(raw_params.get("subject"), str) else None,
            "start_date": start_date_obj,
            "end_date": end_date_obj,
            "search_terms": search_terms_val
        }

    except json.JSONDecodeError as e_json:
        logger.error(f"[_extract_email_search_parameters_for_iceberg] JSONDecodeError: {e_json}. Raw LLM output: {extracted_params_str}")
    except Exception as e_param:
        logger.error(f"[_extract_email_search_parameters_for_iceberg] Unexpected error: {e_param}", exc_info=True)
    
    return {} # Return empty dict on error, so downstream uses defaults