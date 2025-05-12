import logging
from typing import Dict, Any, List, Optional, Union, Callable
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
        if system_message is None:
            system_message = """You are an expert research agent capable of deep investigation on topics.
            
Your responsibilities include:
1. Thoroughly researching topics using all available information
2. Providing comprehensive and balanced analysis
3. Citing sources and evidence for all claims
4. Identifying gaps in knowledge and addressing them
5. Organizing information in a structured, easy-to-understand format
6. Considering multiple perspectives on controversial topics

Always maintain scholarly rigor in your responses and avoid making unsupported claims.
When uncertain, acknowledge limitations in current knowledge.
"""

        # Call parent constructor
        super().__init__(
            name=name,
            system_message=system_message,
            llm_config=llm_config,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply or 10,
            human_input_mode=human_input_mode,
            code_execution_config=code_execution_config,
            **kwargs
        )
        
        # Additional capabilities specific to research
        self.research_databases = kwargs.get("research_databases", [])
        self.knowledge_areas = kwargs.get("knowledge_areas", [])
        
        logger.info(f"Created ResearchAgent: {name}")

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
        if system_message is None:
            system_message = """You are an expert software developer with deep knowledge of programming best practices.
            
Your responsibilities include:
1. Writing clean, efficient, and maintainable code
2. Following industry best practices and design patterns
3. Providing comprehensive documentation
4. Ensuring proper error handling and edge case management
5. Writing testable code with clear examples
6. Considering security, performance, and scalability

Optimize your code for readability and maintainability first, then for performance.
Always include appropriate error handling and validate inputs properly.
"""

        # Call parent constructor
        super().__init__(
            name=name,
            system_message=system_message,
            llm_config=llm_config,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply or 10,
            human_input_mode=human_input_mode,
            code_execution_config=code_execution_config,
            **kwargs
        )
        
        # Additional capabilities specific to coding
        self.preferred_languages = kwargs.get("preferred_languages", ["Python", "JavaScript", "TypeScript"])
        self.development_frameworks = kwargs.get("development_frameworks", [])
        
        logger.info(f"Created CodingAgent: {name}")

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
        if system_message is None:
            system_message = """You are an expert critical thinker and evaluator.
            
Your responsibilities include:
1. Identifying logical fallacies and weak arguments
2. Pointing out assumptions and biases
3. Evaluating the quality and reliability of evidence
4. Challenging claims without sufficient support
5. Suggesting alternative perspectives and interpretations
6. Providing constructive feedback for improvement

Maintain a respectful tone while being thorough in your critical analysis.
Focus on strengthening arguments rather than simply tearing them down.
"""

        # Call parent constructor
        super().__init__(
            name=name,
            system_message=system_message,
            llm_config=llm_config,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply or 10,
            human_input_mode=human_input_mode,
            code_execution_config=code_execution_config,
            **kwargs
        )
        
        # Additional capabilities specific to critical analysis
        self.evaluation_frameworks = kwargs.get("evaluation_frameworks", [])
        self.critical_methodologies = kwargs.get("critical_methodologies", [])
        
        logger.info(f"Created CriticAgent: {name}")

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
    
    # Create each agent specified in the team config
    for agent_config in team_config.get("agents", []):
        agent_type = agent_config.get("type", "assistant")
        name = agent_config.get("name", f"Agent_{len(agents)}")
        system_message = agent_config.get("system_message")
        
        if agent_type == "researcher":
            agent = ResearchAgent(
                name=name,
                system_message=system_message,
                llm_config=llm_config,
                **agent_config.get("kwargs", {})
            )
        elif agent_type == "coder":
            agent = CodingAgent(
                name=name,
                system_message=system_message,
                llm_config=llm_config,
                **agent_config.get("kwargs", {})
            )
        elif agent_type == "critic":
            agent = CriticAgent(
                name=name,
                system_message=system_message,
                llm_config=llm_config,
                **agent_config.get("kwargs", {})
            )
        else:
            # Default to standard assistant
            agent = create_assistant(
                name=name,
                system_message=system_message or "You are a helpful assistant.",
                llm_config=llm_config,
                **agent_config.get("kwargs", {})
            )
        
        agents.append(agent)
    
    logger.info(f"Created agent team with {len(agents)} agents")
    return agents 