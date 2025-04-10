from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel

# Import the RAG function
from app.services.llm import generate_openai_rag_response
# Import authentication dependency and User model
from app.dependencies.auth import get_current_active_user 
from app.models.user import User 

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    reply: str

@router.post("/chat/openai", response_model=ChatResponse)
async def handle_openai_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user) # Add dependency
):
    """
    Endpoint to handle chat requests using RAG with OpenAI, 
    targeting the user's specific collection.
    """
    if not current_user:
         # This check might be redundant if get_current_active_user raises exception
         raise HTTPException(status_code=401, detail="Could not authenticate user")
         
    try:
        # Call the RAG function, passing the authenticated user
        response_text = await generate_openai_rag_response(
            message=request.message,
            user=current_user, # Pass the user object
            chat_history=request.chat_history 
        )
        return ChatResponse(reply=response_text)
    except Exception as e:
        # Log the exception details if needed
        print(f"Error in chat endpoint for user {current_user.email}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error generating chat response.") 