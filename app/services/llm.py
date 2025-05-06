import re

# Ensure query_features is a dict even after fallback
if query_features is None: query_features = {}

logger.debug(f"RateCardRAG: Extracted query features: {query_features}")

# Extract requested document type
requested_doc_type = query_features.get('document_type')
if requested_doc_type == 'unknown': requested_doc_type = None # Treat unknown as None

# --- START: Revised Filename Terms Logic ---
filename_terms_for_search = []
# Try to match "original_filename is X" or "original_filename = X" (case-insensitive)
# This regex captures the content X, optionally handling quotes around X, and stops before a file extension dot.
filename_pattern = r"original_filename\s*(?:is|=)\s*['"]?([^.'"]+)['"]?"
explicit_fn_match = re.search(filename_pattern, message, re.IGNORECASE)

if explicit_fn_match:
    explicit_filename_part = explicit_fn_match.group(1).strip()
    # Split by common delimiters (space, underscore, hyphen) and filter out short/common words
    raw_terms = re.split(r'[\s_-]+', explicit_filename_part)
    # Filter terms: length > 1 and not common stop words (simplified here)
    common_stopwords = {"and", "the", "is", "of", "for", "a", "to", "v"} # 'v' for 'v3' etc.
    filename_terms_for_search = [term for term in raw_terms if len(term) > 1 and term.lower() not in common_stopwords]
    if filename_terms_for_search: # Only log if we actually got terms this way
        logger.info(f"RateCardRAG: Extracted explicit filename terms from query: {filename_terms_for_search}")
    else: # If splitting/filtering yielded nothing, clear it to trigger fallback
        logger.info(f"RateCardRAG: Explicit filename matched ('{explicit_filename_part}') but resulted in no usable terms after filtering.")
        filename_terms_for_search = [] # Ensure it's empty to allow fallback

# Fallback or augmentation if no explicit filename terms were successfully extracted
if not filename_terms_for_search:
    logger.info("RateCardRAG: No explicit filename terms extracted or used. Falling back to role/doc_type based terms.")
    role_term = query_features.get('role')
    if role_term:
        # Split role_term itself if it's multi-word, e.g., "MAS Rate Card" -> ["MAS", "Rate", "Card"]
        filename_terms_for_search.extend([term for term in re.split(r'[\s_-]+', role_term) if len(term) > 1])

    # Add requested_doc_type to filename terms if it's specific
    if requested_doc_type and requested_doc_type not in ['general info', 'unknown', None]:
         # Split doc type too if it's multi-word like "rate card"
        filename_terms_for_search.extend([term for term in re.split(r'[\s_-]+', requested_doc_type) if len(term) > 1])

    # Default "rate", "card" terms if it seems relevant and terms are still sparse or missing defaults
    is_rate_card_query_flag = "rate card" in message.lower() # Specific to this function
    if is_rate_card_query_flag or requested_doc_type == "rate card":
        current_terms_lower = {t.lower() for t in filename_terms_for_search}
        if 'rate' not in current_terms_lower and 'rates' not in current_terms_lower:
            filename_terms_for_search.append('rate')
        if 'card' not in current_terms_lower and 'cards' not in current_terms_lower:
            filename_terms_for_search.append('card')

# Deduplicate and filter empty strings finally
filename_terms_for_search = list(set(term for term in filename_terms_for_search if term and term.strip()))
logger.debug(f"RateCardRAG: Final filename terms for pre-filtering: {filename_terms_for_search}")
# --- End Revised Filename Terms Logic ---

# 3. Construct Multi-Vector Retrieval Queries
# MODIFIED: Call the new hybrid search function for each query vector
for i, q in enumerate(retrieval_queries):
    logger.debug(f"RateCardRAG: Performing HYBRID search for query: '{q}'")
    # Determine target collection name (RAG collection)
    sanitized_email = user.email.replace('@', '_').replace('.', '_')
    target_collection_name = f"{sanitized_email}_knowledge_base_bm"

        # Boost candidate pool and increase ef for better recall
    k_per_query = max(k_per_query, int(getattr(settings, 'RATE_CARD_RESULTS_PER_QUERY', 3)) * 2)
    search_params = {"metric_type": "COSINE", "params": {"ef": 256}}

    # Call the hybrid function with the filename terms list
    hybrid_results = await search_milvus_knowledge_hybrid(
        query_text=q,  # Pass the actual query text
        collection_name=target_collection_name,
        limit=k_per_query,
        search_params=search_params,
        filename_terms=filename_terms_for_search
    )
    # The hybrid function returns a single list of fused results for the query