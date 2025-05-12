import logging
from typing import Dict, Any, List, Optional, Union, Callable
# Re-enable autogen imports
import autogen
from autogen import AssistantAgent, UserProxyAgent
from app.autogen.agent_factory import create_assistant

logger = logging.getLogger(__name__)

class ResearchAgent(AssistantAgent):
    """
    Specialized agent for research tasks with enhanced context retrieval.
    Extends the standard AssistantAgent with additional research capabilities.
    """
    
    def __init__(
        self, 
        name: str, 
        system_message: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        is_termination_msg: Optional[Callable[[Dict[str, Any]], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: str = "NEVER",
        code_execution_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            system_message=system_message or "You are a research expert who provides detailed information.",
            llm_config=llm_config,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            **kwargs
        )

class CodingAgent(AssistantAgent):
    """
    Specialized agent for software development tasks.
    Extends the standard AssistantAgent with enhanced coding capabilities.
    """
    
    def __init__(
        self, 
        name: str, 
        system_message: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        is_termination_msg: Optional[Callable[[Dict[str, Any]], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: str = "NEVER",
        code_execution_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            system_message=system_message or "You are a coding expert who writes clean, efficient code.",
            llm_config=llm_config,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            **kwargs
        )

class CriticAgent(AssistantAgent):
    """
    Specialized agent for critical analysis and evaluation.
    Extends the standard AssistantAgent with enhanced critical thinking capabilities.
    """
    
    def __init__(
        self, 
        name: str, 
        system_message: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        is_termination_msg: Optional[Callable[[Dict[str, Any]], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: str = "NEVER",
        code_execution_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            system_message=system_message or "You are a critical thinking expert who evaluates ideas thoroughly.",
            llm_config=llm_config,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            **kwargs
        )

def create_agent_team(
    team_config: Dict[str, Any],
    llm_config: Dict[str, Any]
) -> List[AssistantAgent]:
    """
    Create a team of specialized agents based on the provided configuration.
    
    Args:
        team_config: Configuration for the team of agents
        llm_config: Configuration for the LLM to use
        
    Returns:
        List of created agents
    """
    agents = []
    
    # Create agents based on team_config
    for agent_config in team_config.get('agents', []):
        agent_type = agent_config.get('type', 'assistant')
        agent_name = agent_config.get('name', f'Agent-{len(agents)+1}')
        agent_system_message = agent_config.get('system_message', '')
        
        if agent_type == 'researcher':
            agent = ResearchAgent(
                name=agent_name,
                system_message=agent_system_message,
                llm_config=llm_config
            )
        elif agent_type == 'coder':
            agent = CodingAgent(
                name=agent_name,
                system_message=agent_system_message,
                llm_config=llm_config
            )
        elif agent_type == 'critic':
            agent = CriticAgent(
                name=agent_name,
                system_message=agent_system_message,
                llm_config=llm_config
            )
        else:
            # Default to standard assistant
            agent = create_assistant(
                name=agent_name,
                system_message=agent_system_message,
                llm_config=llm_config
            )
        
        agents.append(agent)
    
    return agents 