from fastapi import APIRouter, Depends, HTTPException, Body, Path
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.services.tool_executor import execute_tool
from app.crud import mcp_tool_crud

router = APIRouter(
    prefix="/tools",
    tags=["Tools"],
    responses={404: {"description": "Not found"}}
)

logger = logging.getLogger(__name__)

@router.post("/execute", response_model=Any)
async def execute_tool_endpoint(
    tool_request: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Execute a tool by name with provided arguments."""
    tool_name = tool_request.get("name")
    arguments = tool_request.get("arguments", {})
    
    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool name is required")
    
    logger.info(f"User {current_user.email} requesting execution of tool: {tool_name}")
    
    # First, check if it's a user-defined tool
    user_tool = mcp_tool_crud.get_mcp_tool_by_name(db, tool_name, current_user.email)
    
    if user_tool:
        # If it's a user-defined tool, ensure it's enabled
        if not user_tool.enabled:
            raise HTTPException(status_code=403, detail=f"Tool {tool_name} is disabled")
        
        # Create tool metadata for the executor
        tool_metadata = {
            "name": user_tool.name,
            "description": user_tool.description,
            "parameters": user_tool.parameters,
            "entrypoint": user_tool.entrypoint,
            "version": user_tool.version,
            "is_custom": True
        }
        
        # Execute the user-defined tool
        result = await execute_tool(
            tool_name=tool_name,
            arguments=arguments,
            tool_metadata=tool_metadata,
            user_email=current_user.email
        )
        return result
    
    # If it's not a user-defined tool, check if it's a built-in tool
    # This would typically check against a list of allowed built-in tools
    # For now, we just pass it to the executor and let it handle it
    result = await execute_tool(
        tool_name=tool_name,
        arguments=arguments,
        user_email=current_user.email
    )
    
    return result

@router.get("/list", response_model=List[Dict[str, Any]])
async def list_available_tools(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all available tools for the user."""
    # Get user-defined tools
    user_tools = mcp_tool_crud.get_mcp_tools(db, current_user.email)
    
    # Convert to dictionary format
    tools = [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "entrypoint": tool.entrypoint,
            "version": tool.version,
            "enabled": tool.enabled,
            "is_custom": True
        }
        for tool in user_tools
    ]
    
    # TODO: Add built-in tools to the list (read from a config or registry)
    
    return tools 