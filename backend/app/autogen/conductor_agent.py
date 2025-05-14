import logging
from typing import Dict, Any, List, Optional, Callable, Tuple, Union
import json
import re
import autogen
from autogen import AssistantAgent
from app.autogen.agent_factory import create_assistant

logger = logging.getLogger(__name__)

class ConductorAgent(AssistantAgent):
    """
    A specialized agent that determines orchestration flow and manages agent interactions.
    Acts as a router between parallel and sequential workflows based on task requirements.
    """
    
    def __init__(
        self, 
        name: str = "Conductor",
        system_message: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        default_system_message = """You are an expert Conductor agent who determines the optimal workflow for multi-agent collaboration.
        
Your job is to:
1. Analyze user requests to decide whether a parallel (fan-out) or sequential (chain) agent workflow is more appropriate
2. Route requests to appropriate domain agents based on task requirements
3. Coordinate agent interactions and synthesize final responses

For PARALLEL workflows: Route the same request to multiple domain experts simultaneously
For SEQUENTIAL workflows: Chain the request through agents in a specific order, with each agent building on previous work

Criteria for workflow selection:
- Use PARALLEL when task requires multiple perspectives or domain expertise simultaneously
- Use SEQUENTIAL when the task has clear dependencies where each step builds on previous work
- Default to PARALLEL for complex multi-faceted questions with no clear workflow dependencies
"""
        
        super().__init__(
            name=name,
            system_message=system_message or default_system_message,
            llm_config=llm_config,
            **kwargs
        )

    async def determine_workflow_type(self, query: str, llm_config: Dict[str, Any]) -> str:
        """
        Determine whether to use a parallel or sequential workflow based on user query.
        
        Args:
            query: The user's query
            llm_config: LLM configuration for making the determination
            
        Returns:
            Workflow type: "parallel" or "sequential"
        """
        # Create a temporary agent to make the determination
        workflow_classifier = create_assistant(
            name="WorkflowClassifier",
            system_message="""You are an expert workflow classifier. 
            Analyze the user query and determine if it requires a PARALLEL or SEQUENTIAL workflow.
            
            PARALLEL: Use when the query benefits from multiple independent perspectives simultaneously
            SEQUENTIAL: Use when the query has clear dependencies where each step builds on previous steps
            
            Respond with EXACTLY one word: either "parallel" or "sequential".""",
            llm_config=llm_config
        )
        
        # Create a user proxy to simulate the question
        user_proxy = autogen.UserProxyAgent(
            name="ClassifierUser",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            code_execution_config=False
        )
        
        # Initialize with "parallel" as default
        workflow_type = "parallel"
        
        # Send the query to the workflow classifier
        user_proxy.initiate_chat(
            workflow_classifier,
            message=f"Classify the following query as requiring parallel or sequential workflow: {query}"
        )
        
        # Extract the response from the last message FROM THE CLASSIFIER
        workflow_classifier_response_content = None
        if workflow_classifier in user_proxy.chat_messages: # Use agent object as key
            for msg in reversed(user_proxy.chat_messages[workflow_classifier]):
                if msg.get("name") == workflow_classifier.name: # Ensure message is from the classifier
                    workflow_classifier_response_content = msg.get("content", "").lower()
                    break
        
        if workflow_classifier_response_content and "sequential" in workflow_classifier_response_content:
            workflow_type = "sequential"
        
        logger.info(f"Determined workflow type for query: {workflow_type}")
        return workflow_type

    async def should_use_mcp_tools(self, query: str, llm_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Determine if the query would benefit from using MCP tools, and if so, which ones.
        
        Args:
            query: The user's query
            llm_config: LLM configuration for making the determination
            
        Returns:
            Tuple of (should_use_tools: bool, relevant_tool_types: List[str])
        """
        # Create a temporary agent to make the determination
        tool_classifier = create_assistant(
            name="ToolClassifier",
            system_message="""You are an expert tool classifier. 
            Analyze the user query and determine if it requires external tools.
            
            Respond with a JSON object with these properties:
            - "requires_tools": boolean (true/false)
            - "tool_types": list of strings representing types of tools that would be helpful
              (e.g., "web_search", "database", "calendar", "email", etc.)
            - "reason": brief explanation of your decision
            
            Example: {"requires_tools": true, "tool_types": ["web_search", "calculator"], "reason": "Query requires up-to-date information and numeric computation"}
            """,
            llm_config=llm_config
        )
        
        # Create a user proxy to simulate the question
        user_proxy = autogen.UserProxyAgent(
            name="ToolClassifierUser",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=0,
            code_execution_config=False
        )
        
        # Initialize defaults
        requires_tools = False
        tool_types = []
        
        # Send the query to the tool classifier
        user_proxy.initiate_chat(
            tool_classifier,
            message=f"Analyze if this query requires external tools: {query}"
        )
        
        # Extract the response from the last message FROM THE CLASSIFIER
        tool_classifier_response_content = None
        if tool_classifier in user_proxy.chat_messages: # Use agent object as key
            for msg in reversed(user_proxy.chat_messages[tool_classifier]):
                if msg.get("name") == tool_classifier.name: # Ensure message is from the classifier
                    tool_classifier_response_content = msg.get("content")
                    break
        
        if tool_classifier_response_content:
            try:
                # Extract JSON from the response (it might be embedded in text)
                json_match = re.search(r'({.*})', tool_classifier_response_content, re.DOTALL)
                if json_match:
                    classification = json.loads(json_match.group(1))
                    requires_tools = classification.get("requires_tools", False)
                    tool_types = classification.get("tool_types", [])
            except Exception as e:
                logger.error(f"Error parsing tool classification: {e}")
        
        logger.info(f"Tool use determination: requires_tools={requires_tools}, tool_types={tool_types}")
        return requires_tools, tool_types 