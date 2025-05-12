import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.user import User
from app.models.conversation import AutogenConversation, AutogenMessage
from app.crud import conversation_crud
from app.db.session import get_db
from app.dependencies.auth import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", status_code=status.HTTP_200_OK)
async def get_conversations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all conversations for the current user.
    """
    try:
        conversations = conversation_crud.get_conversations_by_user(db, current_user.id)
        return [conversation.to_dict() for conversation in conversations]
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversations: {str(e)}"
        )

@router.get("/{conversation_id}", status_code=status.HTTP_200_OK)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific conversation by ID.
    """
    conversation = conversation_crud.get_conversation(db, conversation_id)
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Ensure the conversation belongs to the current user
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation"
        )
    
    # Get messages for this conversation
    messages = conversation_crud.get_messages_by_conversation(db, conversation_id)
    
    # Return detailed conversation with messages
    result = conversation.to_dict()
    result["messages"] = [message.to_dict() for message in messages]
    
    return result

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new conversation.
    """
    try:
        db_conversation = conversation_crud.create_conversation(db, current_user.id, conversation)
        return db_conversation.to_dict()
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create conversation: {str(e)}"
        )

@router.put("/{conversation_id}", status_code=status.HTTP_200_OK)
async def update_conversation(
    conversation_id: UUID,
    updates: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing conversation.
    """
    # Check if conversation exists and belongs to the current user
    conversation = conversation_crud.get_conversation(db, conversation_id)
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this conversation"
        )
    
    try:
        updated_conversation = conversation_crud.update_conversation(db, conversation_id, updates)
        return updated_conversation.to_dict()
    except Exception as e:
        logger.error(f"Error updating conversation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update conversation: {str(e)}"
        )

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a conversation.
    """
    # Check if conversation exists and belongs to the current user
    conversation = conversation_crud.get_conversation(db, conversation_id)
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this conversation"
        )
    
    if conversation_crud.delete_conversation(db, conversation_id):
        return None
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )

@router.post("/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def add_message(
    conversation_id: UUID,
    message: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Add a message to a conversation.
    """
    # Check if conversation exists and belongs to the current user
    conversation = conversation_crud.get_conversation(db, conversation_id)
    
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add messages to this conversation"
        )
    
    try:
        db_message = conversation_crud.create_message(db, conversation_id, message)
        return db_message.to_dict()
    except Exception as e:
        logger.error(f"Error adding message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add message: {str(e)}"
        ) 