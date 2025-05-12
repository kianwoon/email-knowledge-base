import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.user import User
from app.models.agent import Agent
from app.crud import agent_crud
from app.db.session import get_db
from app.dependencies.auth import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", status_code=status.HTTP_200_OK)
async def get_agents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all agents for the current user.
    """
    try:
        agents = agent_crud.get_agents_by_user(db, current_user.id)
        return [agent.to_dict() for agent in agents]
    except Exception as e:
        logger.error(f"Error getting agents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agents: {str(e)}"
        )

@router.get("/{agent_id}", status_code=status.HTTP_200_OK)
async def get_agent(
    agent_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific agent by ID.
    """
    agent = agent_crud.get_agent(db, agent_id)
    
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Ensure the agent belongs to the current user
    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this agent"
        )
    
    return agent.to_dict()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new agent.
    """
    try:
        agent = agent_crud.create_agent(db, current_user.id, agent_data)
        return agent.to_dict()
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agent: {str(e)}"
        )

@router.put("/{agent_id}", status_code=status.HTTP_200_OK)
async def update_agent(
    agent_id: UUID,
    agent_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing agent.
    """
    # Check if agent exists and belongs to the current user
    agent = agent_crud.get_agent(db, agent_id)
    
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this agent"
        )
    
    try:
        updated_agent = agent_crud.update_agent(db, agent_id, agent_data)
        return updated_agent.to_dict()
    except Exception as e:
        logger.error(f"Error updating agent: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent: {str(e)}"
        )

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete an agent.
    """
    # Check if agent exists and belongs to the current user
    agent = agent_crud.get_agent(db, agent_id)
    
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this agent"
        )
    
    if agent_crud.delete_agent(db, agent_id):
        return None
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent"
        ) 