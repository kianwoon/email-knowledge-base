import logging
import uuid
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.models.agent import Agent

logger = logging.getLogger(__name__)

def get_agent(db: Session, agent_id: uuid.UUID) -> Optional[Agent]:
    """
    Get an agent by ID.
    
    Args:
        db: Database session
        agent_id: Agent UUID
        
    Returns:
        Agent object if found, None otherwise
    """
    return db.query(Agent).filter(Agent.id == agent_id).first()

def get_agents_by_user(db: Session, user_id: uuid.UUID) -> List[Agent]:
    """
    Get all agents for a user.
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        List of Agent objects
    """
    return db.query(Agent).filter(Agent.user_id == user_id).all()

def create_agent(db: Session, user_id: uuid.UUID, agent_data: Dict[str, Any]) -> Agent:
    """
    Create a new agent.
    
    Args:
        db: Database session
        user_id: User UUID
        agent_data: Dict with agent data
        
    Returns:
        Created Agent object
    """
    db_agent = Agent(
        user_id=user_id,
        name=agent_data.get('name'),
        type=agent_data.get('type'),
        system_message=agent_data.get('systemMessage'),
        is_public=agent_data.get('isPublic', False)
    )
    
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    
    logger.info(f"Created agent {db_agent.id} for user {user_id}")
    return db_agent

def update_agent(db: Session, agent_id: uuid.UUID, agent_data: Dict[str, Any]) -> Optional[Agent]:
    """
    Update an agent.
    
    Args:
        db: Database session
        agent_id: Agent UUID
        agent_data: Dict with agent data to update
        
    Returns:
        Updated Agent object if found, None otherwise
    """
    db_agent = get_agent(db, agent_id)
    
    if db_agent is None:
        return None
    
    # Update agent fields
    if 'name' in agent_data:
        db_agent.name = agent_data['name']
    if 'type' in agent_data:
        db_agent.type = agent_data['type']
    if 'systemMessage' in agent_data:
        db_agent.system_message = agent_data['systemMessage']
    if 'isPublic' in agent_data:
        db_agent.is_public = agent_data['isPublic']
    
    db.commit()
    db.refresh(db_agent)
    
    logger.info(f"Updated agent {agent_id}")
    return db_agent

def delete_agent(db: Session, agent_id: uuid.UUID) -> bool:
    """
    Delete an agent.
    
    Args:
        db: Database session
        agent_id: Agent UUID
        
    Returns:
        True if agent was deleted, False otherwise
    """
    db_agent = get_agent(db, agent_id)
    
    if db_agent is None:
        return False
    
    db.delete(db_agent)
    db.commit()
    
    logger.info(f"Deleted agent {agent_id}")
    return True 