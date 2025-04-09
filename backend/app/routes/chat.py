from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.services.llm import generate_openai_chat_response
# Assuming you have authentication set up via dependencies
# from app.dependencies import get_current_user # Adjust if your dependency is different
# from app.models.user import User # Adjust user model path if needed

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    reply: str

@router.post("/chat/openai", response_model=ChatResponse)
async def handle_openai_chat(
    request: ChatRequest,
    # current_user: User = Depends(get_current_user) # Uncomment and adjust if auth is needed
):
    """
    Endpoint to handle chat requests using the simple OpenAI-only backend.
    """
    try:
        response_text = await generate_openai_chat_response(
            message=request.message,
            chat_history=request.chat_history
        )
        return ChatResponse(reply=response_text)
    except Exception as e:
        # Log the exception details if needed
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error generating chat response.") 