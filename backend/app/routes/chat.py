from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel

# Import the RAG function
from app.services.llm import generate_openai_rag_response
# Import authentication dependency and User model
from app.dependencies.auth import get_current_active_user 
from app.models.user import User 
from app.db.session import get_db

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict[str, str]]] = None
    model_id: Optional[str] = None  # Model to use for this chat session

class ChatResponse(BaseModel):
    reply: str

@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user), # Get authenticated user
    db: Session = Depends(get_db) # Inject DB session
):
    """Receives a chat message and returns a response using RAG."""
    try:
        # Call the RAG function, passing the user object and db session
        response_text = await generate_openai_rag_response(
            message=request.message,
            chat_history=request.chat_history,
            user=current_user,
            db=db,
            model_id=request.model_id
        )
        return ChatResponse(reply=response_text)
    except HTTPException as he:
        # Re-raise HTTP exceptions (like 400 for missing key)
        raise he
    except Exception as e:
        # Log the error
        # Consider more specific error handling
        raise HTTPException(status_code=500, detail=f"Error generating chat response: {str(e)}") 