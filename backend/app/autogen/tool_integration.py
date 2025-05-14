import logging
from typing import Dict, Any, List, Optional, Tuple
import json
import re

from sqlalchemy.orm import Session
from app.routes.chat import load_tool_manifest
from app.services.tool_executor import execute_tool

logger = logging.getLogger(__name__)

async def get_relevant_mcp_tools(user_email: str, db: Session, tool_types: List[str]) -> List[Dict[str, Any]]:
    """
    Select relevant MCP tools based on the identified tool types.
    
    Args:
        user_email: User email for loading their available tools
        db: Database session
        tool_types: List of tool type categories to match
        
    Returns:
        List of relevant MCP tool configurations
    """
    # Load all available MCP tools
    tools_config = load_tool_manifest(user_email, db)
    available_tools = tools_config.get("tools", [])
    
    # If no tool types specified, return empty list
    if not tool_types:
        return []
    
    # Filter tools based on relevance to the specified tool types
    relevant_tools = []
    
    for tool in available_tools:
        tool_name = tool.get("name", "")
        tool_desc = tool.get("description", "")
        
        # Simple keyword matching for relevant tools
        # This could be enhanced with better semantic matching
        matches = False
        for tool_type in tool_types:
            if (
                tool_type.lower() in tool_name.lower() or 
                tool_type.lower() in tool_desc.lower()
            ):
                matches = True
                break
        
        if matches:
            relevant_tools.append(tool)
    
    logger.info(f"Selected {len(relevant_tools)} relevant MCP tools out of {len(available_tools)} available")
    return relevant_tools

async def extract_tool_parameters(tool: Dict[str, Any], query: str, llm_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract parameters for a tool from the user query using an LLM.
    
    Args:
        tool: The tool configuration
        query: The user query to extract parameters from
        llm_config: LLM configuration for parameter extraction
        
    Returns:
        Dictionary of parameter values for the tool
    """
    from app.autogen.agent_factory import create_assistant
    import autogen
    
    # Get the parameters schema
    parameters_schema = tool.get("parameters", {})
    properties = parameters_schema.get("properties", {})
    required = parameters_schema.get("required", [])
    
    # If no parameters required, return empty dict
    if not properties:
        return {}
    
    # Create a temporary agent for parameter extraction
    param_extractor = create_assistant(
        name="ParameterExtractor",
        system_message=f"""You are an expert at extracting parameters from user messages.
        
For the tool '{tool.get('name')}' with description '{tool.get('description')}', 
extract the following parameters from the user's message:

{json.dumps(properties, indent=2)}

Required parameters: {', '.join(required)}

Respond with a JSON object containing ONLY the extracted parameters. For example:
{{"param1": "value1", "param2": "value2"}}

If a required parameter is missing, use null as its value.
        """,
        llm_config=llm_config
    )
    
    # Create a user proxy to simulate the question
    user_proxy = autogen.UserProxyAgent(
        name="ParamExtractorUser",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=0,
        code_execution_config=False
    )
    
    # Send the query to the parameter extractor
    user_proxy.initiate_chat(
        param_extractor,
        message=f"Extract parameters for the tool from this message: {query}"
    )
    
    # Default empty parameters
    parameters = {}
    
    # Extract the response from the last message
    if len(user_proxy.chat_messages[param_extractor.name]) > 0:
        last_message = user_proxy.chat_messages[param_extractor.name][-1]["content"]
        try:
            # Extract JSON from the response (it might be embedded in text)
            json_match = re.search(r'({.*})', last_message, re.DOTALL)
            if json_match:
                parameters = json.loads(json_match.group(1))
        except Exception as e:
            logger.error(f"Error parsing parameter extraction: {e}")
    
    # Ensure all required parameters have at least null value
    for param in required:
        if param not in parameters:
            parameters[param] = None
    
    return parameters

async def execute_mcp_tool_for_query(tool: Dict[str, Any], query: str, user_email: str, llm_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an MCP tool based on the query.
    
    Args:
        tool: The tool configuration
        query: The user query to extract parameters from
        user_email: The user email for authorization
        llm_config: LLM configuration for parameter extraction
        
    Returns:
        The result of the tool execution
    """
    tool_name = tool.get("name", "")
    
    # Extract parameters from the query
    parameter_values = await extract_tool_parameters(tool, query, llm_config)
    
    # Log the extracted parameters
    logger.info(f"Extracted parameters for tool {tool_name}: {parameter_values}")
    
    # Execute the tool with the extracted parameters
    try:
        result = await execute_tool(
            tool_name=tool_name,
            arguments=parameter_values,
            tool_metadata=tool,
            user_email=user_email
        )
        return result
    except Exception as e:
        logger.error(f"Error executing MCP tool {tool_name}: {e}")
        return {"error": f"Tool execution failed: {str(e)}"} 