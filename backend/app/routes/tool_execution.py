from fastapi import APIRouter, Depends, HTTPException, Body, Path, Request, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.services.tool_executor import execute_tool, AuthenticationError
from app.services.auth_service import AuthService
from pydantic import BaseModel, Field

# Import manifest functions
from app.routes.chat import load_tool_manifest

# MCP tool CRUD for looking up tools
from app.crud import mcp_tool_crud

logger = logging.getLogger(__name__)

# Define the request model for tool execution
class ToolExecutionRequest(BaseModel):
    tool_name: Optional[str] = None
    name: Optional[str] = None  # Alternative field name that might be sent by frontend
    arguments: Dict[str, Any]
    
    def get_tool_name(self) -> str:
        """Returns the tool name, prioritizing tool_name over name."""
        if self.tool_name:
            return self.tool_name
        elif self.name:
            return self.name
        else:
            raise ValueError("Either 'tool_name' or 'name' must be provided")

router = APIRouter(
    prefix="/tools",
    tags=["Tools"],
    responses={404: {"description": "Not found"}}
)

@router.post("/execute")
async def execute_tool_endpoint(
    execution_request: ToolExecutionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Execute a tool based on its name and arguments.
    This endpoint is called by the frontend after the LLM decides to use a tool.
    """
    try:
        # Get the tool name from the request, supporting both 'tool_name' and 'name' fields
        try:
            tool_name = execution_request.get_tool_name()
        except ValueError as e:
            logger.error(f"Invalid tool execution request from user {current_user.email}: {str(e)}")
            return {"error": str(e)}
            
        logger.info(f"Tool execution request: {tool_name} for user {current_user.email}")
        
        # Look up tool metadata from manifest or DB
        tool_metadata = None
        
        # Search in tool manifest first (includes static and user-defined tools)
        tools_config = load_tool_manifest(current_user.email, db)
        tools = tools_config.get("tools", [])
        
        # Find the tool by name
        for tool in tools:
            if tool.get("name") == tool_name:
                tool_metadata = tool
                break
        
        if not tool_metadata:
            logger.warning(f"Tool {tool_name} not found in manifest for user {current_user.email}")
            return {"error": f"Tool '{tool_name}' not found"}
        
        # Log the tool metadata and arguments for debugging
        logger.debug(f"Tool metadata for {tool_name}: {tool_metadata}")
        logger.debug(f"Tool arguments: {execution_request.arguments}")
        
        # Add the tool name to the metadata to ensure it's passed through correctly
        if "name" not in tool_metadata:
            tool_metadata["name"] = tool_name
        
        # For custom tools, ensure they're properly identified
        if tool_metadata.get("entrypoint") and "is_custom" not in tool_metadata:
            tool_metadata["is_custom"] = True
            logger.info(f"Marked tool {tool_name} as custom based on entrypoint: {tool_metadata.get('entrypoint')}")
        
        # Execute the tool
        result = await execute_tool(
            tool_name=tool_name,
            arguments=execution_request.arguments,
            tool_metadata=tool_metadata,
            user_email=current_user.email
        )
        
        # Check if there was an error during execution
        if "error" in result:
            error_message = result.get("error", "Unknown error")
            logger.warning(f"Tool execution error for {tool_name}: {error_message}")
            
            # Provide more detailed and user-friendly error messages based on the response
            if "404" in str(error_message):
                return {
                    "error": "The tool endpoint could not be found. Please check the tool configuration.",
                    "details": error_message,
                    "status_code": 404
                }
            elif "422" in str(error_message):
                return {
                    "error": "The tool request was invalid. Required parameters may be missing or formatted incorrectly.",
                    "details": error_message,
                    "status_code": 422
                }
            elif "401" in str(error_message) or "403" in str(error_message):
                return {
                    "error": "Authentication or authorization failed when accessing the tool endpoint.",
                    "details": error_message,
                    "status_code": 401
                }
            else:
                return {
                    "error": "Tool execution failed.",
                    "details": error_message
                }
            
        # Log successful result summary (without potentially large data)
        if isinstance(result, dict):
            result_keys = list(result.keys())
            logger.info(f"Tool {tool_name} executed successfully. Result contains keys: {result_keys}")
        else:
            logger.info(f"Tool {tool_name} executed successfully with non-dict result type: {type(result)}")
            
        return result
    
    except AuthenticationError as auth_error:
        # Get a fallback tool name if it wasn't set earlier
        try:
            tool_name_for_log = tool_name
        except NameError:
            tool_name_for_log = execution_request.get_tool_name() if hasattr(execution_request, 'get_tool_name') else "unknown"
            
        logger.error(f"Authentication error executing tool {tool_name_for_log}: {str(auth_error)}")
        return {
            "error": "Authentication required",
            "details": str(auth_error),
            "auth_required": True
        }
    except Exception as e:
        # Get a fallback tool name if it wasn't set earlier
        tool_name_for_log = "unknown"
        try:
            tool_name_for_log = tool_name
        except NameError:
            try:
                tool_name_for_log = execution_request.get_tool_name() if hasattr(execution_request, 'get_tool_name') else "unknown"
            except:
                pass
                
        logger.error(f"Error executing tool {tool_name_for_log}: {str(e)}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

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
            "reauthorize_url": "/api/v1/auth/login" if not is_authenticated else None
        }
    except Exception as e:
        logger.error(f"Error checking auth status for {service}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def check_microsoft_auth(db: Session, user_email: str) -> bool:
    """Check if user is authenticated with Microsoft."""
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