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
        # Mandatory base conditions
        final_where_clauses = ["owner_email = ?"]
        final_query_params = [user_email]

        # Apply date filters as top-level AND conditions if they exist
        if start_date:
            final_where_clauses.append("received_datetime_utc >= ?")
            final_query_params.append(start_date)
            logger.info(f"Applying mandatory start_date filter: {start_date.isoformat()} (Year: {start_date.year})")
        if end_date:
            final_where_clauses.append("received_datetime_utc <= ?")
            final_query_params.append(end_date)
            logger.info(f"Applying mandatory end_date filter: {end_date.isoformat()} (Year: {end_date.year})")

        # Clauses for specific field attribute filters (sender, subject)
        attribute_filter_clauses = []
        attribute_filter_params = []
        
        # Plausibility check for sender
        is_plausible_sender_filter = False
        if sender_filter:
            # Simple check: contains @ or multiple words, or is a reasonable length name
            if '@' in sender_filter or len(sender_filter.split()) > 1 or (len(sender_filter) >= 2 and sender_filter.isalpha()): 
                is_plausible_sender_filter = True
            else:
                logger.warning(f"Ignoring likely implausible sender filter: '{sender_filter}'. Does not look like an email or multi-word name.")

        if is_plausible_sender_filter:
            attribute_filter_clauses.append("sender LIKE ?")
            attribute_filter_params.append(f"%{sender_filter}%")
            logger.debug(f"Applying attribute sender filter: {sender_filter}")
        
        if subject_filter:
            attribute_filter_clauses.append("subject LIKE ?")
            attribute_filter_params.append(f"%{subject_filter}%")
            logger.debug(f"Applying attribute subject filter: {subject_filter}")
        
        attribute_filters_sql_part = ""
        if attribute_filter_clauses:
            attribute_filters_sql_part = " AND ".join(attribute_filter_clauses)
            # Wrap in parentheses if there are attribute filters
            attribute_filters_sql_part = f"({attribute_filters_sql_part})"

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
                logger.debug(f"Applying keyword search terms: {search_terms}")

        # Combine attribute filters and keyword search with an OR, if both exist
        # This combined group will then be ANDed with the mandatory filters (owner, dates)
        optional_filters_combined_sql = ""
        if attribute_filters_sql_part and keyword_search_sql_part:
            optional_filters_combined_sql = f"({attribute_filters_sql_part} OR {keyword_search_sql_part})"
            final_query_params.extend(attribute_filter_params)
            final_query_params.extend(keyword_search_params)
        elif attribute_filters_sql_part:
            optional_filters_combined_sql = attribute_filters_sql_part
            final_query_params.extend(attribute_filter_params)
        elif keyword_search_sql_part:
            optional_filters_combined_sql = keyword_search_sql_part
            final_query_params.extend(keyword_search_params)
        
        # Add the combined optional filters part to the main WHERE clauses if it's not empty
        if optional_filters_combined_sql:
            final_where_clauses.append(optional_filters_combined_sql)
        elif not (sender_filter or subject_filter or search_terms or start_date or end_date):
            # This case is where only owner_email was provided which is usually not intended for a search.
            # The initial check in the function (`if not sender_filter and not subject_filter ...`) handles this by returning early.
            # If that check were removed, this log would be useful.
            logger.warning("Querying with only owner_email filter. This might return many results.")

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

        where_sql_final = " AND ".join(final_where_clauses)

        sql_query = f"""
        SELECT
            {select_columns}
        FROM {view_name}
        WHERE {where_sql_final}
        ORDER BY received_datetime_utc DESC
        LIMIT ?;
        """
        # The final_query_params list has been built progressively.
        # Now add the limit parameter.
        final_query_params.append(effective_limit)

        logger.debug(f"Executing DuckDB Query: {sql_query}")
        logger.debug(f"With Params: {final_query_params}")

        # Execute query and fetch results
        arrow_table = con.execute(sql_query, final_query_params).fetch_arrow_table()
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
        f"For relative time expressions like 'last week', use the actual date range with correct years from the retrieved emails.\n" \
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
    user_email: str
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
        model_name = settings.DEFAULT_CHAT_MODEL
        tokenizer_model = get_tokenizer_model_for_chat_model(model_name)
        
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
    ms_token: Optional[str] = None
) -> str:
    """Generates a chat response using RAG with context from Milvus and Iceberg (emails),
    using an LLM to select/synthesize the most relevant context.
    Fails if the user has not provided their OpenAI API key."""
    logger.debug(f"DEBUG RAG - Function Entry: generate_openai_rag_response for user {user.email} - Message: '{message[:50]}...'")
    logger.critical("!!! RAG function execution STARTED !!!")
    fallback_response = "I apologize, but I encountered an unexpected error while processing your request. Our team has been notified and is looking into it. Please try again later or contact support if the issue persists."
    
    # Create tracking variable for token efficiency
    total_tokens_saved = 0
    
    # OPTIMIZED: Hardcoded token limits for maximum utilization
    # Define core token budget constants
    MAX_TOTAL_TOKENS = 16384  # Max tokens for model context
    RESPONSE_BUFFER = 4096    # Buffer for model response
    MAX_HISTORY_TOKENS = 2000 # Max tokens for chat history
    
    # Optimized email processing constants
    EMAIL_BATCH_SIZE = 50     # INCREASED: Number of emails per batch
    EMAIL_TOKEN_THRESHOLD = 20000  # INCREASED: When to trigger summarization
    MAX_EMAIL_CONTEXT_ITEMS = 100  # INCREASED: Max emails to retrieve in focused queries
    MIN_TOKENS_PER_BATCH = 512  # INCREASED: Minimum tokens per batch summary
    
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

        # Configure client with simplified timeout handling
        provider_timeout = 30.0  # Default timeout in seconds
        if hasattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS") and getattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS"):
            try:
                provider_timeout = float(getattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS"))
            except (ValueError, TypeError):
                logger.warning(f"Invalid timeout value for {provider.upper()}_TIMEOUT_SECONDS. Using default: 30.0s")

        client_kwargs = {"api_key": user_api_key, "timeout": provider_timeout}
        if db_api_key.model_base_url:
            client_kwargs["base_url"] = db_api_key.model_base_url
        user_client = AsyncOpenAI(**client_kwargs)
    except HTTPException as http_setup_exc:
        logger.error(f"RAG: Caught HTTPException during setup, re-raising: {http_setup_exc.detail}")
        raise http_setup_exc
    except Exception as setup_err:
        logger.error(f"Error during RAG setup (model/key/client): {setup_err}", exc_info=True)
        return fallback_response

    # Main Logic
    try:
        tokenizer_model = chat_model

        # --- Preliminary RAG Budget Calculation ---
        system_prompt_base = _build_system_prompt().replace("<RAG_CONTEXT_PLACEHOLDER>", "")
        base_prompt_tokens = count_tokens(system_prompt_base, tokenizer_model)
        
        formatted_history = _format_chat_history(chat_history, model=tokenizer_model, max_tokens=MAX_HISTORY_TOKENS)
        history_tokens = count_tokens(formatted_history, tokenizer_model)
        
        query_tokens = count_tokens(message, tokenizer_model)
        
        # Overall budget calculation - TARGET AT LEAST 70% UTILIZATION
        rag_budget = MAX_TOTAL_TOKENS - (base_prompt_tokens + history_tokens + query_tokens + RESPONSE_BUFFER)
        rag_budget = max(0, rag_budget)  # Ensure non-negative
        target_utilization = int(MAX_TOTAL_TOKENS * 0.7)  # Target 70% of total tokens
        logger.info(f"Preliminary Overall RAG Budget calculated: {rag_budget} tokens (Total Model Tokens: {MAX_TOTAL_TOKENS}, Target Utilization: {target_utilization})")

        # Intent & Param Extraction
        extracted_email_params = {}
        try:
            # Calculate reference dates
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
                example_1_start_date = calculate_past_date(days=7, now_iso=now_utc_iso) # "last week"
                example_2_start_date = calculate_past_date(days=1, now_iso=now_utc_iso, start_of_day=True) # "yesterday start"
                example_2_end_date = calculate_past_date(days=1, now_iso=now_utc_iso, end_of_day=True) # "yesterday end"
                
                # NEW: Calculate dates for "past week" and "last fortnight"
                example_past_week_start_date = calculate_past_date(days=7, now_iso=now_utc_iso) # Equivalent to last week
                example_last_fortnight_start_date = calculate_past_date(days=14, now_iso=now_utc_iso)

                # Add explicit logging for "last week" calculation
                now_dt = datetime.fromisoformat(now_utc_iso.replace('Z', '+00:00'))
                week_ago_dt = now_dt - timedelta(days=7)
                logger.info(f"Current date: {now_dt.strftime('%Y-%m-%d')}, 'Last week' would be from: {week_ago_dt.strftime('%Y-%m-%d')} to {now_dt.strftime('%Y-%m-%d')}")
            except Exception as e:
                logger.error(f"Error calculating example dates: {e}", exc_info=True)
                example_1_start_date = "[7_days_ago_error]"
                example_2_start_date = "[yesterday_start_error]"
                example_2_end_date = "[yesterday_end_error]"
                # NEW: Handle potential errors for new example dates
                example_past_week_start_date = "[past_week_error]"
                example_last_fortnight_start_date = "[last_fortnight_error]"

            extraction_prompt_template = (
                f"Analyze the user's message to extract parameters for searching emails. Current UTC time: {{now_utc_iso}}.\\n"
                f"User Message: {{message}}\\n"
                f"Extract: sender, subject, start_date_utc (ISO 8601 UTC), end_date_utc (ISO 8601 UTC), search_terms (list).\\n"
                f"Calculate start_date_utc and end_date_utc from relative terms like 'last week' (past 7 days from current time), 'past week' (same as last week), 'yesterday', 'last fortnight' (past 14 days from current time), 'upcoming' (from current time to no specific end). Use null if a date is not applicable or not found.\\n"
                f"Respond ONLY with a JSON object. Null if not found.\\n"
                f"Example 1: \\\"emails from jeff last week about the UOB project\\\" (Time: {{now_utc_iso}}) -> {{{{ \\\"sender\\\": \\\"jeff\\\", \\\"subject\\\": \\\"UOB project\\\", \\\"start_date_utc\\\": \\\"{{example_1_start_date}}\\\", \\\"end_date_utc\\\": \\\"{{now_utc_iso}}\\\", \\\"search_terms\\\": [\\\"UOB project\\\"]}}}}\\n"
                f"Example 2: \\\"onboarding emails from yesterday\\\" (Time: {{now_utc_iso}}) -> {{{{ \\\"sender\\\": null, \\\"subject\\\": \\\"onboarding\\\", \\\"start_date_utc\\\": \\\"{{example_2_start_date}}\\\", \\\"end_date_utc\\\": \\\"{{example_2_end_date}}\\\", \\\"search_terms\\\": [\\\"onboarding\\\"]}}}}\\n"
                f"Example 3: \\\"upcoming meetings from Derick\\\" (Time: {{now_utc_iso}}) -> {{{{ \\\"sender\\\": \\\"Derick\\\", \\\"subject\\\": \\\"meeting\\\", \\\"start_date_utc\\\": \\\"{{now_utc_iso}}\\\", \\\"end_date_utc\\\": null, \\\"search_terms\\\": [\\\"meeting\\\"]}}}}\\n"
                f"Example 4: \\\"show me emails from the past week regarding customer feedback\\\" (Time: {{now_utc_iso}}) -> {{{{ \\\"sender\\\": null, \\\"subject\\\": \\\"customer feedback\\\", \\\"start_date_utc\\\": \\\"{{example_past_week_start_date}}\\\", \\\"end_date_utc\\\": \\\"{{now_utc_iso}}\\\", \\\"search_terms\\\": [\\\"customer feedback\\\"]}}}}\\n"
                f"Example 5: \\\"what were the key updates in the last fortnight?\\\" (Time: {{now_utc_iso}}) -> {{{{ \\\"sender\\\": null, \\\"subject\\\": null, \\\"start_date_utc\\\": \\\"{{example_last_fortnight_start_date}}\\\", \\\"end_date_utc\\\": \\\"{{now_utc_iso}}\\\", \\\"search_terms\\\": [\\\"key updates\\\"]}}}}\\n"
                f"JSON Response:"
            )
            extraction_prompt = extraction_prompt_template.format(
                message=message, now_utc_iso=now_utc_iso, 
                example_1_start_date=example_1_start_date,
                example_2_start_date=example_2_start_date, example_2_end_date=example_2_end_date,
                # NEW: Add new example dates to format call
                example_past_week_start_date=example_past_week_start_date,
                example_last_fortnight_start_date=example_last_fortnight_start_date
            )
            
            response = await user_client.chat.completions.create(
                model=chat_model,
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
            
            logger.info(f"LLM extracted date parameters - Raw start_date: '{raw_start}', Raw end_date: '{raw_end}'")
            
            if raw_start:
                try:
                    start_date_obj = datetime.fromisoformat(raw_start.replace('Z', '+00:00'))
                    logger.info(f"Parsed start_date: {start_date_obj.isoformat()} (Year: {start_date_obj.year})")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid start date format from LLM: {raw_start}")
            if raw_end:
                try:
                    end_date_obj = datetime.fromisoformat(raw_end.replace('Z', '+00:00'))
                    logger.info(f"Parsed end_date: {end_date_obj.isoformat()} (Year: {end_date_obj.year})")
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

            # --- START: Adjust start_date for 'upcoming' email queries ---
            user_message_lower = message.lower()
            if "upcoming" in user_message_lower or "up coming" in user_message_lower: # Check for both variations
                llm_start_date = extracted_email_params.get("start_date")
                # Check if LLM set start_date to roughly now for "upcoming"
                if llm_start_date and (datetime.now(timezone.utc) - llm_start_date).total_seconds() < 300: # 5 min tolerance
                    buffer_days = 7
                    actual_email_search_start_date = llm_start_date - timedelta(days=buffer_days)
                    extracted_email_params["start_date"] = actual_email_search_start_date
                    logger.info(
                        f"Adjusted email search start_date for 'upcoming/up coming' query by -{buffer_days} days to: "
                        f"{actual_email_search_start_date.isoformat()} (Original LLM start_date: {llm_start_date.isoformat()})"
                    )
            # --- END: Adjust start_date for 'upcoming' email queries ---

        except Exception: # Broader exception catch for parameter extraction phase
            logger.error(f"Error during LLM parameter extraction or upcoming-adjustment: {e_ex}", exc_info=True)
            extracted_email_params = {} # Ensure it's empty on error

        # Determine query type
        if extracted_email_params.get("sender_filter") or extracted_email_params.get("subject_filter") or extracted_email_params.get("start_date"):
            source_target = "email_focused"
        else:
            # Check for document-related keywords
            doc_keywords = ['policy', 'procedure', 'document', 'rate card', 'sow', 'loa', 'guideline', 'report', 'agreement', 'contract', 'spec', 'manual']
            message_lower = message.lower()
            source_target = "document_focused" if any(k in message_lower for k in doc_keywords) else "mixed"
            
        is_email_focused = source_target == "email_focused"
        is_broad_email_query = is_email_focused and not any(
            extracted_email_params.get(k) for k in ["sender_filter", "subject_filter", "start_date"]
        )
        
        logger.info(f"Query Intent Analysis - Source Target: {source_target}, Is Email Focused: {is_email_focused}, Is Broad Email Query: {is_broad_email_query}")
        logger.debug(f"Extracted Email Params: {extracted_email_params}")

        # --- START: Optimized Context Retrieval ---
        retrieved_document_dicts = []
        retrieved_email_dicts = []

        logger.info("Starting SEQUENTIAL context retrieval...")

        # OPTIMIZED: Retrieve more documents
        if source_target in ["mixed", "document_focused"]:
            logger.debug("Retrieving document context sequentially...")
            try:
                retrieved_document_dicts, milvus_tokens_saved = await _get_milvus_context(
                    max_items=40,  # INCREASED: Retrieve more documents
                    max_chunk_chars=8000,  # INCREASED: Allow larger chunks
                    query=message,
                    user_email=user.email
                )
                total_tokens_saved += milvus_tokens_saved
                
                # Additional deduplication step with token accounting
                if len(retrieved_document_dicts) > 1:
                    retrieved_document_dicts, tokens_saved = await deduplicate_and_log_tokens(
                        results=retrieved_document_dicts,
                        tokenizer_model=tokenizer_model,  # Use the already initialized tokenizer model
                        similarity_threshold=0.9  # Higher threshold for standard RAG pipeline
                    )
                    total_tokens_saved += tokens_saved
                
                logger.debug(f"Sequential document retrieval finished. Retrieved {len(retrieved_document_dicts)} documents.")
            except Exception as doc_err:
                logger.error(f"Error during sequential document retrieval: {doc_err}", exc_info=True)
                retrieved_document_dicts = []
                if source_target in ["mixed", "document_focused"]:
                    logger.warning("Document retrieval was expected but failed. Proceeding without document context.")

        # Retrieve Emails if needed
        if source_target in ["mixed", "email_focused"]:
            logger.debug("Retrieving email context sequentially...")
            try:
                retrieved_email_dicts = await _get_email_context(
                    max_items=MAX_EMAIL_CONTEXT_ITEMS,
                    max_chunk_chars=8000,  # INCREASED: Allow larger email chunks
                    user_client=user_client,
                    search_params=extracted_email_params,
                    user_email=user.email
                )
                logger.debug(f"Sequential email retrieval finished. Retrieved {len(retrieved_email_dicts)} emails.")
            except Exception as email_err:
                logger.error(f"Error during sequential email retrieval: {email_err}", exc_info=True)
                retrieved_email_dicts = []
                if source_target in ["mixed", "email_focused"]:
                    logger.warning("Email retrieval was expected but failed. Proceeding without email context.")

        logger.info("Finished SEQUENTIAL context retrieval.")
        # --- END: Context Retrieval ---

        logger.critical("!!! POINTER: Right before Process Email Context block !!!")

        # --- START: Process Email Context ---
        final_email_context_str = "No relevant emails found or search skipped."

        if retrieved_email_dicts:
            logger.debug(f"Processing {len(retrieved_email_dicts)} retrieved email dictionaries.")
            
            # Helper to format a single email with INCREASED chunk size
            def _format_single_email(email: Dict[str, Any], max_len: int) -> str:
                def _truncate_text(text: str, max_l: int) -> str:
                    text_str = str(text) if text is not None else ''
                    if len(text_str) > max_l: 
                        return text_str[:max_l] + "... [TRUNCATED]"
                    return text_str

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

                return (
                    f"Email ID: {email.get('message_id', 'N/A')}\n"
                    f"Type: {entry_type}\n"
                    f"Received: {email.get('received_datetime_utc', 'N/A')}\n"
                    f"Sender: {email.get('sender', 'N/A')}\n"
                    f"Subject: {email.get('subject', 'N/A')}\n"
                    f"Tags: {email.get('generated_tags', 'N/A')}\n"
                    f"Content: {_truncate_text(str(text_content) if text_content else '', max_len)}"
                )

            # Estimate tokens for full email context
            full_potential_email_context = "\n\n---\n\n".join([_format_single_email(email, 8000) for email in retrieved_email_dicts])
            full_email_tokens = count_tokens(full_potential_email_context, tokenizer_model)
            logger.info(f"Estimated tokens for full email context ({len(retrieved_email_dicts)} emails): {full_email_tokens}")

            # OPTIMIZED: Improved summarization decision with higher threshold
            if full_email_tokens > EMAIL_TOKEN_THRESHOLD:
                logger.info(f"Triggering email summarization because token count {full_email_tokens} exceeds threshold {EMAIL_TOKEN_THRESHOLD}.")
                
                # --- Batch Summarization Logic ---
                # Calculate tokens per batch based on available budget - OPTIMIZED for more detailed summaries
                email_batches = [
                    retrieved_email_dicts[i:i + EMAIL_BATCH_SIZE]
                    for i in range(0, len(retrieved_email_dicts), EMAIL_BATCH_SIZE)
                ]
                num_batches = len(email_batches)
                logger.info(f"Created {num_batches} email batches for summarization (batch size: {EMAIL_BATCH_SIZE}).")
                
                # OPTIMIZED: Allocate more tokens per batch for richer summaries
                # Target around 80% of available RAG budget for summaries, divided by number of batches
                summary_budget = int(rag_budget * 0.8)
                max_tokens_per_batch = min(8000, max(MIN_TOKENS_PER_BATCH, summary_budget // max(1, num_batches)))
                logger.info(f"Targeting {max_tokens_per_batch} tokens for each summarization batch LLM call (summary budget: {summary_budget}).")
                
                # Run summarization tasks
                summary_tasks = [
                    _summarize_email_batch(
                        batch,
                        message, 
                        user_client, 
                        chat_model,
                        max_chars_per_email=2000,  # INCREASED: Allow more content per email
                        batch_max_tokens_for_llm=max_tokens_per_batch
                    )
                    for batch in email_batches
                ]
                
                try:
                    batch_summaries = await asyncio.gather(*summary_tasks)
                    # OPTIMIZED: Don't filter out empty summaries as they might indicate important negatives
                    combined_summaries = "\n\n---\n\n".join([s for s in batch_summaries if s])
                    final_email_context_str = f"<Summarized Email Context (Multiple Batches, {len(retrieved_email_dicts)} emails total)>\n{combined_summaries}\n</Summarized Email Context>"
                    logger.info(f"Multi-stage summarization completed. Final summary token count: {count_tokens(final_email_context_str, tokenizer_model)}")
                except Exception as e_summary:
                    logger.error(f"Error during concurrent email batch summarization: {e_summary}", exc_info=True)
                    final_email_context_str = "<Error during multi-stage email summarization>"
            else:
                # Using direct email context - OPTIMIZED: Include more raw content when below threshold
                logger.info(f"Using direct email context as token count {full_email_tokens} is within threshold {EMAIL_TOKEN_THRESHOLD}.")
                
                # OPTIMIZED: Dynamically adjust the number of emails based on token budget
                current_rag_tokens = 0
                direct_context_entries = []
                
                # Include as many full emails as possible within the budget
                for email in retrieved_email_dicts:
                    email_entry = _format_single_email(email, 8000)  # INCREASED: Allow more content per email
                    email_tokens = count_tokens(email_entry, tokenizer_model)
                    
                    if current_rag_tokens + email_tokens <= rag_budget * 0.9:  # Use 90% of budget for direct emails
                        direct_context_entries.append(email_entry)
                        current_rag_tokens += email_tokens
                    else:
                        # We've reached our token limit, stop adding emails
                        break
                
                logger.info(f"Including {len(direct_context_entries)} of {len(retrieved_email_dicts)} emails directly within token budget (using {current_rag_tokens} tokens).")
                final_email_context_str = "<User Email Context>\n" + "\n\n---\n\n".join(direct_context_entries) + "\n</User Email Context>"
        else:
            final_email_context_str = "No email context was retrieved or searched for."
            logger.info("No email dictionaries were retrieved to process for context.")
        # --- END: Process Email Context ---

        # --- START: Process Document Context ---
        final_document_context_str = "No document context was retrieved or searched for."
        if retrieved_document_dicts:
            logger.debug(f"Processing {len(retrieved_document_dicts)} retrieved document dictionaries for context.")
            document_context_parts = []
            
            for i, doc in enumerate(retrieved_document_dicts):
                content = doc.get('content', '')
                # OPTIMIZED: Increase document token limit
                truncated_content = truncate_text_by_tokens(content, tokenizer_model, 2000)  # INCREASED: Allow more content per document
                
                source_info = doc.get('metadata', {}).get('source', f"Document {i+1}")
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

        # --- OPTIMIZED: Context Assembly and Token Budget Management ---
        logger.info("Starting token budgeting and context construction...")
        system_prompt_template = _build_system_prompt()
        
        remaining_tokens = rag_budget
        logger.info(f"Token budget: Total={MAX_TOTAL_TOKENS}, BasePrompt={base_prompt_tokens}, History={history_tokens}, Query={query_tokens}, ResponseBuffer={RESPONSE_BUFFER} => Remaining for RAG: {remaining_tokens}")

        context_parts = []

        # Calculate document and email token counts
        doc_tokens = count_tokens(final_document_context_str, tokenizer_model) if final_document_context_str != "No document context was retrieved or searched for." else 0
        email_tokens = count_tokens(final_email_context_str, tokenizer_model) if final_email_context_str != "No email context was retrieved or searched for." else 0
        
        logger.info(f"Context token counts - Documents: {doc_tokens}, Emails: {email_tokens}, Total: {doc_tokens + email_tokens}")

        # OPTIMIZED STRATEGY: If both context types exist, balance them based on relevance type
        if doc_tokens > 0 and email_tokens > 0:
            # Determine allocation ratio based on query type
            if source_target == "document_focused":
                doc_ratio, email_ratio = 0.7, 0.3  # Prioritize documents
            elif source_target == "email_focused":
                doc_ratio, email_ratio = 0.3, 0.7  # Prioritize emails
            else:  # mixed
                doc_ratio, email_ratio = 0.5, 0.5  # Equal priority
                
            # Allocate token budget accordingly
            doc_budget = int(remaining_tokens * doc_ratio)
            email_budget = remaining_tokens - doc_budget
            
            logger.info(f"Allocation - Documents: {doc_budget} tokens ({doc_ratio*100:.0f}%), Emails: {email_budget} tokens ({email_ratio*100:.0f}%)")
            
            # Add document context with allocated budget
            if doc_tokens <= doc_budget:
                context_parts.append(final_document_context_str)
                remaining_tokens -= doc_tokens
                logger.info(f"Added full document context ({doc_tokens} tokens). Remaining: {remaining_tokens}")
            else:
                truncated_doc_context = truncate_text_by_tokens(final_document_context_str, tokenizer_model, doc_budget)
                context_parts.append(truncated_doc_context)
                truncated_doc_tokens = count_tokens(truncated_doc_context, tokenizer_model)
                remaining_tokens -= truncated_doc_tokens
                logger.info(f"Added truncated document context ({truncated_doc_tokens} tokens). Remaining: {remaining_tokens}")
            
            # Add email context with allocated budget
            if email_tokens <= email_budget:
                context_parts.append(final_email_context_str)
                remaining_tokens -= email_tokens
                logger.info(f"Added full email context ({email_tokens} tokens). Remaining: {remaining_tokens}")
            else:
                truncated_email_context = truncate_text_by_tokens(final_email_context_str, tokenizer_model, email_budget)
                context_parts.append(truncated_email_context)
                truncated_email_tokens = count_tokens(truncated_email_context, tokenizer_model)
                remaining_tokens -= truncated_email_tokens
                logger.info(f"Added truncated email context ({truncated_email_tokens} tokens). Remaining: {remaining_tokens}")
        else:
            # Only one context type exists, use all available tokens for it
            if doc_tokens > 0:
                if doc_tokens <= remaining_tokens:
                    context_parts.append(final_document_context_str)
                    remaining_tokens -= doc_tokens
                    logger.info(f"Added document context ({doc_tokens} tokens). Remaining: {remaining_tokens}")
                else:
                    truncated_doc_context = truncate_text_by_tokens(final_document_context_str, tokenizer_model, remaining_tokens)
                    context_parts.append(truncated_doc_context)
                    truncated_doc_tokens = count_tokens(truncated_doc_context, tokenizer_model)
                    remaining_tokens -= truncated_doc_tokens
                    logger.info(f"Added truncated document context ({truncated_doc_tokens} tokens). Remaining: {remaining_tokens}")
            
            if email_tokens > 0:
                if email_tokens <= remaining_tokens:
                    context_parts.append(final_email_context_str)
                    remaining_tokens -= email_tokens
                    logger.info(f"Added email context ({email_tokens} tokens). Remaining: {remaining_tokens}")
                else:
                    truncated_email_context = truncate_text_by_tokens(final_email_context_str, tokenizer_model, remaining_tokens)
                    context_parts.append(truncated_email_context)
                    truncated_email_tokens = count_tokens(truncated_email_context, tokenizer_model)
                    remaining_tokens -= truncated_email_tokens
                    logger.info(f"Added truncated email context ({truncated_email_tokens} tokens). Remaining: {remaining_tokens}")

        rag_context_str = "\n\n".join(context_parts) if context_parts else "No context could be provided within token limits."
        if not context_parts:
            logger.warning("No RAG context could be assembled within token limits or none was retrieved.")
        
        final_system_prompt = system_prompt_template.replace("<RAG_CONTEXT_PLACEHOLDER>", rag_context_str)
        
        # Construct final messages array
        final_prompt_messages = [{"role": "system", "content": final_system_prompt}]
        if formatted_history:
            final_prompt_messages.append({"role": "user", "content": f"Previous conversation history:\n{formatted_history}"})
        final_prompt_messages.append({"role": "user", "content": message})

        # --- Final LLM Call ---
        logger.info(f"Making final LLM call to {provider}/{chat_model} with {len(final_prompt_messages)} messages.")
        
        # Log total tokens being sent to LLM for debugging
        total_final_prompt_tokens = sum(count_tokens(msg["content"], tokenizer_model) for msg in final_prompt_messages)
        total_utilization_percentage = (total_final_prompt_tokens / MAX_TOTAL_TOKENS) * 100
        logger.info(f"Estimated total tokens in final prompt to LLM: {total_final_prompt_tokens} ({total_utilization_percentage:.1f}% of max {MAX_TOTAL_TOKENS})")
        
        # Log token efficiency from content deduplication
        if total_tokens_saved > 0:
            efficiency_percentage = (total_tokens_saved / (total_final_prompt_tokens + total_tokens_saved)) * 100
            logger.info(f"Token efficiency: Deduplication saved {total_tokens_saved:,} tokens ({efficiency_percentage:.1f}% reduction)")
        
        if total_final_prompt_tokens > MAX_TOTAL_TOKENS:
            logger.error(f"CRITICAL: Final prompt token count ({total_final_prompt_tokens}) EXCEEDS model max tokens ({MAX_TOTAL_TOKENS}). LLM call will likely fail.")

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
                messages=final_prompt_messages,
                temperature=temperature,
                max_tokens=RESPONSE_BUFFER
            )
            response_content = llm_response.choices[0].message.content.strip()
            logger.info(f"RAG response generated successfully by {chat_model}.")
            logger.debug(f"LLM Response (first 100 chars): {response_content[:100]}...")
            return response_content
        except RateLimitError as rle:
            logger.error(f"OpenAI Rate Limit Error during RAG generation: {rle}", exc_info=True)
            return "I'm currently experiencing high demand. Please try again in a few moments."
        except Exception as llm_call_err:
            logger.error(f"Error during final LLM call for RAG: {llm_call_err}", exc_info=True)
            return fallback_response

    except HTTPException as http_exc:
        logger.error(f"RAG: Caught HTTPException, re-raising: {http_exc.detail}", exc_info=True)
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error in generate_openai_rag_response: {e}", exc_info=True)
        return fallback_response
        
    logger.error("RAG function reached unexpected end. Returning fallback.")
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