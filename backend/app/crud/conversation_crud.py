import logging
import uuid
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.models.conversation import AutogenConversation, AutogenMessage

logger = logging.getLogger(__name__)

# Conversation CRUD operations

def get_conversation(db: Session, conversation_id: uuid.UUID) -> Optional[AutogenConversation]:
    """
    Get a conversation by ID.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        
    Returns:
        AutogenConversation object if found, None otherwise
    """
    return db.query(AutogenConversation).filter(AutogenConversation.id == conversation_id).first()

def get_conversations_by_user(db: Session, user_id: uuid.UUID) -> List[AutogenConversation]:
    """
    Get all conversations for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        List of AutogenConversation objects
    """
    return db.query(AutogenConversation).filter(
        AutogenConversation.user_id == user_id
    ).order_by(AutogenConversation.last_accessed_at.desc()).all()

def create_conversation(db: Session, user_id: uuid.UUID, data: Dict[str, Any]) -> AutogenConversation:
    """
    Create a new conversation.
    
    Args:
        db: Database session
        user_id: User UUID
        data: Dict with conversation data
        
    Returns:
        Created AutogenConversation object
    """
    db_conversation = AutogenConversation(
        user_id=user_id,
        title=data.get('title', 'New Conversation'),
        max_rounds=data.get('maxRounds', 10),
        agent_configs=data.get('agentConfigs', {})
    )
    
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    
    logger.info(f"Created conversation {db_conversation.id} for user {user_id}")
    return db_conversation

def update_conversation(db: Session, conversation_id: uuid.UUID, data: Dict[str, Any]) -> Optional[AutogenConversation]:
    """
    Update a conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        data: Dict with conversation data to update
        
    Returns:
        Updated AutogenConversation object if found, None otherwise
    """
    db_conversation = get_conversation(db, conversation_id)
    
    if db_conversation is None:
        return None
    
    # Update conversation fields
    if 'title' in data:
        db_conversation.title = data['title']
    if 'maxRounds' in data:
        db_conversation.max_rounds = data['maxRounds']
    if 'agentConfigs' in data:
        db_conversation.agent_configs = data['agentConfigs']
    
    # Update the last accessed time
    db_conversation.last_accessed_at = None # Will use server default (current time)
    
    db.commit()
    db.refresh(db_conversation)
    
    logger.info(f"Updated conversation {conversation_id}")
    return db_conversation

def delete_conversation(db: Session, conversation_id: uuid.UUID) -> bool:
    """
    Delete a conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        
    Returns:
        True if conversation was deleted, False otherwise
    """
    db_conversation = get_conversation(db, conversation_id)
    
    if db_conversation is None:
        return False
    
    db.delete(db_conversation)
    db.commit()
    
    logger.info(f"Deleted conversation {conversation_id}")
    return True

# Message CRUD operations

def get_message(db: Session, message_id: uuid.UUID) -> Optional[AutogenMessage]:
    """
    Get a message by ID.
    
    Args:
        db: Database session
        message_id: Message UUID
        
    Returns:
        AutogenMessage object if found, None otherwise
    """
    return db.query(AutogenMessage).filter(AutogenMessage.id == message_id).first()

def get_messages_by_conversation(db: Session, conversation_id: uuid.UUID) -> List[AutogenMessage]:
    """
    Get all messages for a conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        
    Returns:
        List of AutogenMessage objects
    """
    return db.query(AutogenMessage).filter(
        AutogenMessage.conversation_id == conversation_id
    ).order_by(AutogenMessage.sequence_number).all()

def create_message(db: Session, conversation_id: uuid.UUID, data: Dict[str, Any]) -> AutogenMessage:
    """
    Create a new message.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        data: Dict with message data
        
    Returns:
        Created AutogenMessage object
    """
    # Get the next sequence number
    next_seq = db.query(AutogenMessage).filter(
        AutogenMessage.conversation_id == conversation_id
    ).count() + 1
    
    db_message = AutogenMessage(
        conversation_id=conversation_id,
        role=data.get('role', 'user'),
        agent_name=data.get('agentName'),
        content=data.get('content', ''),
        sequence_number=next_seq
    )
    
    db.add(db_message)
    
    # Update the conversation's last accessed time
    db_conversation = get_conversation(db, conversation_id)
    if db_conversation:
        db_conversation.last_accessed_at = None # Will use server default (current time)
    
    db.commit()
    db.refresh(db_message)
    
    logger.info(f"Created message {db_message.id} for conversation {conversation_id}")
    return db_message 