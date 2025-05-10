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
        is_custom = False
        if tool_metadata:
            # Tool is custom if it has the is_custom flag set or has an entrypoint defined
            is_custom = tool_metadata.get("is_custom", False) or "entrypoint" in tool_metadata
            
        if is_custom:
            logger.info(f"Executing custom MCP tool: {tool_name}")
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
    logger.debug(f"Tool arguments: {arguments}")
    logger.debug(f"Tool metadata: {tool_metadata}")
    
    # Ensure we have the correct tool name
    if "name" in tool_metadata and tool_metadata["name"] != tool_name:
        logger.warning(f"Tool name mismatch: request={tool_name}, metadata={tool_metadata['name']}. Using metadata name.")
        tool_name = tool_metadata["name"]
    
    # Check if this tool needs name remapping for the remote service
    if "__remote_tool_name" in tool_metadata:
        remote_tool_name = tool_metadata["__remote_tool_name"]
        logger.info(f"Found remote tool name mapping: {tool_name} -> {remote_tool_name}")
        arguments["__remote_tool_name"] = remote_tool_name
    
    # For calendar tools, we'll try different endpoint variations
    potential_endpoints = [entrypoint]
    
    # If it's a calendar tool, add alternative endpoints
    is_calendar_tool = "calendar" in tool_name.lower()
    is_email_kb_endpoint = "email-knowledge-base" in entrypoint
    
    if is_calendar_tool and is_email_kb_endpoint:
        # Add potential alternative endpoint URLs
        base_url = entrypoint.split('/invoke')[0]  # Get the base URL without /invoke paths
        potential_endpoints = [
            entrypoint,  # Original endpoint (likely /invoke/invoke)
            f"{base_url}/invoke",  # Single /invoke
            f"{base_url}/api/invoke",  # API path
            f"{base_url}/api/tools/invoke",  # Another common pattern
            f"{base_url}/api/v1/invoke"  # Versioned API
        ]
        logger.info(f"Will try multiple potential endpoints for calendar tool: {potential_endpoints}")
        
    for endpoint_url in potential_endpoints:
        try:
            # Log which endpoint we're trying
            if endpoint_url != entrypoint:
                logger.info(f"Trying alternative endpoint URL: {endpoint_url}")
                
            # If entrypoint is a URL, make an HTTP request
            if endpoint_url.startswith(("http://", "https://")):
                logger.info(f"Executing tool via HTTP entrypoint: {endpoint_url}, tool_name={tool_name}")
                result = await execute_http_entrypoint(endpoint_url, arguments, user_email, tool_name)
                
                # Check if the request was successful (no error in the result)
                if "error" not in result or (isinstance(result.get("error"), str) and "Unknown tool" not in result["error"]):
                    # If successful or error is not about unknown tool, return the result
                    return result
                    
                # If we got an "Unknown tool" error and have more endpoints to try, continue to the next one
                if "error" in result and isinstance(result.get("error"), str) and "Unknown tool" in result["error"] and endpoint_url != potential_endpoints[-1]:
                    logger.warning(f"Endpoint {endpoint_url} returned 'Unknown tool' error. Trying next endpoint.")
                    continue
                    
                # If this was the last endpoint or error is not about unknown tool, return the result
                return result
                
            # If we're here, the endpoint wasn't a URL or all URLs failed
            elif "." in endpoint_url:
                logger.info(f"Executing tool via function entrypoint: {endpoint_url}")
                return await execute_function_entrypoint(endpoint_url, arguments, user_email)
            
            # If entrypoint is just a path without protocol
            else:
                # Assume it's a relative API path
                base_url = settings.MCP_SERVER_URL or "http://localhost:8000"
                full_url = f"{base_url.rstrip('/')}/{endpoint_url.lstrip('/')}"
                logger.info(f"Using base URL: {base_url}, full URL: {full_url}, tool_name={tool_name}")
                return await execute_http_entrypoint(full_url, arguments, user_email, tool_name)
                
        except Exception as e:
            # Log the error but continue trying other endpoints if available
            logger.error(f"Error executing custom MCP tool {tool_name} with endpoint {endpoint_url}: {str(e)}")
            if endpoint_url == potential_endpoints[-1]:
                # If this was the last endpoint, raise the exception
                return {"error": f"Tool execution failed with all endpoints: {str(e)}"}
                
    # This should never be reached unless all endpoints fail
    return {"error": f"Tool execution failed with all endpoints"}

async def execute_http_entrypoint(url: str, arguments: Dict[str, Any], user_email: Optional[str] = None, tool_name: Optional[str] = None) -> Dict[str, Any]:
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
        
        # Format the request payload according to the expected format
        # If the URL contains '/invoke', it likely expects the MCP format with name and arguments
        if '/invoke' in url:
            if not tool_name:
                logger.warning(f"Tool name not provided for MCP tool request to {url}")
                tool_name = "unknown_tool"  # Fallback name if not provided
                
            # Check if we need to map the local tool name to a different remote tool name
            # This could be specified in the arguments as a special parameter
            remote_tool_name = tool_name
            
            # For calendar-related tools, create a list of potential names to try
            potential_tool_names = [remote_tool_name]
            
            if "__remote_tool_name" in arguments:
                remote_tool_name = arguments.pop("__remote_tool_name")
                logger.info(f"Using mapped remote tool name: {remote_tool_name} (local name: {tool_name})")
                potential_tool_names = [remote_tool_name]  # Reset list to just use the provided remote name
            elif "calendar" in tool_name.lower():
                # Only use alternatives if no explicit remote name was provided
                potential_tool_names = [
                    remote_tool_name,  # Original name (calendar_list_events)
                    "list_events",
                    "calendar",
                    "get_calendar",
                    "get_events",
                    "calendar_events",
                    "list_calendar_events",
                    "calendar_lookup"
                ]
                logger.info(f"Will try multiple potential tool names for calendar tool: {potential_tool_names}")
            
            # For our first attempt, use the primary tool name (either mapped or original)
            payload = {
                "name": potential_tool_names[0],
                "arguments": arguments
            }
            logger.debug(f"Formatted MCP tool request payload: {payload}")
            
            # Send the request with the initial tool name
            logger.debug(f"Making HTTP request to {url} with payload: {payload}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try each potential tool name in sequence
                for i, name in enumerate(potential_tool_names):
                    if i > 0:  # Skip the first one as we already tried it
                        payload["name"] = name
                        logger.info(f"Retrying with alternate tool name: {name}")
                    
                    response = await client.post(url, json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        # Success! We found the right tool name
                        logger.info(f"Successfully called tool with name: {name}")
                        break
                    elif response.status_code == 400 and "Unknown tool" in response.text and i < len(potential_tool_names) - 1:
                        # Continue to the next tool name
                        logger.warning(f"Tool name '{name}' not recognized by the server. Trying next alternative.")
                        continue
                    else:
                        # Other error or last attempt
                        if response.status_code >= 400:
                            logger.error(f"HTTP error {response.status_code} from {url}: {response.text}")
                            return {"error": f"Tool execution failed with status {response.status_code}: {response.text}"}
            
            # Process the response from the last attempt
            try:
                result = response.json()
                return result
            except json.JSONDecodeError:
                # If not JSON, return text
                return {"result": response.text}
        else:
            # Use arguments directly for other APIs
            payload = arguments
            
            logger.debug(f"Making HTTP request to {url} with payload: {payload}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
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