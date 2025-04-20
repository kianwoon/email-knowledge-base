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
from qdrant_client.http.models import PayloadField, Filter, IsEmptyCondition
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

        # --- Determine user-specific collection name ---
        sanitized_email = user.email.replace('@', '_').replace('.', '_')
        # Derive BM hybrid collection for dense, colbertv2.0, and bm25 embeddings
        bm_collection = f"{sanitized_email}_knowledge_base_bm"
        logger.info(f"RAG: Targeting Qdrant collection: '{bm_collection}' for user {user.email}")

        # --- START: Two-Phase Retrieval (PDFs then Emails) ---
        logger.info(f"RAG: Starting two-phase retrieval (Phase 1: PDFs, Phase 2: Emails).")

        doc_hits = [] # Initialize doc_hits here
        email_hits = []

        # Define the Document filter (Phase 1)
        # Filter for points where metadata.content_type field exists (is not empty)
        doc_filter = Filter(
            must_not=[
                IsEmptyCondition(
                    is_empty=PayloadField(key="metadata.content_type")
                )
            ]
        )
        doc_k = 20 
        logger.debug(f"RAG Phase 1: Searching Documents (metadata.content_type exists) with k={doc_k} and filter={doc_filter}")

        # Initialize result lists
        doc_dense_hits = []
        doc_bm25_hits = []

        # Phase 1a: Dense search for Documents
        try:
            doc_dense_hits = await search_qdrant_knowledge(
                query_embedding=dense_emb, 
                limit=doc_k,
                collection_name=bm_collection,
                qdrant_filter=doc_filter, 
                vector_name="dense"
            )
            logger.debug(f"RAG Phase 1 (Dense): Found {len(doc_dense_hits)} Document hits.")
        except Exception as e:
            logger.warning(f"RAG Phase 1 (Dense Document search) failed: {e}", exc_info=True)
            doc_dense_hits = []

        # Phase 1b: BM25 search for Documents
        try:
            doc_bm25_hits = await search_qdrant_knowledge_sparse(
                query_text=retrieval_query, 
                limit=doc_k, 
                collection_name=bm_collection,
                qdrant_filter=doc_filter, # Apply the same Document filter
                vector_name="bm25"
            )
            logger.debug(f"RAG Phase 1 (BM25): Found {len(doc_bm25_hits)} Document hits.")
        except Exception as e:
            logger.warning(f"RAG Phase 1 (BM25 Document search) failed: {e}", exc_info=True)
            doc_bm25_hits = []

        # Merge Dense and BM25 Document hits, deduplicating by ID
        doc_merged = {}
        for hit in itertools.chain(doc_dense_hits, doc_bm25_hits):
            hit_id = hit.get('id')
            payload = hit.get('payload') 
            if hit_id and payload:
                 if hit_id in doc_merged:
                     doc_merged[hit_id]['score'] = max(doc_merged[hit_id].get('score', 0.0), hit.get('score', 0.0))
                 else:
                     doc_merged[hit_id] = hit
        # doc_hits becomes the list of unique, highest-scoring Document hits from dense+BM25
        doc_hits = list(doc_merged.values())
        logger.debug(f"RAG Phase 1 (Merged Dense+BM25): Found {len(doc_hits)} unique Document hits.")

        # Phase 2: Search Emails
        email_hits = [] # Initialize here
        email_filter = models.Filter(
            must=[
                models.FieldCondition(key="metadata.source", match=models.MatchValue(value="email")) # Check metadata.source
            ]
        )
        email_k = 10
        logger.debug(f"RAG Phase 2: Searching Emails with k={email_k} and filter={email_filter}")
        try:
            # Perform only dense search for emails for now, unless BM25 is also desired
            email_hits = await search_qdrant_knowledge(
                query_embedding=dense_emb, 
                limit=email_k,
                collection_name=bm_collection,
                qdrant_filter=email_filter,
                vector_name="dense"
            )
            logger.debug(f"RAG Phase 2: Found {len(email_hits)} Email hits.")
        except Exception as e:
            logger.warning(f"RAG Phase 2 (Email search) failed: {e}", exc_info=True)
            email_hits = []

        # Merge and Deduplicate Results (Documents first, then Emails)
        merged_hits_dict = {}
        for hit in doc_hits + email_hits: # Add Docs first
            hit_id = hit.get('id')
            if hit_id and hit_id not in merged_hits_dict:
                 merged_hits_dict[hit_id] = hit 

        search_results = list(merged_hits_dict.values())
        search_results.sort(key=lambda x: x.get('score', 0.0), reverse=True)

        logger.info(f"RAG: Two-phase retrieval merged {len(search_results)} unique hits ({len(doc_hits)} Docs initially, {len(email_hits)} Emails initially). Passing to reranking/filtering.")
        logger.debug(f"RAG: Merged search results (pre-reranking): {search_results}")

        # --- END: Two-Phase Retrieval ---

        # Check if results are empty *after* the two phases
        if not search_results:
             logger.warning("RAG: Two-phase retrieval (PDF+Email) yielded no results. Proceeding without context.")
             # Consider if a fallback search for *all* types is needed here if results are empty. For now, just proceed.

        # --- Fallback logic for Query Expansion (Keep this, it's separate) ---
        # NOTE: This fallback might need reconsideration. It currently reruns a dense search
        # with the original query if the *expanded* query yielded zero results from the two-phase search.
        # This might be okay, but it bypasses the PDF/Email filtering on the fallback.
        if not search_results and getattr(settings, 'ENABLE_QUERY_EXPANSION', False) and retrieval_query != orig_retrieval_query:
            logger.warning("RAG: No results after query expansion with two-phase retrieval, retrying dense search with original query (NO PDF/EMAIL filter)")
            # Recreate embedding for original query
            orig_query_embedding = await create_retrieval_embedding(orig_retrieval_query, "dense") # Use dense
            logger.debug(f"RAG: Running Qdrant fallback search for original query: '{orig_retrieval_query[:50]}...' with limit {settings.RAG_SEARCH_LIMIT}")
            # Perform a simple dense search without PDF/Email filters for this fallback
            search_results = await search_qdrant_knowledge(
                query_embedding=orig_query_embedding,
                limit=settings.RAG_SEARCH_LIMIT, # Use standard limit for fallback
                collection_name=bm_collection,
                qdrant_filter=None, # No filter in this specific fallback
                vector_name="dense"
            )
            logger.debug(f"RAG: Qdrant fallback search (original query) returned {len(search_results)} hits.")
        # --- End Fallback logic for Query Expansion ---


        # --- Start: LLM-based chunk classification to handle arbitrary layouts ---
        # (This and subsequent steps like reranking, dollar filtering now operate on the 'search_results' from the two-phase retrieval)
        if 'rate card' not in message.lower() and 'rate for' not in message.lower():
            # Only classify chunks for non-rate-card queries
            try:
                # Prepare chunks for classification
                # Ensure payload and content exist before accessing
                chunk_texts = [
                    hit['payload']['content'] for hit in search_results
                    if hit.get('payload') and hit['payload'].get('content')
                ]
                if not chunk_texts:
                     logger.debug("RAG: No valid chunks found to send for classification.")
                else:
                    class_messages = [
                        {"role": "system", "content": (
                            "You are a classification assistant. Given a user question and a list of text chunks, "
                            "return ONLY a JSON object mapping chunk indices to \"yes\" or \"no\" indicating whether "
                            "each chunk is useful to answer the question. Do not include any additional text or markdown."
                        )},
                        {"role": "user", "content": (
                            f"User question: {message}\\nChunks:\\n" +
                            "\\n".join(f"Chunk {i+1}: {txt}" for i, txt in enumerate(chunk_texts)) +
                            "\\nRespond with only a JSON object mapping each chunk number to 'yes' or 'no'. No extra text."
                        )}
                    ]
                    class_resp = await user_client.chat.completions.create(
                        model=chat_model,
                        messages=class_messages,
                        temperature=0.0
                    )
                    # Debug: log raw classification response
                    logger.debug(f"Classification response content: {class_resp.choices[0].message.content}")
                    try:
                        decisions = json.loads(class_resp.choices[0].message.content)
                        # Filter only chunks marked 'yes'
                        # Align indices correctly with the potentially filtered chunk_texts
                        original_indices = [
                            idx for idx, hit in enumerate(search_results)
                            if hit.get('payload') and hit['payload'].get('content')
                        ]
                        classified_hits = []
                        for i, original_idx in enumerate(original_indices):
                             if decisions.get(str(i + 1), "no").lower() == "yes":
                                 classified_hits.append(search_results[original_idx])

                        if classified_hits: # Only overwrite if classification succeeded and found relevant chunks
                            search_results = classified_hits
                            logger.debug(f"RAG: Post-classification filtered hits: {len(search_results)}")
                        else:
                             logger.debug("RAG: Classification marked all chunks as 'no' or failed to find matches. Keeping original results.")
                    except json.JSONDecodeError as json_e:
                         logger.warning(f"Chunk classification response was not valid JSON: {json_e}", exc_info=True)
                    except Exception as class_e: # Catch other potential errors during classification processing
                        logger.warning(f"Error processing classification decisions: {class_e}", exc_info=True)

            except Exception as e:
                logger.warning(f"Chunk classification step failed entirely: {e}", exc_info=True)
        else:
            # Skip classification for rate-card queries to preserve table chunks
            logger.debug("RAG: Skipping chunk classification for rate-card/table style query")
        # --- End: LLM-based classification ---

        # Local reranking using OpenAI embeddings and cosine similarity
        if settings.ENABLE_RERANK and search_results:
            try:
                # Extract document texts, ensuring payload and content exist
                docs = [
                    hit["payload"]["content"] for hit in search_results
                    if hit.get("payload") and hit["payload"].get("content")
                ]
                # Skip reranking if no valid docs found
                if not docs:
                    logger.warning("RAG: No valid document content found for reranking. Skipping.")
                else:
                    # Generate embeddings for each doc using user's API key
                    doc_embeddings = [
                        await create_embedding(text, client=user_client)
                        for text in docs
                    ]
                    # Cosine similarity helper
                    import math
                    def cos_sim(a, b):
                        # Ensure embeddings are valid lists/tuples of numbers
                        if not (isinstance(a, (list, tuple)) and isinstance(b, (list, tuple))): return 0.0
                        if len(a) != len(b) or len(a) == 0: return 0.0
                        try:
                            dot = sum(x*y for x, y in zip(a, b))
                            norm_a = math.sqrt(sum(x*x for x in a))
                            norm_b = math.sqrt(sum(y*y for y in b))
                            # Avoid division by zero
                            return dot/(norm_a*norm_b) if norm_a and norm_b else 0.0
                        except TypeError: # Handle case where embeddings might contain non-numeric types
                             logger.warning("RAG: TypeError during cosine similarity calculation. Skipping similarity.")
                             return 0.0

                    # Compute similarities using the DENSE embedding (from HyDE or retrieval_query)
                    sims = [cos_sim(dense_emb, emb) for emb in doc_embeddings] 

                    # Blend Qdrant's native score with cosine similarity
                    qdrant_scores = [hit.get('score', 0.0) for hit in search_results if hit.get("payload") and hit["payload"].get("content")] # Align with filtered docs
                    # Normalize Qdrant scores (handle division by zero if all scores are same)
                    min_s, max_s = (min(qdrant_scores), max(qdrant_scores)) if qdrant_scores else (0.0, 0.0) # Simplified initialization
                    if max_s > min_s:
                        norm_scores = [(s - min_s)/(max_s - min_s) for s in qdrant_scores]
                    else:
                        norm_scores = [1.0] * len(qdrant_scores) # Assign 1 if all scores are equal or list empty

                    alpha = getattr(settings, 'RERANK_WEIGHT', 0.5)
                    # Ensure lists have the same length before blending
                    if len(norm_scores) == len(sims):
                         raw_scores = [alpha * norm_scores[i] + (1 - alpha) * sims[i] for i in range(len(sims))]
                    else:
                         logger.warning("RAG: Mismatch between number of scores and similarities. Skipping score blending.")
                         raw_scores = sims # Fallback to similarity scores only

                    # --- NOTE: PDF BOOST logic removed as prioritization happens earlier ---
                    # boosted_scores = raw_scores # Use raw blended scores directly now
                    # --- END PDF BOOST REMOVAL --- 

                    # Apply optional threshold filtering (using raw_scores)
                    min_score = getattr(settings, 'RERANK_MIN_SCORE', None)
                    if min_score is not None:
                        # filter out low-scoring hits based on raw score
                        scored_indices = [(idx, sc) for idx, sc in enumerate(raw_scores) if sc >= min_score]
                        if scored_indices:
                            # Sort remaining based on score
                            order = [idx for idx, _ in sorted(scored_indices, key=lambda x: x[1], reverse=True)]
                        else:
                            # fallback to sorting all raw scores if none meet threshold
                            logger.debug(f"RAG: No hits met rerank threshold {min_score}. Sorting all {len(raw_scores)} hits by score.")
                            order = sorted(range(len(raw_scores)), key=lambda i: raw_scores[i], reverse=True)
                    else:
                        # Sort based on raw scores if no threshold
                        order = sorted(range(len(raw_scores)), key=lambda i: raw_scores[i], reverse=True)

                    # Optional MMR diversification for diversity (uses raw_scores for relevance term)
                    if getattr(settings, 'ENABLE_MMR', False):
                        mmr_lambda = getattr(settings, 'MMR_LAMBDA', 0.5)
                        mmr_top_k = getattr(settings, 'MMR_TOP_K', len(order)) # Base K on potentially thresholded list
                        selected_indices = []
                        candidate_indices = order.copy() # Indices remaining after potential thresholding

                        # Ensure we have embeddings and scores for the candidates
                        valid_candidates = [idx for idx in candidate_indices if idx < len(doc_embeddings) and idx < len(raw_scores)]

                        if valid_candidates:
                            # Pick the highest scoring candidate first
                            first_idx = max(valid_candidates, key=lambda idx: raw_scores[idx])
                            selected_indices.append(first_idx)
                            valid_candidates.remove(first_idx)

                            while len(selected_indices) < mmr_top_k and valid_candidates:
                                mmr_scores = []
                                selected_embeddings = [doc_embeddings[sel_idx] for sel_idx in selected_indices]
                                for cand_idx in valid_candidates:
                                    cand_embedding = doc_embeddings[cand_idx]
                                    cand_score = raw_scores[cand_idx]
                                    # Ensure selected_embeddings is not empty before calculating max_sim
                                    if selected_embeddings:
                                         max_sim_with_selected = max(cos_sim(cand_embedding, sel_emb) for sel_emb in selected_embeddings)
                                    else:
                                         max_sim_with_selected = 0.0 # No similarity if nothing selected yet
                                    score_mmr = mmr_lambda * cand_score - (1 - mmr_lambda) * max_sim_with_selected
                                    mmr_scores.append((cand_idx, score_mmr))

                                if not mmr_scores: break # Exit if no more candidates can be scored

                                next_cand_idx = max(mmr_scores, key=lambda x: x[1])[0]
                                selected_indices.append(next_cand_idx)
                                valid_candidates.remove(next_cand_idx)

                            order = selected_indices # Final order determined by MMR
                            logger.debug(f"Applied MMR diversification: final order indices {order}")
                        else:
                             logger.warning("RAG: Skipping MMR due to no valid candidates (check embeddings/scores alignment).")

                    # Reorder search_results based on the final order (from reranking/MMR)
                    # First, get the subset of search_results corresponding to the `docs` used
                    valid_search_results = [
                        hit for hit in search_results
                        if hit.get("payload") and hit["payload"].get("content")
                    ]
                    # Apply the final order, making sure indices are valid
                    final_ordered_results = [valid_search_results[i] for i in order if i < len(valid_search_results)]
                    # Replace the original search_results with the reranked/filtered/diversified list
                    search_results = final_ordered_results
                    logger.debug(f"Locally reranked/diversified Qdrant hits, final count: {len(search_results)}") # Updated log

            except Exception as e:
                logger.warning(f"Local rerank or diversification failed, proceeding with original Qdrant order: {e}", exc_info=True)

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
