"""
AutoGen Module for Knowledge Base Builder
This module integrates Microsoft AutoGen framework for multi-agent conversations
"""

# Re-export key components for easier imports
from app.autogen.agent_factory import create_assistant, create_user_proxy, create_group_chat
from app.autogen.workflows import run_research_workflow, run_code_generation_workflow, run_qa_workflow, run_chat_workflow
from app.autogen.custom_agents import ResearchAgent, CodingAgent, CriticAgent, create_agent_team

