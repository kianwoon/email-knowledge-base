import logging
import json
import httpx
from typing import Dict, Any, Optional, List
import importlib
import inspect
from pydantic import ValidationError

from ..config import settings

logger = logging.getLogger(__name__)

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
    
    # Handle custom MCP tool (user-defined)
    if tool_metadata and tool_metadata.get("is_custom", False):
        return await execute_custom_mcp_tool(tool_name, arguments, tool_metadata, user_email)
        
    # Handle built-in tools based on their names
    # This could be extended to use a map or registry of tools
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
            "X-User-Email": user_email or "unknown"  # For authorization/logging
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=arguments, headers=headers)
            
            if response.status_code >= 400:
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
        
    except Exception as e:
        logger.error(f"Unexpected error calling {url}: {str(e)}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

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

# Placeholder implementations for built-in tools
async def execute_outlook_create_event(arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Placeholder for Outlook create event implementation."""
    # This should be implemented to call the actual Outlook API
    logger.info(f"Creating Outlook event: {arguments}")
    return {"status": "not_implemented", "message": "This is a placeholder for the Outlook create event tool"}

async def execute_outlook_list_events(arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Placeholder for Outlook list events implementation."""
    logger.info(f"Listing Outlook events: {arguments}")
    return {"status": "not_implemented", "message": "This is a placeholder for the Outlook list events tool"}

async def execute_jira_create_issue(arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Placeholder for Jira create issue implementation."""
    logger.info(f"Creating Jira issue: {arguments}")
    return {"status": "not_implemented", "message": "This is a placeholder for the Jira create issue tool"}

async def execute_jira_list_issues(arguments: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    """Placeholder for Jira list issues implementation."""
    logger.info(f"Listing Jira issues: {arguments}")
    return {"status": "not_implemented", "message": "This is a placeholder for the Jira list issues tool"} 