import json
import re  # For rate-card dollar filtering
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import logging # Import logging

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.models.user import User # Assuming User model is here
# Import RAG components - Updated for Milvus
from app.services.embedder import create_embedding, search_milvus_knowledge, create_retrieval_embedding
# Removed: search_qdrant_knowledge, search_qdrant_knowledge_sparse
from app.crud import api_key_crud # Import API key CRUD
from fastapi import HTTPException, status # Import HTTPException
# Qdrant specific imports (no longer needed for search in llm.py)
# from qdrant_client import models
# from qdrant_client.http.models import PayloadField, Filter, IsEmptyCondition
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
        user_client = AsyncOpenAI(
            api_key=user_openai_key, 
            timeout=30.0 # Set timeout to 30 seconds
        )

        # 2. Create embedding for the user message/HyDE doc
        # ... (Query refinement, expansion, HyDE logic remains the same) ...
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
        
        hyde_embedding = await create_retrieval_embedding(hyde_document)
        logger.debug("RAG: Created HyDE embedding.")

        # 2.5 Build Filter (Moved filter construction here)
        search_filter_parts = []
        # --- START: Rate card filtering --- 
        if 'rate card' in message.lower():
            # Extract dollar amount if present
            match = re.search(r'\$?(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?', message)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = int(amount_str)
                    # Add a filter condition for rate_card_amount if the field exists in payload
                    # NOTE: Adjust "payload.rate_card_amount" if the field name is different
                    search_filter_parts.append(f"metadata_json['rate_card_amount'] >= {amount}")
                    logger.debug(f"RAG: Added rate card filter: amount >= {amount}")
                except ValueError:
                    logger.warning(f"Could not parse amount from rate card query: {match.group(1)}")
            else:
                 logger.debug("RAG: 'rate card' detected but no dollar amount found for filtering.")
        # --- END: Rate card filtering ---
        
        # Example: Filter by role if extracted during refinement
        if refined and refined.get('role'):
            # Assuming role is stored in metadata_json['role']
            search_filter_parts.append(f'metadata_json["role"] == "{refined["role"]}"')
            logger.debug(f"RAG: Added filter for role: {refined['role']}")
            
        # Combine filters with ' and '
        search_filter = " and ".join(search_filter_parts) if search_filter_parts else None
        logger.debug(f"RAG: Constructed search filter: {search_filter}")


        # 3. Search Milvus for relevant context (dense search using HyDE embedding)
        k_dense = int(getattr(settings, 'RAG_DENSE_RESULTS', 5))
        logger.debug(f"RAG: Performing dense search with HyDE embedding for query: {message[:50]}... (k={k_dense})")
        dense_search_results = await search_milvus_knowledge(
            user_email=user.email,
            query_vector=hyde_embedding,
            query_text=hyde_document, # Pass HyDE doc for potential metadata logging/debugging
            k=k_dense, # Number of results for dense search
            filter_criteria=search_filter # Apply the constructed filter (now a string)
        )
        logger.debug(f"RAG: Dense search returned {len(dense_search_results)} results.")

        # 4. Perform sparse search (REMOVED) 
        # sparse_search_results = [] # Set sparse results to empty list (no longer needed)

        # 5. Combine and Rank Results using Reciprocal Rank Fusion (RRF)
        # --- MODIFIED RRF TO HANDLE ONLY DENSE RESULTS --- 
        logger.debug("RAG: Combining results (using only dense search results).")
        combined_results = {}
        rrf_k = 60  # Constant factor for RRF scoring, as described in papers

        # Process dense results
        for rank, hit in enumerate(dense_search_results):
            doc_id = hit["id"]
            # Milvus returns distance; lower is better. 
            # We use rank directly for RRF scoring (higher is better)
            score = 1.0 / (rank + 1 + rrf_k) # Add 1 because rank is 0-indexed
            if doc_id not in combined_results:
                combined_results[doc_id] = {"score": 0, "metadata": hit["metadata"], "id": doc_id}
            combined_results[doc_id]["score"] += score
            logger.debug(f"RAG: Dense Result ID: {doc_id}, Rank: {rank}, Score Contribution: {score}")
        
        # --- REMOVED Sparse result processing --- 

        # Sort combined results by RRF score in descending order
        ranked_results = sorted(combined_results.values(), key=lambda x: x["score"], reverse=True)
        logger.debug(f"RAG: Combined {len(ranked_results)} unique results after RRF.")

        # 6. Format context and build prompt
        context = "\n\n---\n\n".join([f"Document ID: {res['id']}\nContent: {json.dumps(res['metadata'])}" for res in ranked_results[:5]]) # Limit context window
        logger.debug(f"RAG: Formatted context (top {len(ranked_results[:5])} results):\n{context[:500]}...") # Log snippet of context

        # --- Existing history formatting logic --- 
        formatted_history = []
        for msg in chat_history:
            role = "user" if msg["role"] == "user" else "assistant"
            formatted_history.append({"role": role, "content": msg["content"]})
        # --- End history formatting ---

        system_prompt = f"""You are Jarvis, an AI assistant. 
        You are chatting with {user.display_name or user.email}. 
        Use the following retrieved context to answer the user's question.
        If the context doesn't contain the answer, say you don't have enough information from the knowledge base.
        Do not make up information not present in the context.
        Be concise and helpful.

        Context:
        {context}
        """
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        messages.extend(formatted_history) # Add formatted history
        messages.append({"role": "user", "content": message})
        
        logger.debug(f"RAG: Sending final prompt to {chat_model}...")
        
        # 7. Call OpenAI API with context and user message (using user's key)
        response = await user_client.chat.completions.create(
            model=chat_model,
            messages=messages,
            temperature=0.1 # Low temperature for factual RAG response
        )
        
        final_response = response.choices[0].message.content
        logger.debug(f"RAG: Received final response from {chat_model}.")
        return final_response

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly (like the API key missing error)
        raise http_exc
    except Exception as e:
        logger.error(f"Error generating RAG response for user {user.email}: {e}", exc_info=True)
        # Generic error for other unexpected issues
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An error occurred while generating the response: {str(e)}"
        )

# --- Helper function for cosine similarity ---
import numpy as np

def cos_sim(a, b):
    # Ensure embeddings are valid lists/tuples of numbers
    if not isinstance(a, (list, tuple, np.ndarray)) or not isinstance(b, (list, tuple, np.ndarray)):
        logger.warning(f"Invalid input types for cosine similarity: {type(a)}, {type(b)}")
        return 0.0 # Or raise an error?
        
    # Check if elements are numeric (simple check)
    if not all(isinstance(x, (int, float)) for x in a) or not all(isinstance(x, (int, float)) for x in b):
        logger.warning("Non-numeric elements found in embeddings for cosine similarity.")
        return 0.0
        
    # Convert to numpy arrays
    a = np.array(a)
    b = np.array(b)
    
    # Check for zero vectors or dimension mismatch
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0 or a.shape != b.shape:
        logger.warning("Invalid vectors for cosine similarity (zero vector or shape mismatch).")
        return 0.0
        
    # Calculate cosine similarity
    similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return similarity
# --- End Helper --- 

# --- START: ADVANCED RAG FOR RATE CARDS --- 
async def get_rate_card_response_advanced(
    message: str,
    user: User,
    db: Session
) -> str:
    """Advanced RAG pipeline specifically for rate card queries."""
    
    logger.info(f"Initiating ADVANCED rate card query for user {user.email}: '{message}'")
    
    try:
        # 1. User API Key & Client Setup (same as standard RAG)
        user_openai_key = api_key_crud.get_decrypted_api_key(db, user.email, "openai")
        if not user_openai_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OpenAI API key required.")
        user_client = AsyncOpenAI(api_key=user_openai_key, timeout=30.0)
        chat_model = settings.OPENAI_MODEL_NAME
        
        # 2. Query Analysis & Feature Extraction (Tailored for Rate Cards)
        logger.debug("RateCardRAG: Analyzing query for key features...")
        analysis_prompt = (
            f"Analyze the following rate card query: '{message}'. "
            "Extract key features like role, experience level (e.g., junior, mid, senior, principal), specific skills mentioned, "
            "location/region (if any), and requested dollar amount (if any). "
            "Return a JSON object with keys: 'role', 'experience', 'skills' (list), 'location', 'amount' (integer). "
            "If a feature is not mentioned, use null or an empty list."
        )
        analysis_response = await user_client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": "You are a query analyzer specializing in rate card requests."},
                {"role": "user", "content": analysis_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        query_features = json.loads(analysis_response.choices[0].message.content)
        logger.debug(f"RateCardRAG: Extracted query features: {query_features}")
        
        # 3. Construct Multi-Vector Retrieval Queries
        retrieval_queries = []
        # Base query from features
        base_query_parts = [query_features.get(k) for k in ['role', 'experience', 'location'] if query_features.get(k)]
        if query_features.get('skills'):
            base_query_parts.extend(query_features['skills'])
        base_query = " ".join(base_query_parts) if base_query_parts else message # Fallback to original message
        retrieval_queries.append(base_query)
        logger.debug(f"RateCardRAG: Base retrieval query: {base_query}")
        
        # Additional queries (e.g., focusing only on role and experience)
        if query_features.get('role') and query_features.get('experience'):
            role_exp_query = f"{query_features['role']} {query_features['experience']}"
            retrieval_queries.append(role_exp_query)
            logger.debug(f"RateCardRAG: Role/Experience query: {role_exp_query}")
        # Consider adding queries focusing only on skills if present
        if query_features.get('skills'):
            skills_query = " ".join(query_features['skills'])
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
                hyde_msgs = [
                    {"role": "system", "content": "Generate a concise, factual hypothetical rate card document answering the query."}, 
                    {"role": "user", "content": q}
                ]
                hyde_resp = await user_client.chat.completions.create(model=chat_model, messages=hyde_msgs, temperature=0.0)
                gen_doc = hyde_resp.choices[0].message.content.strip()
                if gen_doc: hyde_doc = gen_doc
            except Exception: pass # Ignore HyDE failure for individual queries
            hyde_docs[q] = hyde_doc
            
            # Create embedding using the HyDE document (or original query if HyDE failed)
            embedding = await create_retrieval_embedding(hyde_doc)
            query_vectors.append(embedding)
            logger.debug(f"RateCardRAG: Generated embedding for query: '{q}' (using HyDE: {hyde_doc[:50]}...)")

        # 5. Perform Multi-Vector Search in Milvus
        k_per_query = int(getattr(settings, 'RATE_CARD_RESULTS_PER_QUERY', 3)) # Retrieve fewer per query initially
        all_search_results = [] 
        
        # Build filter based on extracted amount
        search_filter = None
        requested_amount = query_features.get('amount')
        if requested_amount is not None and isinstance(requested_amount, int):
            # Assuming rate is stored in metadata_json.rate_card_amount
            search_filter = f"metadata_json['rate_card_amount'] >= {requested_amount}"
            logger.debug(f"RateCardRAG: Applying search filter: {search_filter}")
        else:
            logger.debug("RateCardRAG: No amount filter applied.")

        for i, vector in enumerate(query_vectors):
            logger.debug(f"RateCardRAG: Searching with vector {i+1} for query: '{retrieval_queries[i]}'")
            results = await search_milvus_knowledge(
                user_email=user.email,
                query_vector=vector,
                query_text=hyde_docs[retrieval_queries[i]], # Pass associated HyDE doc
                k=k_per_query,
                filter_criteria=search_filter # Apply amount filter if applicable
            )
            all_search_results.extend(results) # Combine results from all queries
            logger.debug(f"RateCardRAG: Found {len(results)} results for vector {i+1}.")
            
        logger.info(f"RateCardRAG: Total raw results from multi-vector search: {len(all_search_results)}")

        # 6. Deduplicate and Re-rank Results
        unique_results = {res['id']: res for res in all_search_results} # Simple deduplication by ID
        ranked_results = list(unique_results.values())
        logger.info(f"RateCardRAG: Unique results after deduplication: {len(ranked_results)}")
        
        # Re-ranking based on relevance to the *original* user message
        if ranked_results:
            logger.debug("RateCardRAG: Re-ranking based on original query similarity...")
            original_query_embedding = await create_retrieval_embedding(message)
            
            # Calculate similarity between original query and each result's content/embedding
            for result in ranked_results:
                result_embedding = result.get('vector') # Assuming search_milvus_knowledge can return vectors
                result_text = json.dumps(result.get('metadata', {})) # Use metadata text
                
                if result_embedding:
                    # Option 1: Use pre-computed embedding from result if available
                    similarity = cos_sim(original_query_embedding, result_embedding)
                else:
                    # Option 2: Re-embed result text (less efficient but fallback)
                    logger.warning(f"RateCardRAG: Re-embedding result ID {result['id']} for re-ranking as vector not found.")
                    result_embedding_rerank = await create_retrieval_embedding(result_text)
                    similarity = cos_sim(original_query_embedding, result_embedding_rerank)
                
                # Assign similarity score for sorting (can combine with original distance if needed)
                result['rerank_score'] = similarity 
                logger.debug(f"RateCardRAG: Result ID {result['id']} rerank similarity: {similarity:.4f}")
            
            # Sort by the new rerank_score (higher is better)
            ranked_results.sort(key=lambda x: x.get('rerank_score', 0.0), reverse=True)
            logger.debug("RateCardRAG: Completed re-ranking.")
        
        # 7. Context Selection & Formatting (Select top N re-ranked results)
        final_context_limit = int(getattr(settings, 'RATE_CARD_FINAL_CONTEXT_LIMIT', 5))
        context = "\n\n---\n\n".join([f"Document ID: {res['id']}\nContent: {json.dumps(res['metadata'])}" for res in ranked_results[:final_context_limit]])
        logger.debug(f"RateCardRAG: Formatted final context (top {len(ranked_results[:final_context_limit])}):\n{context[:500]}...")

        # 8. Generate Final Response using LLM
        system_prompt = (
            "You are Jarvis, an AI assistant specializing in providing rate card information. "
            f"You are chatting with {user.display_name or user.email}. "
            "Use the provided context containing relevant rate card entries to answer the user's query accurately. "
            "Directly quote rates and associated details (like role, experience, skills, location) from the context. "
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
        response = await user_client.chat.completions.create(
            model=chat_model,
            messages=messages,
            temperature=0.0 # Very low temp for factual rate card response
        )
        final_response = response.choices[0].message.content
        logger.info("RateCardRAG: Generated final response.")
        return final_response

    except HTTPException as http_exc:
        raise http_exc # Re-raise specific errors
    except Exception as e:
        logger.error(f"Error during advanced rate card RAG for user {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your rate card request."
        )
# --- END: ADVANCED RAG FOR RATE CARDS --- 
