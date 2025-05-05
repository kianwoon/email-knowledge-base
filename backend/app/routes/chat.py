from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel
import logging
import asyncio
import httpx
import json

# Import the RAG function
from app.services.llm import generate_openai_rag_response, get_rate_card_response_advanced
# Import authentication dependency and User model
from app.dependencies.auth import get_current_active_user_or_token_owner
from app.models.user import User
from app.db.session import get_db

# --- ADDED IMPORTS ---
from app.crud import crud_jarvis_token
from app.services.encryption_service import decrypt_token
from app.models.jarvis_token import JarvisExternalToken
from app.config import settings
# --- END ADDED IMPORTS ---

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict[str, str]]] = None
    model_id: Optional[str] = None  # Model to use for this chat session

class ChatResponse(BaseModel):
    reply: str

# --- ADDED HELPER FUNCTION for External Search --- 
async def search_external_knowledge(token_record: JarvisExternalToken, query: str, request: Request) -> List[Dict]:
    """Performs a search using a single external token."""
    try:
        decrypted_token = decrypt_token(token_record.encrypted_token_value)
    except Exception as e:
        logger.error(f"Failed to decrypt external token ID {token_record.id} for user {token_record.user_id}: {e}")
        # TODO: Consider marking token as invalid in DB after several failures
        return [] # Return empty list on decryption failure

    search_endpoint = request.url_for('search_shared_knowledge') # Use FastAPI's reverse routing
    # Fallback if reverse routing fails (e.g., testing)
    if not search_endpoint:
         search_endpoint = f"/api/v1/shared-knowledge/search" # Adjust if your base path differs
         logger.warning(f"Could not reverse route 'search_shared_knowledge', using hardcoded path: {search_endpoint}")
    
    # Construct absolute URL for the internal request
    base_url = str(request.base_url) # e.g., http://localhost:8000/
    target_url = f"{base_url.rstrip('/')}{search_endpoint}"
    
    headers = {
        "Authorization": f"Bearer {decrypted_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"query": query, "limit": 5} # Limit external results for performance
    
    logger.debug(f"External search: User={token_record.user_id}, TokenID={token_record.id}, Nickname='{token_record.token_nickname}', URL={target_url}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client: # Use httpx for async requests
            response = await client.post(target_url, headers=headers, json=payload)
        
        response.raise_for_status() # Raise exception for 4xx/5xx errors
        results = response.json()
        logger.info(f"External search success: User={token_record.user_id}, TokenID={token_record.id}, ResultsCount={len(results)}")
        # Add source info to results
        for result in results:
             result['_source_nickname'] = token_record.token_nickname
        return results
    except httpx.HTTPStatusError as e:
        logger.error(f"External search failed (HTTP {e.response.status_code}): TokenID={token_record.id}, Nickname='{token_record.token_nickname}', URL={target_url}, Response: {e.response.text}")
        # TODO: Handle specific errors (401/403 might mean token is invalid)
        if e.response.status_code in [401, 403]:
            # Mark token as invalid? Needs DB access - complex here, maybe handle later.
            pass
        return []
    except Exception as e:
        logger.error(f"External search failed (General Error): TokenID={token_record.id}, Nickname='{token_record.token_nickname}', URL={target_url}, Error: {e}", exc_info=True)
        return []
# --- END HELPER FUNCTION ---

@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    chat_message: ChatRequest,
    request: Request, # Add Request dependency to get base URL
    current_user: User = Depends(get_current_active_user_or_token_owner),
    db: Session = Depends(get_db)
):
    """Chat endpoint for processing user messages and generating responses."""
    logger.info(f"Received chat request from user: {current_user.email}")

    # --- ADDED: Fetch and Search External Knowledge --- 
    external_search_tasks = []
    all_external_results = []
    try:
        valid_external_tokens = crud_jarvis_token.get_valid_tokens_for_user(db=db, user_id=current_user.id)
        logger.info(f"Found {len(valid_external_tokens)} valid external tokens for user {current_user.id}")
        
        if valid_external_tokens:
            for token_record in valid_external_tokens:
                # Create an async task for each token search
                task = search_external_knowledge(token_record, chat_message.message, request)
                external_search_tasks.append(task)
            
            # Run searches concurrently
            if external_search_tasks:
                 logger.info(f"Gathering results from {len(external_search_tasks)} external searches...")
                 results_list = await asyncio.gather(*external_search_tasks)
                 # Flatten the list of lists
                 all_external_results = [item for sublist in results_list for item in sublist]
                 logger.info(f"Total external results gathered: {len(all_external_results)}")
                 # Log results for now (in future, combine/re-rank)
                 logger.debug(f"External results details: {json.dumps(all_external_results, indent=2)}")

    except Exception as e:
        logger.error(f"Error during external token processing for user {current_user.id}: {e}", exc_info=True)
        # Decide if this should halt the process or just log and continue
    # --- END External Knowledge Fetch --- 

    # --- Existing Logic --- 
    is_rate_card_query = "rate card" in chat_message.message.lower()
    logger.info(f"Query type check: is_rate_card_query = {is_rate_card_query}")
    
    try:
        # Combine external context (if any) with user message for RAG
        # --- MODIFICATION POINT (Example Option B - simple text append) ---
        combined_context_text = "\n\n---\\nAdditional Context from Shared Knowledge:\n"
        if all_external_results:
            for result in all_external_results[:3]: # Limit context added
                source = result.get('_source_nickname', 'Unknown Source')
                content = result.get('metadata', {}).get('raw_text', '[No text content]') 
                combined_context_text += f"\nSource: {source}\nContent: {content}\n---\n"
            logger.info(f"Prepared combined context text from {len(all_external_results)} external results.")
        else:
            combined_context_text = "" # No external results
            logger.info("No external results to add to context.")

        # Append context to original message ONLY IF external results found
        message_for_rag = chat_message.message
        if combined_context_text:
             message_for_rag += combined_context_text
             logger.debug(f"Using combined message for RAG: {message_for_rag[:500]}...") # Log truncated combined message
        else:
             logger.debug("Using original message for RAG.")
        # --- END MODIFICATION POINT --- 

        if is_rate_card_query:
            logger.info("Routing to Advanced Rate Card RAG pipeline...")
            response_content = await get_rate_card_response_advanced(
                message=message_for_rag, # Use potentially modified message
                user=current_user,
                db=db,
                model_id=chat_message.model_id
            )
        else:
            logger.info("Routing to Standard RAG pipeline...")
            # Use the original function
            response_content = await generate_openai_rag_response(
                message=message_for_rag, # Use potentially modified message
                chat_history=chat_message.chat_history or [],
                user=current_user,
                db=db,
                model_id=chat_message.model_id,
                ms_token=current_user.ms_access_token
            )
            
        logger.info(f"Successfully generated response for user: {current_user.email}")
        
        # Add safeguard check to handle None response
        if response_content is None:
            logger.error(f"Received None response from RAG function for user {current_user.email}")
            response_content = "I'm sorry, but I couldn't generate a response at this time. There was an issue with the language model service. Please try again later."
            
        return ChatResponse(reply=response_content)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error processing chat request for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your request.") 