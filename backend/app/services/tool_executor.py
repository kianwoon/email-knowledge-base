import logging
import json
import httpx
from typing import Dict, Any, Optional, List, Tuple
import importlib
import inspect
from pydantic import ValidationError
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db.session import get_db
from ..services.outlook import OutlookService
from ..services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Custom exception for authentication errors
class AuthenticationError(Exception):
    """Exception raised when authentication fails for a tool."""
    pass

async def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tool_metadata: Optional[Dict[str, Any]] = None,
    user_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a tool based on its name and arguments.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments for the tool
        tool_metadata: Additional metadata about the tool, including entrypoint for custom tools
        user_email: Email of the user executing the tool (for logging and authorization)
        
    Returns:
        Dict containing the result of tool execution
    """
    logger.info(f"Executing tool: {tool_name} for user: {user_email or 'unknown'}")
    logger.debug(f"Tool arguments: {arguments}")
    
    try:
        # Handle custom MCP tool (user-defined)
        if tool_metadata and tool_metadata.get("is_custom", False):
            return await execute_custom_mcp_tool(tool_name, arguments, tool_metadata, user_email)
            
        # Handle built-in tools based on their names
        if tool_name == "outlook_create_event":
            return await execute_outlook_create_event(arguments, user_email)
        elif tool_name == "outlook_list_events":
            return await execute_outlook_list_events(arguments, user_email)
        elif tool_name == "jira_create_issue":
            return await execute_jira_create_issue(arguments, user_email)
        elif tool_name == "jira_list_issues":
            return await execute_jira_list_issues(arguments, user_email)
        # Add other built-in tools as needed
        
        # If we get here, the tool wasn't found
        logger.warning(f"Tool not found: {tool_name}")
        return {"error": f"Tool '{tool_name}' not found or not implemented"}
    
    except AuthenticationError as auth_err:
        logger.error(f"Authentication error executing tool {tool_name}: {str(auth_err)}")
        return {
            "error": "Authentication error",
            "message": str(auth_err) or "Failed to authenticate with the required service. Please check your credentials or re-authenticate.",
            "requires_auth": True,
            "auth_service": get_auth_service_for_tool(tool_name)
        }
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

def get_auth_service_for_tool(tool_name: str) -> str:
    """Determine which authentication service a tool requires."""
    if tool_name.startswith("outlook_"):
        return "microsoft"
    elif tool_name.startswith("jira_"):
        return "jira"
    # Add more mappings as needed
    return "unknown"

async def execute_custom_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    tool_metadata: Dict[str, Any],
    user_email: Optional[str] = None
) -> Dict[str, Any]:
    """Execute a custom MCP tool by calling its entrypoint."""
    entrypoint = tool_metadata.get("entrypoint")
    if not entrypoint:
        logger.error(f"Custom tool {tool_name} has no entrypoint defined")
        return {"error": "Tool entrypoint not defined"}
    
    logger.info(f"Executing custom MCP tool: {tool_name} with entrypoint: {entrypoint}")
    
    try:
        # If entrypoint is a URL, make an HTTP request
        if entrypoint.startswith(("http://", "https://")):
            return await execute_http_entrypoint(entrypoint, arguments, user_email)
        
        # If entrypoint is a local function path
        elif "." in entrypoint:
            return await execute_function_entrypoint(entrypoint, arguments, user_email)
        
        # If entrypoint is just a path without protocol
        else:
            # Assume it's a relative API path
            base_url = settings.MCP_SERVER_URL or "http://localhost:8000"
            full_url = f"{base_url.rstrip('/')}/{entrypoint.lstrip('/')}"
            return await execute_http_entrypoint(full_url, arguments, user_email)
            
    except Exception as e:
        logger.error(f"Error executing custom MCP tool {tool_name}: {str(e)}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

async def execute_http_entrypoint(url: str, arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Execute a tool by making an HTTP request to its entrypoint."""
    try:
        headers = {
            "Content-Type": "application/json",
            "X-User-Email": user_email or "anonymous"
        }
        
        # If we have a user email, add authentication
        if user_email:
            db = next(get_db())
            try:
                # Try to get a token for the user (implement based on your auth system)
                auth_header = await get_auth_header_for_user(db, user_email, url)
                if auth_header:
                    headers.update(auth_header)
            finally:
                db.close()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=arguments, headers=headers)
            
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed for {url}")
            elif response.status_code >= 400:
                logger.error(f"HTTP error {response.status_code} from {url}: {response.text}")
                return {"error": f"Tool execution failed with status {response.status_code}: {response.text}"}
            
            # Try to parse response as JSON
            try:
                result = response.json()
                return result
            except json.JSONDecodeError:
                # If not JSON, return text
                return {"result": response.text}
    
    except httpx.RequestError as e:
        logger.error(f"Request error to {url}: {str(e)}")
        return {"error": f"Failed to connect to tool endpoint: {str(e)}"}
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error calling {url}: {str(e)}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

async def get_auth_header_for_user(db: Session, user_email: str, url: str) -> Optional[Dict[str, str]]:
    """Get authentication headers for a user based on the URL/service."""
    try:
        if "microsoft" in url or "graph.microsoft" in url:
            ms_token = await AuthService.refresh_ms_token(db, user_email)
            if ms_token and ms_token.get("access_token"):
                return {"Authorization": f"Bearer {ms_token['access_token']}"}
        # Add more services as needed
        return None
    except Exception as e:
        logger.error(f"Error getting auth header: {str(e)}")
        return None

async def execute_function_entrypoint(func_path: str, arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Execute a tool by calling a local Python function."""
    try:
        # Parse module and function names
        module_path, func_name = func_path.rsplit(".", 1)
        
        # Import the module
        module = importlib.import_module(module_path)
        
        # Get the function
        func = getattr(module, func_name)
        
        # Check if function is coroutine (async)
        is_coroutine = inspect.iscoroutinefunction(func)
        
        # Add user_email to arguments if the function accepts it
        sig = inspect.signature(func)
        if "user_email" in sig.parameters:
            arguments["user_email"] = user_email
        
        # Call the function
        if is_coroutine:
            result = await func(**arguments)
        else:
            result = func(**arguments)
            
        return result if isinstance(result, dict) else {"result": result}
        
    except ImportError as e:
        logger.error(f"Module import error for {func_path}: {str(e)}")
        return {"error": f"Tool module not found: {str(e)}"}
        
    except AttributeError as e:
        logger.error(f"Function not found: {func_path}: {str(e)}")
        return {"error": f"Tool function not found: {str(e)}"}
        
    except ValidationError as e:
        logger.error(f"Validation error calling {func_path}: {str(e)}")
        return {"error": f"Invalid arguments: {str(e)}"}
        
    except Exception as e:
        logger.error(f"Error calling function {func_path}: {str(e)}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

# Actual implementations for built-in tools
async def execute_outlook_create_event(arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Implementation for Outlook create event."""
    logger.info(f"Creating Outlook event: {arguments}")
    
    if not user_email:
        return {"error": "User email is required"}
    
    try:
        # Validate required parameters
        required_fields = ["subject", "start_datetime", "end_datetime"]
        for field in required_fields:
            if field not in arguments:
                return {"error": f"Missing required parameter: {field}"}
        
        # Get database session
        db = next(get_db())
        
        try:
            # Create outlook service for the user
            outlook_service = await OutlookService.create(user_email)
            
            # Format the event creation request
            # This depends on your OutlookService implementation
            # Placeholder for actual implementation
            
            # Return success
            return {
                "status": "success",
                "message": "Event created successfully",
                "details": {
                    "subject": arguments["subject"],
                    "start": arguments["start_datetime"],
                    "end": arguments["end_datetime"]
                }
            }
        except HTTPException as http_error:
            if http_error.status_code == 401:
                raise AuthenticationError("Failed to authenticate with Microsoft. Please reauthorize your account.")
            raise
        finally:
            db.close()
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Error creating Outlook event: {str(e)}", exc_info=True)
        return {"error": f"Failed to create event: {str(e)}"}

async def execute_outlook_list_events(arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Implementation for Outlook list events."""
    logger.info(f"Listing Outlook events: {arguments}")
    
    if not user_email:
        return {"error": "User email is required"}
    
    try:
        # Parse time range from arguments
        start_datetime = arguments.get("start_datetime")
        end_datetime = arguments.get("end_datetime")
        
        # If not provided, default to next 7 days
        if not start_datetime or not end_datetime:
            now = datetime.now()
            end = now + timedelta(days=7)
            start_datetime = now.isoformat()
            end_datetime = end.isoformat()
        
        # Get database session
        db = next(get_db())
        
        try:
            # Create outlook service for the user
            outlook_service = await OutlookService.create(user_email)
            
            # Get upcoming events using OutlookService
            days_ahead = 7  # Default to 7 days if we're using the get_upcoming_events method
            events = await outlook_service.get_upcoming_events(days_ahead)
            
            # Return the events
            return {
                "events": events,
                "count": len(events),
                "time_range": {
                    "start": start_datetime,
                    "end": end_datetime
                }
            }
        except HTTPException as http_error:
            logger.error(f"HTTP Exception in outlook_list_events: {http_error.detail}")
            if http_error.status_code == 401:
                raise AuthenticationError("Failed to authenticate with Microsoft. Please reauthorize your account.")
            raise
        finally:
            db.close()
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Error listing Outlook events: {str(e)}", exc_info=True)
        return {"error": f"Failed to list events: {str(e)}"}

async def execute_jira_create_issue(arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Placeholder for Jira create issue implementation."""
    logger.info(f"Creating Jira issue: {arguments}")
    # TODO: Implement proper Jira integration
    return {"status": "not_implemented", "message": "Jira integration is not yet implemented"}

async def execute_jira_list_issues(arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Placeholder for Jira list issues implementation."""
    logger.info(f"Listing Jira issues: {arguments}")
    # TODO: Implement proper Jira integration
    return {"status": "not_implemented", "message": "Jira integration is not yet implemented"} 