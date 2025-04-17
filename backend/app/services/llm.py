import json
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import logging # Import logging
import httpx  # For HuggingFace reranker API
from httpx import HTTPStatusError

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.models.user import User # Assuming User model is here
# Import RAG components
from app.services.embedder import create_embedding, search_qdrant_knowledge
from app.crud import api_key_crud # Import API key CRUD
from fastapi import HTTPException, status # Import HTTPException

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
) -> str:
    """
    Generates a chat response using RAG and the USER'S OpenAI API key.
    Fails if the user has not provided their OpenAI API key.
    """
    try:
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
        import json
        retrieval_query = message
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
                model=settings.OPENAI_MODEL_NAME,
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
        # --- END: Query refinement ---
        logger.debug(f"Creating embedding for retrieval_query: '{retrieval_query[:50]}...' using user key")
        query_embedding = await create_embedding(retrieval_query, client=user_client) # Pass the user client
        logger.debug("Embedding created using user key.")

        # 3. Determine user-specific collection name and search
        sanitized_email = user.email.replace('@', '_').replace('.', '_')
        collection_to_search = f"{sanitized_email}_knowledge_base"
        logger.info(f"RAG: Targeting Qdrant collection: '{collection_to_search}' for user {user.email}")

        # Log a snippet of the query embedding
        embedding_snippet = str(query_embedding[:5]) + "..." if query_embedding else "None"
        logger.debug(f"RAG: Using query embedding (first 5 elements): {embedding_snippet}")

        search_results = await search_qdrant_knowledge(
            query_embedding=query_embedding,
            limit=10,
            collection_name=collection_to_search
        )
        # Log the raw search result length AND the results themselves for inspection
        logger.debug(f"RAG: Qdrant search returned {len(search_results)} hits from '{collection_to_search}'")
        logger.debug(f"RAG: Raw search results: {search_results}")

        # --- Start: LLM-based chunk classification to handle arbitrary layouts ---
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
                    "\nRespond with exactly the JSON object (e.g. {\\"1\\":\\"yes\\",\\"2\\":\\"no\\"})."
                )}
            ]
            class_resp = await user_client.chat.completions.create(
                model=settings.OPENAI_MODEL_NAME,
                messages=class_messages,
                temperature=0.0
            )
            # Debug: log raw classification response
            logger.debug(f"Classification response content: {class_resp.choices[0].message.content}")
            import json
            decisions = json.loads(class_resp.choices[0].message.content)
            # Filter only chunks marked 'yes'
            classified = [hit for idx, hit in enumerate(search_results, start=1)
                          if decisions.get(str(idx), "no").lower() == "yes"]
            if classified:
                search_results = classified
            logger.debug(f"RAG: Post-classification filtered hits: {len(search_results)}")
        except Exception as e:
            logger.warning(f"Chunk classification failed, using original hits: {e}", exc_info=True)
        # --- End: LLM-based classification ---

        # --- Start: Enhanced filtering to drop wrong table chunks for monthly vs conversion queries ---
        query_lower = message.lower()
        # If the user requests monthly rates or rate card, only keep chunks that mention monthly rate (or B1)
        if 'monthly rate' in query_lower or 'rate card' in query_lower:
            monthly_terms = ['monthly rate', 'monthly rates by individual', 'b1:']
            search_results = [
                hit for hit in search_results
                if any(term in hit.get('payload', {}).get('content', '').lower() for term in monthly_terms)
            ]
        # If the user requests conversion fees, only keep chunks that mention conversion fee (or B4)
        elif 'conversion fee' in query_lower:
            conversion_terms = ['conversion fee', 'conversion fees by individual', 'b4:']
            search_results = [
                hit for hit in search_results
                if any(term in hit.get('payload', {}).get('content', '').lower() for term in conversion_terms)
            ]
        # --- End: Enhanced filtering ---

        # Local reranking using OpenAI embeddings and cosine similarity
        if settings.ENABLE_RERANK:
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
                # Compute similarities
                sims = [cos_sim(query_embedding, emb) for emb in doc_embeddings]
                # Blend Qdrant's native score with cosine similarity
                qdrant_scores = [hit.get('score', 0.0) for hit in search_results]
                min_s, max_s = min(qdrant_scores), max(qdrant_scores)
                if max_s > min_s:
                    norm_scores = [(s - min_s)/(max_s - min_s) for s in qdrant_scores]
                else:
                    norm_scores = [1.0] * len(qdrant_scores)
                alpha = getattr(settings, 'RERANK_WEIGHT', 0.5)
                final_scores = [alpha * norm_scores[i] + (1 - alpha) * sims[i] for i in range(len(sims))]
                order = sorted(range(len(final_scores)), key=lambda i: final_scores[i], reverse=True)
                search_results = [search_results[i] for i in order]
                logger.debug(f"Locally reranked Qdrant hits new order: {order}")
            except Exception as e:
                logger.warning(f"Local rerank failed, proceeding with original Qdrant order: {e}", exc_info=True)

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
            logger.warning(f"RAG: search_qdrant_knowledge returned 0 results for collection '{collection_to_search}'.")
            context_str = "No relevant context found in the knowledge base.\n\n"
        
        # --- ADDED LOG: Show the final constructed context --- 
        logger.debug(f"RAG: Final context string being sent to LLM:\n---\n{context_str}\n---")
        # --- END ADDED LOG ---

        # --- REVISED SYSTEM PROMPT V9 (Modified Fallback Instruction) ---
        system_prompt = f"""You are Jarvis, an AI assistant that uses provided RAG context and conversation history only.
Always answer strictly from the provided context; do not fabricate or infer any details not present in the context.
If the context lacks enough information, respond that you don't have sufficient context or ask a clarifying question.

**Output Modes (use exactly one):**
- Markdown list
- JSON object
- Code block (triple‑backticks)
- Plain text

**Instructions (in order):**
1. If the user's question includes "list," "what are," etc., use a Markdown list.
2. If the user's question requests structured data for code, output valid JSON.
3. For other direct questions, answer in plain text paragraphs.
4. If you cannot answer from context, ask exactly one clarifying question.

--- START RAG CONTEXT ---
{context_str}
--- END RAG CONTEXT ---

Answer:
""" # End of revised RAG system prompt
        # --- END REVISED SYSTEM PROMPT V9 ---
        
        # --- START HISTORY HANDLING ---
        messages = []
        messages.append({"role": "system", "content": system_prompt})

        # Add chat history (last 5 messages), ensuring alternating user/assistant roles
        if chat_history:
            # Take the last 5 entries (or fewer if history is shorter)
            history_to_use = chat_history[-5:]
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

        # Add the *current* user message AFTER the history
        messages.append({"role": "user", "content": message})
        # --- END HISTORY HANDLING ---

        # 5. Call OpenAI using the USER-specific client
        logger.debug(f"Calling OpenAI model '{settings.OPENAI_MODEL_NAME}' with user key...")
        # Log the final messages structure being sent (optional but good for debugging history)
        logger.debug(f"RAG: Final messages structure sent to OpenAI: {messages}") 
        response = await user_client.chat.completions.create(
            model=settings.OPENAI_MODEL_NAME, 
            messages=messages, # Send the constructed messages list
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

# +++ Reranker Function +++
async def rerank_documents(query: str, docs: List[str]) -> List[int]:
    """
    Call HuggingFace BAAI/bge-reranker-v2-m3 to rerank documents.
    Returns list of indices sorted by descending relevance.
    """
    # Check feature flag and token
    if not settings.ENABLE_RERANK or not settings.HUGGINGFACE_API_TOKEN:
        logger.debug("Reranking disabled or no HuggingFace token, skipping rerank.")
        return list(range(len(docs)))
    url = "https://api-inference.huggingface.co/models/BAAI/bge-reranker-v2-m3?pipeline_tag=sentence-similarity"
    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_TOKEN}"}
    # BGE reranker expects a list of {query, document} entries
    payload = {"inputs": [
        {"query": query, "document": doc}
        for doc in docs
    ]}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            try:
                resp.raise_for_status()
            except HTTPStatusError as he:
                # Log full error response body for debugging
                logger.error(f"HuggingFace reranker HTTP {he.response.status_code} error: {he.response.text}", exc_info=True)
                raise
            result = resp.json()
            # HF reranker may return a list of scores or a dict with "scores"
            if isinstance(result, list):
                scores = result
            elif isinstance(result, dict) and "scores" in result:
                scores = result["scores"]
            else:
                raise ValueError("Unexpected reranker response format")
            # Sort indices by score descending
            return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    except Exception as e:
        logger.warning(f"Failed to rerank documents using HuggingFace: {e}", exc_info=True)
        return list(range(len(docs)))
# +++ End Reranker Function +++
