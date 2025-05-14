"""
AutoGen Module for Knowledge Base Builder
This module integrates Microsoft AutoGen framework for multi-agent conversations
"""

# Re-export key components for easier imports
from app.autogen.agent_factory import create_assistant, create_user_proxy, create_group_chat
from app.autogen.workflows import (
    run_research_workflow, 
    run_code_generation_workflow, 
    run_qa_workflow, 
    run_chat_workflow,
    run_hybrid_orchestration_workflow  # Add new workflow
)
from app.autogen.custom_agents import ResearchAgent, CodingAgent, CriticAgent, create_agent_team
from app.autogen.conductor_agent import ConductorAgent  # Add new agent
from app.autogen.tool_integration import get_relevant_mcp_tools, execute_mcp_tool_for_query  # Add tool integration

