import logging
import json
import re
import hashlib
import difflib
from typing import Dict, Any, List, Optional, Tuple

from app.config import settings
from app.services.embedder import search_milvus_knowledge_hybrid, rerank_results, create_retrieval_embedding, deduplicate_results, search_milvus_knowledge

# Set up logger for this module
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

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

# --- Helper function for token counting ---
_token_encoders = {}

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Estimates the number of tokens for a given text and model."""
    if model not in _token_encoders:
        try:
            import tiktoken
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
                import tiktoken
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

# --- START: Milvus Context Retrieval Helper ---
async def get_milvus_context(
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
    logger.debug(f"get_milvus_context called with query: '{query[:50]}...', limit: {max_items}")
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
            
        logger.info(f"get_milvus_context retrieved {len(document_results)} documents.")
        return document_results, tokens_saved
    except Exception as e_milvus:
        logger.error(f"Error during Milvus document retrieval in get_milvus_context: {e_milvus}", exc_info=True)
        return [], tokens_saved  # Return empty list and 0 tokens saved on error 