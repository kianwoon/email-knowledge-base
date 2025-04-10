import json
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
import logging # Import logging

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.models.user import User # Assuming User model is here
# Import RAG components
from app.services.embedder import create_embedding, search_qdrant_knowledge
from app.crud import api_key_crud # Import API key CRUD
from fastapi import HTTPException, status # Import HTTPException

# Set up logger for this module
logger = logging.getLogger(__name__)

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
    user: User, # User object
    db: Session, # Database session
    chat_history: Optional[List[Dict[str, str]]] = None
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
        user_client = AsyncOpenAI(api_key=user_openai_key)

        # 2. Create embedding for the user message (can still use system key client? Let's use user key)
        # Potentially switch embedding to use user_client too if needed, or keep using global client
        # For now, let's use the user_client for embedding as well for consistency
        logger.debug(f"Creating embedding for message: '{message[:50]}...' using user key")
        query_embedding = await create_embedding(message, client=user_client) # Pass the user client
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
        logger.info(f"RAG: Qdrant search returned {len(search_results)} hits from '{collection_to_search}'")
        logger.debug(f"RAG: Raw search results: {search_results}")

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

        # --- REVISED SYSTEM PROMPT V5 (Allowing History for Follow-ups) ---
        system_prompt = f"""You are a helpful AI assistant. Your primary goal is to answer the user's question based on the **provided RAG context** and the **ongoing conversation history**. Do not use prior knowledge outside of these.

**Instructions (Follow in order):**

1.  **Counting Query:** If the user asks 'how many' of something:
    *   Carefully review all provided context snippets for evidence related to the user's query terms.
    *   Attempt to count the distinct instances mentioned based *only* on the RAG context.
    *   **Response:** State the count clearly if possible. If not, state that and summarize the key details of all relevant evidence found in the RAG context. **Stop.**

2.  **Follow-up Query:** If the user's current question is a follow-up referring to your *immediately preceding* response (e.g., 'give me the details', 'tell me more about that', 'what was the first point?'):
    *   Refer primarily to your **own previous response** in the chat history.
    *   Provide the requested details or elaboration based on what you stated previously. Use the RAG context only if needed to supplement the details from your previous response. **Stop.**

3.  **Other Query - Direct Answer:** If the question is not about counting or a direct follow-up, try to find and provide a direct answer from the RAG context. If successful, provide the answer and stop.

4.  **Fallback - Summarization:** If you cannot provide a count, answer a follow-up, or find a direct answer based *only* on the RAG context and history, state that you couldn't find the specific information, and then summarize the key information from the RAG context that seems most relevant to the user's original question.

--- START RAG CONTEXT ---
{context_str}
--- END RAG CONTEXT ---

User Question: {message}

Answer:"""
        # --- END REVISED SYSTEM PROMPT V5 ---
        
        # --- START HISTORY HANDLING ---
        messages = []
        messages.append({"role": "system", "content": system_prompt})

        # Add chat history (last 5 messages), ensuring alternating user/assistant roles
        if chat_history:
            # Take the last 5 entries (or fewer if history is shorter)
            history_to_use = chat_history[-5:]
            logger.debug(f"RAG: Adding {len(history_to_use)} messages from history to prompt.")
            for entry in history_to_use:
                role = entry.get("role")
                content = entry.get("content")
                if role and content:
                    # Basic validation: Ensure role is 'user' or 'assistant'
                    if role in ["user", "assistant"]:
                         messages.append({"role": role, "content": content})
                    else:
                        logger.warning(f"RAG: Skipping history entry with invalid role: {role}")
                else:
                     logger.warning(f"RAG: Skipping history entry with missing role or content: {entry}")

        # Add the *current* user message (it's already included IN the system prompt's {message})
        # We don't add it separately here as it's part of the final instruction in the system prompt.
        # --- END HISTORY HANDLING ---

        # 5. Call OpenAI using the USER-specific client
        logger.debug(f"Calling OpenAI model '{settings.LLM_MODEL}' with user key...")
        # Log the final messages structure being sent (optional but good for debugging history)
        logger.debug(f"RAG: Final messages structure sent to OpenAI: {messages}") 
        response = await user_client.chat.completions.create(
            model=settings.LLM_MODEL, 
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
