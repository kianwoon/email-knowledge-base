import json
import re  # For rate-card dollar filtering
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import logging # Import logging

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.models.user import User # Assuming User model is here
# Import RAG components
from app.services.embedder import create_embedding, search_qdrant_knowledge, create_retrieval_embedding, search_qdrant_knowledge_sparse
from app.crud import api_key_crud # Import API key CRUD
from fastapi import HTTPException, status # Import HTTPException
from qdrant_client import models
import itertools  # for merging hybrid search results

# Set up logger for this module
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

# Keep the global client for other potential uses (like analyze_email_content)
# But Jarvis chat will use a user-specific key if available.
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


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


# Updated function to accept user email AND DB session for key lookup
async def generate_openai_rag_response(
    message: str, 
    chat_history: List[Dict[str, str]], 
    user: User,
    db: Session, # Database session
    model_id: Optional[str] = None  # Override the default LLM model
) -> str:
    """
    Generates a chat response using RAG and the USER'S OpenAI API key.
    Fails if the user has not provided their OpenAI API key.
    """
    try:
        # Determine which model to use: user-selected or default
        chat_model = model_id or settings.OPENAI_MODEL_NAME
        logger.debug(f"Using LLM model: {chat_model}")
        # 1. Get USER's OpenAI API Key
        logger.debug(f"Attempting to retrieve user's OpenAI API key for {user.email}")
        user_openai_key = api_key_crud.get_decrypted_api_key(db, user.email, "openai")

        if not user_openai_key:
            logger.warning(f"User {user.email} does not have an OpenAI API key set for Jarvis.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OpenAI API key is required for Jarvis. Please add your key in the settings."
            )
        
        logger.debug(f"Using user's personal OpenAI key for {user.email}")
        # Initialize a client SPECIFICALLY with the user's key for this request
        # --- Increased timeout to 30 seconds --- 
        user_client = AsyncOpenAI(
            api_key=user_openai_key, 
            timeout=30.0 # Set timeout to 30 seconds
        )
        # --- End Timeout Increase ---

        # 2. Create embedding for the user message (can still use system key client? Let's use user key)
        # Potentially switch embedding to use user_client too if needed, or keep using global client
        # For now, let's use the user_client for embedding as well for consistency
        # --- START: Query refinement step to extract table and role for retrieval ---
        retrieval_query = message
        refined = None # Initialize refined variable
        # --- MODIFICATION: Skip refinement for rate card queries ---
        if 'rate card' not in message.lower():
            try:
                refine_msgs = [
                    {"role": "system", "content": (
                        "You are a query refiner. Extract the target table/section and the entity from the user question. "
                        "Return JSON with keys 'table' and 'role'."
                    )},
                    {"role": "user", "content": (
                        f"Question: {message}\nRespond with JSON: {{\"table\":\"...\", \"role\":\"...\"}}."
                    )}
                ]
                resp_refine = await user_client.chat.completions.create(
                    model=chat_model,
                    messages=refine_msgs,
                    temperature=0.0
                )
                refined = json.loads(resp_refine.choices[0].message.content)
                # Build a concise retrieval query
                parts = []
                if refined.get('table'): parts.append(refined['table'])
                if refined.get('role'): parts.append(refined['role'])
                if parts:
                    retrieval_query = ' '.join(parts)
                logger.debug(f"RAG: Refined retrieval query: {retrieval_query}")
            except Exception as e:
                logger.warning(f"Query refinement failed, using original message: {e}", exc_info=True)
        else:
            logger.debug("RAG: Skipping query refinement for rate card query.")
        # --- END MODIFICATION ---
        # --- END: Query refinement ---
        # Store the original retrieval query before refinement/expansion
        orig_retrieval_query = retrieval_query
        # --- START: Query expansion for synonyms ---
        if getattr(settings, 'ENABLE_QUERY_EXPANSION', False):
            try:
                expand_msgs = [
                    {"role": "system", "content": (
                        "You are a synonym expander. Given a query, return an expanded query including synonyms, separated by commas. Output only plain text."
                    )},
                    {"role": "user", "content": f"Expand the following query to include synonyms: {retrieval_query}"}
                ]
                exp_resp = await user_client.chat.completions.create(
                    model=chat_model,
                    messages=expand_msgs,
                    temperature=0.0
                )
                expanded = exp_resp.choices[0].message.content.strip()
                if expanded:
                    retrieval_query = expanded
                    logger.debug(f"RAG: Expanded retrieval query: {retrieval_query}")
            except Exception as e:
                logger.warning(f"Query expansion failed, using original retrieval_query: {e}", exc_info=True)
        # --- END: Query expansion ---
        
        # --- START: HyDE (Hypothetical Document Embedding) Generation ---
        hyde_document = retrieval_query # Default to retrieval_query if HyDE fails
        # --- MODIFICATION: Skip HyDE for rate card queries ---
        if 'rate card' not in message.lower() and getattr(settings, 'ENABLE_HYDE', True): # Enable HyDE by default, controlled by setting
            try:
                hyde_msgs = [
                    {"role": "system", "content": (
                        "You are an assistant that generates a concise, factual hypothetical document "
                        "that directly answers the user's question. Output only the document content, no extra text."
                    )},
                    {"role": "user", "content": f"Generate a hypothetical document answering: {message}"} # Use original message for HyDE prompt
                ]
                hyde_resp = await user_client.chat.completions.create(
                    model=chat_model, # Use the same chat model
                    messages=hyde_msgs,
                    temperature=0.0 # Low temp for factual generation
                )
                generated_doc = hyde_resp.choices[0].message.content.strip()
                if generated_doc:
                    hyde_document = generated_doc
                    logger.debug(f"RAG: Generated HyDE document: {hyde_document[:100]}...") # Log snippet
                else:
                    logger.warning("HyDE generation returned empty content, using original retrieval_query for embedding.")
            except Exception as e:
                logger.warning(f"HyDE generation failed, using original retrieval_query for embedding: {e}", exc_info=True)
        elif 'rate card' in message.lower():
             logger.debug("RAG: Skipping HyDE generation for rate card query.")
        # --- END MODIFICATION ---
        # --- END: HyDE Generation ---

        # --- Use HyDE document (or retrieval_query if HyDE skipped/failed) for DENSE/COLBERT embeddings ---
        logger.debug(f"Creating dense/colbert embeddings based on: '{hyde_document[:50]}...' using user key")
        # Generate field-specific embeddings using hyde_document
        dense_emb = await create_retrieval_embedding(hyde_document, "dense")

        # Log a snippet of the query embedding (now potentially based on retrieval_query if HyDE skipped)
        embedding_snippet = str(dense_emb[:5]) + "..." if dense_emb else "None"
        logger.debug(f"RAG: Using query embedding (first 5 elements): {embedding_snippet}")
        
        # --- Existing Search Logic Starts Here ---
        # 3. Determine user-specific collection name and search
        sanitized_email = user.email.replace('@', '_').replace('.', '_')
        # Derive BM hybrid collection for dense, colbertv2.0, and bm25 embeddings
        bm_collection = f"{sanitized_email}_knowledge_base_bm"
        logger.info(f"RAG: Targeting hybrid Qdrant collection: '{bm_collection}' for user {user.email}")

        # Build a generic tag filter: honor only explicit 'tag:<value>' directives
        tag_filter = None
        directive_match = re.search(r'\btag[:=]\s*([A-Za-z0-9 _-]+)', message, re.IGNORECASE)
        if directive_match:
            tag_val = directive_match.group(1).strip().lower()
            tag_filter = models.Filter(
                must=[models.FieldCondition(key="tag", match=models.MatchValue(value=tag_val))]
            )
            logger.debug(f"RAG: Applying metadata filter for tag directive '{tag_val}'")
        # Log and run Qdrant search with optional metadata filter
        logger.debug(f"RAG: Running Qdrant search for query: '{retrieval_query[:50]}...' with limit {settings.RAG_SEARCH_LIMIT} and filter={tag_filter}")
        
        # --- Dense search uses embedding from HyDE or retrieval_query ---
        dense_hits = await search_qdrant_knowledge(
            query_embedding=dense_emb, # Use dense_emb (from HyDE or retrieval_query)
            limit=settings.RAG_SEARCH_LIMIT * 2,
            collection_name=bm_collection,
            qdrant_filter=tag_filter,
            vector_name="dense"
        )
        # --- Attempt ColBERT embedding & search; skip if NotImplemented --- 
        try:
            colbert_emb = await create_retrieval_embedding(hyde_document, "colbertv2.0") # Use same source as dense
            colbert_hits = await search_qdrant_knowledge(
                query_embedding=colbert_emb, 
                limit=settings.RAG_SEARCH_LIMIT * 2,
                collection_name=bm_collection,
                qdrant_filter=tag_filter,
                vector_name="colbertv2.0"
            )
        except NotImplementedError:
            logger.warning("ColBERT embedding not implemented; skipping colbertv2.0 search")
            colbert_hits = []
        
        # --- Attempt BM25 sparse search using original retrieval_query --- 
        try:
            # Note: BM25 uses the text query directly (retrieval_query), not a dense embedding or HyDE doc
            bm25_hits = await search_qdrant_knowledge_sparse( # New function call
                query_text=retrieval_query, # USE ORIGINAL/REFINED QUERY for sparse
                limit=settings.RAG_SEARCH_LIMIT * 2, # Consider separate limit?
                collection_name=bm_collection,
                qdrant_filter=tag_filter,
                vector_name="bm25" # Specify the sparse vector name
            )
            logger.debug(f"BM25 search (using retrieval_query) returned {len(bm25_hits)} hits.")
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}", exc_info=True)
            bm25_hits = []

        # Merge and dedupe by ID, keeping the highest score
        merged = {}
        # Include bm25_hits in the merge process
        for hit in itertools.chain(dense_hits, colbert_hits, bm25_hits):
            if hit['id'] in merged:
                merged[hit['id']]['score'] = max(merged[hit['id']]['score'], hit['score'])
            else:
                merged[hit['id']] = hit
        # Sort merged hits and select top results
        search_results = sorted(merged.values(), key=lambda x: x['score'], reverse=True)[:settings.RAG_SEARCH_LIMIT * 2]
        logger.debug(f"RAG: Hybrid Qdrant search returned {len(search_results)} merged hits from '{bm_collection}' before reranking/filtering")
        # For rate-card queries, try snippet-only filter first
        if ('rate card' in message.lower() or 'rate for' in message.lower()):
            try:
                snippet_filter = models.Filter(
                    must=[models.FieldCondition(key="source", match=models.MatchValue(value="snippet"))]
                )
                snippet_hits = await search_qdrant_knowledge(
                    query_embedding=dense_emb, # Use dense_emb (from HyDE or retrieval_query)
                    limit=settings.RAG_SEARCH_LIMIT,
                    collection_name=bm_collection,
                    qdrant_filter=snippet_filter,
                    vector_name="dense"
                )
                if snippet_hits:
                    search_results = snippet_hits
                    logger.debug(f"RAG: Using snippet-only hits for rate-card query, found {len(search_results)} chunks")
            except Exception as e:
                logger.warning(f"Snippet-only Qdrant search failed: {e}", exc_info=True)
        # Log the raw search result length AND the results themselves for inspection
        logger.debug(f"RAG: Qdrant search returned {len(search_results)} hits from '{bm_collection}'")
        logger.debug(f"RAG: Raw search results: {search_results}")
        # Fallback: if we filtered by tag but got zero hits, retry without tag filter
        if tag_filter and not search_results:
            logger.warning("RAG: No hits with tag filter, falling back to unfiltered search")
            # Fallback needs embedding based on hyde_document or retrieval_query
            search_results = await search_qdrant_knowledge(
                query_embedding=dense_emb, # Use existing dense_emb
                limit=settings.RAG_SEARCH_LIMIT,
                collection_name=bm_collection,
                vector_name="default"
            )
        # --- Fallback logic for Query Expansion (unrelated to HyDE skip) ---
        if not search_results and getattr(settings, 'ENABLE_QUERY_EXPANSION', False):
            logger.warning("RAG: No results after query expansion, retrying with original query")
            # Recreate embedding for original query - **Use original retrieval query for embedding here**
            orig_query_embedding = await create_embedding(orig_retrieval_query, client=user_client)
            logger.debug(f"RAG: Running Qdrant fallback search for original query: '{orig_retrieval_query[:50]}...' with limit {settings.RAG_SEARCH_LIMIT}")
            search_results = await search_qdrant_knowledge(
                query_embedding=orig_query_embedding,
                limit=settings.RAG_SEARCH_LIMIT,
                collection_name=bm_collection,
                vector_name="default"
            )
            logger.debug(f"RAG: Qdrant fallback search returned {len(search_results)} hits from '{bm_collection}'")

        # --- Start: LLM-based chunk classification to handle arbitrary layouts ---
        if 'rate card' not in message.lower() and 'rate for' not in message.lower():
            # Only classify chunks for non-rate-card queries
            try:
                # Prepare chunks for classification
                chunk_texts = [hit['payload']['content'] for hit in search_results]
                class_messages = [
                    {"role": "system", "content": (
                        "You are a classification assistant. Given a user question and a list of text chunks, "
                        "return ONLY a JSON object mapping chunk indices to \"yes\" or \"no\" indicating whether "
                        "each chunk is useful to answer the question. Do not include any additional text or markdown."
                    )},
                    {"role": "user", "content": (
                        f"User question: {message}\nChunks:\n" +
                        "\n".join(f"Chunk {i+1}: {txt}" for i, txt in enumerate(chunk_texts)) +
                        "\nRespond with only a JSON object mapping each chunk number to 'yes' or 'no'. No extra text."
                    )}
                ]
                class_resp = await user_client.chat.completions.create(
                    model=chat_model,
                    messages=class_messages,
                    temperature=0.0
                )
                # Debug: log raw classification response
                logger.debug(f"Classification response content: {class_resp.choices[0].message.content}")
                decisions = json.loads(class_resp.choices[0].message.content)
                # Filter only chunks marked 'yes'
                classified = [hit for idx, hit in enumerate(search_results, start=1)
                              if decisions.get(str(idx), "no").lower() == "yes"]
                if classified:
                    search_results = classified
                logger.debug(f"RAG: Post-classification filtered hits: {len(search_results)}")
            except Exception as e:
                logger.warning(f"Chunk classification failed, using original hits: {e}", exc_info=True)
        else:
            # Skip classification for rate-card queries to preserve table chunks
            logger.debug("RAG: Skipping chunk classification for rate-card/table style query")
        # --- End: LLM-based classification ---

        # --- START: MAS-Specific Context Filtering (Moved earlier) --- 
        mas_filter_applied = False # Flag to track if MAS filter reduced chunks
        if 'mas' in message.lower():
            original_count = len(search_results)
            pre_mas_filter_results = search_results.copy() # Keep a copy before filtering
            search_results = [
                hit for hit in search_results 
                if 'mas' in hit.get('payload', {}).get('metadata', {}).get('original_filename', '').lower()
            ]
            if len(search_results) < original_count:
                logger.debug(f"RAG: Applied PRE-RERANK MAS-specific context filter. Kept {len(search_results)}/{original_count} chunks from MAS documents.")
                # If filtering removed everything, fallback to original results before MAS filter to avoid empty context later
                if not search_results:
                    logger.warning("RAG: MAS-specific filter removed all chunks, reverting to pre-MAS-filter results to avoid empty context.")
                    search_results = pre_mas_filter_results
                else:
                    mas_filter_applied = True # Set flag only if filter actually removed chunks
            else:
                logger.debug("RAG: PRE-RERANK MAS-specific context filter applied, but all retrieved chunks were already from MAS documents.")
        # --- END: MAS-Specific Context Filtering ---

        # --- START: GIC-Specific Context Filtering ---
        gic_filter_applied = False # Flag to track if GIC filter reduced chunks
        # Apply if 'gic' is in query AND 'mas' is NOT, to avoid conflict if comparing
        if 'gic' in message.lower() and 'mas' not in message.lower():
            original_count = len(search_results)
            pre_gic_filter_results = search_results.copy() # Keep a copy before filtering
            gic_doc_name = "SOW - Data Vendor Resource Augmentation DVRA (Beyondsoft) - 3.pdf" # Define the target GIC doc filename
            search_results = [
                hit for hit in search_results
                if gic_doc_name.lower() in hit.get('payload', {}).get('metadata', {}).get('original_filename', '').lower()
            ]
            if len(search_results) < original_count:
                logger.debug(f"RAG: Applied PRE-RERANK GIC-specific context filter. Kept {len(search_results)}/{original_count} chunks from GIC document ('{gic_doc_name}').")
                # Fallback if GIC filter removed everything
                if not search_results:
                    logger.warning("RAG: GIC-specific filter removed all chunks, reverting to pre-GIC-filter results to avoid empty context.")
                    search_results = pre_gic_filter_results
                else:
                    gic_filter_applied = True # Set flag only if filter actually removed chunks
            else:
                logger.debug("RAG: PRE-RERANK GIC-specific context filter applied, but all retrieved chunks were already from the GIC document.")
        # --- END: GIC-Specific Context Filtering ---

        # Currency-value filtering for rate-card queries: keep only relevant chunks
        # --- MODIFICATION: Skip if MAS or GIC filter already applied ---
        logger.debug(f"RAG: Checking currency filter. mas_filter_applied = {mas_filter_applied}, gic_filter_applied = {gic_filter_applied}") # Log the flags
        if not mas_filter_applied and not gic_filter_applied and ('rate card' in message.lower() or 'rate for' in message.lower()):
            logger.debug("RAG: Applying currency-value filter (MAS/GIC filter was not applied or did not reduce chunks)") # Modified log
            orig_chunks = search_results.copy()
            # Match $, S$, or SGD amounts or comma-formatted numbers (e.g., 4,600)
            pattern = re.compile(r"(?:\\$\\s?\\d|S\\$\\s?\\d|SGD\\s?\\d|\\d{1,3}(?:,\\d{3})+)")
            filtered = [hit for hit in search_results if pattern.search(hit.get('payload', {}).get('content', ''))]
            if filtered:
                search_results = filtered
                logger.debug(f"RAG: Applied currency-value filter, kept {len(search_results)}/{len(orig_chunks)} chunks")
            else:
                logger.debug("RAG: No currency-value chunks found, skipping currency-value filter and keeping all chunks")
            # Fallback substring match for the extracted role if present
            # -- MODIFICATION: Skip fallback if role seems generic like 'rate card' --
            role_extracted = False
            role = None
            if isinstance(refined, dict) and refined.get('role'): # Check if refined exists
                role = refined['role'].strip().lower()
                # Check if the role is likely generic (e.g., is 'rate card' or very short)
                if role and role != 'rate card' and len(role) > 3:
                    role_extracted = True
                else:
                    logger.debug(f"RAG: Skipping role fallback filter because extracted role '{role}' seems generic.")
                    role = None # Prevent using the generic role
            
            if role_extracted and role: # Only apply if we have a specific, non-generic role
            # -- END MODIFICATION --
                substring_hits = [
                    hit for hit in orig_chunks # Apply to original chunks before currency filter? Let's stick to applying it AFTER currency filter for now.
                    if role in hit.get('payload', {}).get('content', '').lower()
                ]
                # Only apply if it finds something AND it's different from the currency filter result
                if substring_hits and len(substring_hits) != len(search_results):
                    search_results = substring_hits
                    logger.debug(f"RAG: Applied specific role substring filter for '{role}', kept {len(search_results)}/{len(orig_chunks)} chunks")
                elif not substring_hits:
                     logger.debug(f"RAG: Specific role '{role}' not found in currency-filtered chunks, keeping currency results.")
                else:
                    logger.debug(f"RAG: Specific role '{role}' filter matched all currency chunks, no change.")

            # If 'tag:' directive was used, reapply that filter after fallback
            if directive_match:
                tag_val = directive_match.group(1).strip().lower()
                tag_hits = [hit for hit in search_results
                            if hit.get('payload', {}).get('tag', '').lower() == tag_val]
                if tag_hits:
                    search_results = tag_hits
                    logger.debug(f"RAG: Reapplied tag filter '{tag_val}', kept {len(tag_hits)}/{len(orig_chunks)} chunks")
        elif mas_filter_applied: # Added log for skipping
            logger.debug("RAG: Skipping currency-value filter because MAS filter was applied and reduced chunks.")
        # --- End: LLM-based classification ---

        # Local reranking using OpenAI embeddings and cosine similarity
        if settings.ENABLE_RERANK and search_results:
            try:
                # Extract document texts
                docs = [hit["payload"]["content"] for hit in search_results]
                # Generate embeddings for each doc using user's API key
                doc_embeddings = [
                    await create_embedding(text, client=user_client)
                    for text in docs
                ]
                # Cosine similarity helper
                import math
                def cos_sim(a, b):
                    dot = sum(x*y for x, y in zip(a, b))
                    norm_a = math.sqrt(sum(x*x for x in a))
                    norm_b = math.sqrt(sum(y*y for y in b))
                    return dot/(norm_a*norm_b) if norm_a and norm_b else 0.0
                # Compute similarities using the DENSE embedding (from HyDE or retrieval_query)
                sims = [cos_sim(dense_emb, emb) for emb in doc_embeddings] # Use dense_emb 
                # Blend Qdrant's native score with cosine similarity
                qdrant_scores = [hit.get('score', 0.0) for hit in search_results]
                min_s, max_s = min(qdrant_scores), max(qdrant_scores)
                if max_s > min_s:
                    norm_scores = [(s - min_s)/(max_s - min_s) for s in qdrant_scores]
                else:
                    norm_scores = [1.0] * len(qdrant_scores)
                alpha = getattr(settings, 'RERANK_WEIGHT', 0.5)
                raw_scores = [alpha * norm_scores[i] + (1 - alpha) * sims[i] for i in range(len(sims))]
                
                # --- ADD BOOST for filename match on specific queries ---
                if 'mas' in message.lower(): # Check if query is about MAS
                    boost_amount = 0.1 # Define boost amount
                    boosted_indices = []
                    for i, hit in enumerate(search_results):
                        filename = hit.get('payload', {}).get('metadata', {}).get('original_filename', '').lower()
                        if 'mas' in filename:
                            raw_scores[i] += boost_amount
                            boosted_indices.append(i)
                    if boosted_indices:
                        logger.debug(f"RAG: Applied rerank score boost (+{boost_amount}) for MAS filename match on indices: {boosted_indices}")
                # --- END BOOST ---
                
                # Apply optional threshold filtering
                min_score = getattr(settings, 'RERANK_MIN_SCORE', None)
                if min_score is not None:
                    # filter out low-scoring hits
                    scored = [(idx, sc) for idx, sc in enumerate(raw_scores) if sc >= min_score]
                    if scored:
                        order = [idx for idx, _ in sorted(scored, key=lambda x: x[1], reverse=True)]
                    else:
                        # fallback to sorting all if none meet threshold
                        order = sorted(range(len(raw_scores)), key=lambda i: raw_scores[i], reverse=True)
                else:
                    order = sorted(range(len(raw_scores)), key=lambda i: raw_scores[i], reverse=True)
                # Optional MMR diversification for diversity
                if getattr(settings, 'ENABLE_MMR', False):
                    mmr_lambda = getattr(settings, 'MMR_LAMBDA', 0.5)
                    mmr_top_k = getattr(settings, 'MMR_TOP_K', len(order))
                    selected = []
                    candidates = order.copy()
                    # first pick highest relevance
                    if sims: # Check if sims is not empty
                        first = max(candidates, key=lambda idx: sims[idx])
                        selected.append(first)
                        candidates.remove(first)
                    while len(selected) < mmr_top_k and candidates:
                        mmr_scores = []
                        for cand in candidates:
                            max_sim = max(cos_sim(doc_embeddings[cand], doc_embeddings[sel]) for sel in selected)
                            score_mmr = mmr_lambda * sims[cand] - (1 - mmr_lambda) * max_sim
                            mmr_scores.append((cand, score_mmr))
                        next_cand = max(mmr_scores, key=lambda x: x[1])[0]
                        selected.append(next_cand)
                        candidates.remove(next_cand)
                    order = selected
                    logger.debug(f"Applied MMR diversification: final order {order}")
                search_results = [search_results[i] for i in order]
                logger.debug(f"Locally reranked Qdrant hits with blending and threshold, new order: {order}")

                # --- START: MAS-Specific Context Filtering --- 
                # MOVED EARLIER - This block is now before currency filtering
                # --- END: MAS-Specific Context Filtering ---

            except Exception as e:
                logger.warning(f"Local rerank or MAS filtering failed, proceeding with original Qdrant order: {e}", exc_info=True)

        # 4. Format context and augment prompt
        context_str = ""
        if search_results:
            context_str += "Relevant Context From Knowledge Base:\n---\n"
            for i, result in enumerate(search_results):
                payload_text = result.get('payload', {}).get('content', '') 
                context_str += f"Context {i+1} (Score: {result.get('score'):.4f}):\n{payload_text}\n---\n"
            context_str += "End of Context\n\n"
        else:
            # Log if no results were found (shouldn't happen based on INFO log, but good practice)
            logger.warning(f"RAG: search_qdrant_knowledge returned 0 results for collection '{bm_collection}'.")
            context_str = "No relevant context found in the knowledge base.\n\n"
        
        # --- ADDED LOG: Show the final constructed context --- 
        logger.debug(f"RAG: Final context string being sent to LLM:\n---\n{context_str}\n---")
        # --- END ADDED LOG ---

        # --- REVISED SYSTEM PROMPT V15 (Pleasant Table Formatting) ---
        system_prompt = f"""You are Jarvis, an AI assistant that uses provided RAG context and conversation history only.
Always answer strictly from the provided context; do not fabricate or infer any details not present in the context. The context often comes from specific documents like SOWs (Statement of Work) between parties (e.g., GIC and a Vendor).

**PRIORITY: If the user's query mentions 'MAS', prioritize information found in context chunks associated with 'MAS' documents.**

**CRITICAL INSTRUCTION - RATE CARD FORMATTING AND ACCURACY:** If the context below contains rate card tables (e.g., Exhibit C or Annex B from an SOW), you MUST extract the data with **absolute precision** and present it clearly. **Failure to follow these steps accurately is unacceptable.**
1.  **Identify Table:** Locate the relevant rate table (e.g., `B1: Monthly Rates`, `B4: Conversion Fees`) mentioned or implied by the user's query within the context's Annex B or Exhibit C.
2.  **Match Role EXACTLY:** Find the row that **precisely matches** the role name requested by the user (e.g., "ICT Infrastructure Engineer"). **DO NOT** use data from a different role's row. If the exact role is not listed, state that clearly and **DO NOT GUESS**.
3.  **Extract Verbatim:** Extract the numerical values for the matched role **exactly as they appear** in the context. **DO NOT** modify, calculate, estimate, or infer any numbers.
4.  **Present Clearly:** Format the extracted data using a **Markdown Table**.
5.  **Simplify Complex Tables:** For tables with sub-levels (e.g., Associate, Consultant, Senior), restructure the output table for clarity. Create separate columns for each level (e.g., | Role | Year 1 Assoc. | Year 1 Consult. | ... |). Avoid cramming multiple values into one cell.
6.  **Add Introduction:** Add a brief introductory sentence identifying the source (e.g., "Here are the conversion fees for [Role Name] from Annex B4:").
7.  **Strict Context Adherence:** **ONLY** use information present in the provided context. **DO NOT HALLUCINATE** or provide data not explicitly found in the relevant table row for the requested role.

**General Instructions (Apply *after* checking for rate cards):**
- If **no relevant Exhibit C/Annex B rate table applies**, and the user's question includes "list", "what are", or asks for multiple items, present a bullet list (markdown or plain hyphens).
- If **no relevant table applies**, and the user's question requests structured data for code, output valid JSON.
- If **no relevant table applies**, answer direct questions or single-item info requests in friendly plain text.
- **ONLY IF** the information is TRULY absent from the entire context **AFTER THOROUGHLY CHECKING ALL TABLES** (especially Exhibit C/Annex B within the SOW context), respond that you don't have sufficient context or ask ONE clarifying question.

--- START RAG CONTEXT ---
{context_str}
--- END RAG CONTEXT ---

Answer:
""" # End of revised RAG system prompt V15
        # --- END REVISED SYSTEM PROMPT V15 ---
        
        # --- START HISTORY HANDLING ---
        messages = []
        messages.append({"role": "system", "content": system_prompt})

        # --- MODIFICATION: Temporarily skip history for rate card queries to test interference ---
        if 'rate card' not in message.lower():
            # Add chat history (last 3 messages), ensuring alternating user/assistant roles
            if chat_history:
                # Take the last 3 entries (or fewer if history is shorter)
                history_to_use = chat_history[-3:]
                logger.debug(f"RAG: Adding {len(history_to_use)} messages from history to prompt.")
                # Basic validation of history items
                validated_history = [
                    item for item in history_to_use
                    if isinstance(item, dict) and 'role' in item and 'content' in item and item['role'] in ["user", "assistant"]
                ]
                # Log skipped items
                if len(validated_history) < len(history_to_use):
                    logger.warning(f"RAG: Skipped {len(history_to_use) - len(validated_history)} invalid history entries.")
                messages.extend(validated_history)
        else:
            logger.debug("RAG: Skipping chat history for rate card query to avoid interference.")
        # --- END MODIFICATION ---

        # Add the *current* user message AFTER the history (or system prompt if history skipped)
        messages.append({"role": "user", "content": message})
        # --- END HISTORY HANDLING ---

        # 5. Call OpenAI using the USER-specific client
        # Choose the model: user-specified or default
        logger.debug(f"Calling OpenAI model '{chat_model}' with user key...")
        logger.debug(f"RAG: Final messages structure sent to OpenAI: {messages}")
        response = await user_client.chat.completions.create(
            model=chat_model,
            messages=messages,
            temperature=0.1,
        )
        response_content = response.choices[0].message.content
        logger.debug(f"Received response from OpenAI using user key for {user.email}.")
        return response_content if response_content else "Sorry, I couldn't generate a response based on the context."
    
    except HTTPException as he:
        # Re-raise HTTP exceptions (like the 400 for missing key)
        raise he
    except Exception as e:
        logger.error(f"Error during RAG generation for user {user.email} using their key: {str(e)}", exc_info=True)
        # Log the specific collection searched during the error
        collection_name_on_error = f"{user.email.replace('@', '_').replace('.', '_')}_knowledge_base"
        # Return a generic error, hide specific details unless needed for debugging
        # Consider raising a 500 error instead of returning a string for better handling
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                            detail=f"Sorry, an error occurred while searching the '{collection_name_on_error}' knowledge base.")

# Keep the old simple chat function for now, or remove if replaced by RAG
# async def generate_openai_chat_response(message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
#    ... (previous implementation) ...
