import logging
from typing import Dict, Any, List, Optional, Tuple, Union

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.models.email import EmailContent, EmailAnalysis

# Set up logger for this module
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

# Keep the global client for backward compatibility
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Import the modular components
from app.rag.email_rag import (
    analyze_email_content as _analyze_email_content,
    extract_email_search_parameters_for_iceberg, 
    get_email_context, 
    summarize_email_batch
)
from app.rag.ratecard_rag import get_rate_card_response_advanced
from app.orchestration.tool_router import (
    generate_openai_rag_response,
    call_jarvis_router, 
    synthesize_answer_from_context
)
from app.services.milvus import (
    get_milvus_context,
    count_tokens,
    get_tokenizer_model_for_chat_model,
    truncate_text_by_tokens,
    deduplicate_and_log_tokens
)
from app.services.duckdb import (
    query_iceberg_emails_duckdb,
    get_duckdb_conn,
    get_iceberg_catalog
)

# For backward compatibility with old imports
# This allows code to still import from llm.py while actually using
# the modular implementations
async def analyze_email_content(email: EmailContent) -> EmailAnalysis:
    """Wrapper for backward compatibility"""
    return await _analyze_email_content(email, client)

# Re-export all the functions
__all__ = [
    'analyze_email_content',
    'extract_email_search_parameters_for_iceberg',
    'get_email_context',
    'summarize_email_batch',
    'get_rate_card_response_advanced',
    'generate_openai_rag_response',
    'call_jarvis_router',
    'synthesize_answer_from_context',
    'get_milvus_context',
    'query_iceberg_emails_duckdb',
    'get_duckdb_conn',
    'get_iceberg_catalog',
    'client',
]