from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel
import logging

# Import the RAG function
from app.services.llm import generate_openai_rag_response, get_rate_card_response_advanced
# Import authentication dependency and User model
from app.dependencies.auth import get_current_active_user_or_token_owner
from app.models.user import User
from app.db.session import get_db

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict[str, str]]] = None
    model_id: Optional[str] = None  # Model to use for this chat session

class ChatResponse(BaseModel):
    reply: str

@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    chat_message: ChatRequest,
    current_user: User = Depends(get_current_active_user_or_token_owner), # Use combined dependency
    db: Session = Depends(get_db) # Inject DB session
):
    """Chat endpoint for processing user messages and generating responses."""
    logger.info(f"Received chat request from user: {current_user.email}")
    
    # --- Logic to Decide between Rate Card RAG and Standard RAG ---
    is_rate_card_query = "rate card" in chat_message.message.lower()
    logger.info(f"Query type check: is_rate_card_query = {is_rate_card_query}")
    
    try:
        if is_rate_card_query:
            # Use the advanced rate card RAG pipeline
            logger.info("Routing to Advanced Rate Card RAG pipeline...")
            response_content = await get_rate_card_response_advanced(
                message=chat_message.message,
                user=current_user,
                db=db,
                model_id=chat_message.model_id # Pass model_id here too
            )
        else:
            # Use the standard RAG pipeline
            logger.info("Routing to Standard RAG pipeline...")
            response_content = await generate_openai_rag_response(
                message=chat_message.message,
                chat_history=chat_message.chat_history or [],
                user=current_user,
                db=db,
                model_id=chat_message.model_id, # Pass model_id if provided
                ms_token=current_user.ms_access_token # Pass the validated MS token
            )
            
        logger.info(f"Successfully generated response for user: {current_user.email}")
        return ChatResponse(reply=response_content)

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions (like 401, 400 from RAG)
        raise http_exc
    except Exception as e:
        logger.error(f"Error processing chat request for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your request.") 