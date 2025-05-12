import logging
import json
import re
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from openai import AsyncOpenAI, RateLimitError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User
from app.crud import api_key_crud
from app.utils.security import decrypt_token
from app.services.milvus import count_tokens, truncate_text_by_tokens, get_tokenizer_model_for_chat_model, deduplicate_and_log_tokens
from app.services.embedder import search_milvus_knowledge_hybrid, rerank_results, create_retrieval_embedding, search_milvus_knowledge

# Set up logger for this module
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

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

async def get_rate_card_response_advanced(
    message: str,
    chat_history: List[Dict[str, str]],
    user: User,
    db: Session,
    model_id: Optional[str] = None,
    ms_token: Optional[str] = None
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
        
        # Use from services.milvus import to get the _format_chat_history function
        # For now we'll define it inline since this is transitional code
        from app.services.milvus import truncate_text_by_tokens
        
        def _format_chat_history(chat_history, model, max_tokens=None):
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
                    truncated_history = truncate_text_by_tokens(full_history_str, model, max_tokens)
                    return truncated_history
                    
            return full_history_str
            
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