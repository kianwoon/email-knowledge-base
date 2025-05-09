from fastapi import APIRouter, Depends, HTTPException, Body, Path
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.services.tool_executor import execute_tool, AuthenticationError
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
    """Execute a tool by name and arguments, handling authentication errors appropriately."""
    tool_name = tool_request.get("name")
    arguments = tool_request.get("arguments", {})
    
    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool name is required")
        
    logger.info(f"Tool execution request: {tool_name} for user {current_user.email}")
    
    # Check if tool exists in MCP tools
    tool_metadata = None
    try:
        user_tools = mcp_tool_crud.get_mcp_tools(db, current_user.email)
        tool_metadata = next((tool for tool in user_tools if tool.name == tool_name), None)
        
        if tool_metadata:
            # Convert Pydantic/SQLAlchemy model to dictionary for easier handling
            tool_metadata = {
                "name": tool_metadata.name,
                "description": tool_metadata.description,
                "entrypoint": tool_metadata.entrypoint,
                "is_custom": True,
                "parameters": tool_metadata.parameters,
                "version": tool_metadata.version
            }
    except Exception as e:
        logger.error(f"Error retrieving tool metadata: {e}")
        # Continue without metadata - might be a built-in tool
    
    # Execute the tool
    try:
        result = await execute_tool(
            tool_name=tool_name,
            arguments=arguments,
            tool_metadata=tool_metadata,
            user_email=current_user.email
        )
        
        # Check for authentication errors in result
        if isinstance(result, dict) and result.get("error") == "Authentication error":
            # Return a standardized response for auth errors
            return {
                "status": "error",
                "error_type": "authentication",
                "message": result.get("message", "Authentication failed"),
                "requires_auth": True,
                "auth_service": result.get("auth_service", "unknown"),
                "callback_endpoint": f"/api/v1/auth/reauthorize/{result.get('auth_service', 'unknown')}"
            }
            
        # Return the result
        return result
        
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth-status/{service}", response_model=Dict[str, Any])
async def check_auth_status(
    service: str = Path(..., description="Authentication service to check"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Check if the user is authenticated with a particular service."""
    logger.info(f"Auth status check for service {service} for user {current_user.email}")
    
    # Map of service names to check functions
    auth_status_checks = {
        "microsoft": check_microsoft_auth,
        "jira": check_jira_auth,
        # Add more services as needed
    }
    
    check_func = auth_status_checks.get(service)
    if not check_func:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service}")
        
    # Execute the appropriate check function
    try:
        is_authenticated = await check_func(db, current_user.email)
        return {
            "service": service,
            "authenticated": is_authenticated,
            "user": current_user.email,
            "reauthorize_url": f"/api/v1/auth/reauthorize/{service}" if not is_authenticated else None
        }
    except Exception as e:
        logger.error(f"Error checking auth status for {service}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def check_microsoft_auth(db: Session, user_email: str) -> bool:
    """Check if user is authenticated with Microsoft."""
    from app.services.auth_service import AuthService
    
    try:
        # Try to get a fresh token
        token_result = await AuthService.refresh_ms_token(db, user_email)
        return token_result is not None and "access_token" in token_result
    except Exception as e:
        logger.error(f"Error checking Microsoft auth: {e}")
        return False

async def check_jira_auth(db: Session, user_email: str) -> bool:
    """Check if user is authenticated with Jira."""
    # Placeholder for Jira authentication check
    # Implement based on your Jira auth system
    return False  # Not implemented

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