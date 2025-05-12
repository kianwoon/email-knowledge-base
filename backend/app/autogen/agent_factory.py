import logging
from typing import Dict, Any, List, Optional, Union, Callable
import autogen
from autogen import Agent, AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from app.services.client_factory import get_user_client
from app.models.user import User
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def create_assistant(
    name: str,
    system_message: str,
    llm_config: Optional[Dict[str, Any]] = None,
    human_input_mode: str = "NEVER",
    max_consecutive_auto_reply: Optional[int] = None,
    default_auto_reply: Optional[str] = None,
    description: Optional[str] = None,
) -> AssistantAgent:
    """
    Create an AutoGen assistant agent with the given configuration.
    
    Args:
        name: Name of the assistant
        system_message: System message that defines the assistant's behavior
        llm_config: Configuration for the LLM, defaults to app config if None
        human_input_mode: When to request human input, default "NEVER"
        max_consecutive_auto_reply: Maximum number of consecutive auto replies
        default_auto_reply: Default reply when max auto replies reached
        description: Optional description of the assistant
        
    Returns:
        AssistantAgent: Configured assistant agent
    """
    logger.info(f"Creating assistant agent: {name}")
    
    if llm_config is None:
        # Default configuration using application settings
        llm_config = {
            "config_list": [
                {
                    "model": "gpt-4",
                    "api_key": "YOUR_API_KEY"
                }
            ],
            "cache_seed": 42,  # Seed for caching and reproducibility
            "temperature": 0.7
        }
    
    assistant = AssistantAgent(
        name=name,
        system_message=system_message,
        llm_config=llm_config,
        human_input_mode=human_input_mode,
        max_consecutive_auto_reply=max_consecutive_auto_reply or 10,
        description=description or f"Assistant agent '{name}'",
    )
    
    logger.debug(f"Created assistant agent: {name} with config: {llm_config}")
    return assistant

def create_user_proxy(
    name: str,
    human_input_mode: str = "ALWAYS",
    system_message: Optional[str] = None,
    code_execution_config: Optional[Dict[str, Any]] = None,
    default_auto_reply: Optional[Union[str, Callable]] = None,
    description: Optional[str] = None,
) -> UserProxyAgent:
    """
    Create an AutoGen user proxy agent.
    
    Args:
        name: Name of the user proxy
        human_input_mode: When to request human input, default "ALWAYS"
        system_message: Optional system message for the user proxy
        code_execution_config: Configuration for code execution
        default_auto_reply: Default reply when auto reply is needed
        description: Optional description of the user proxy
        
    Returns:
        UserProxyAgent: Configured user proxy agent
    """
    logger.info(f"Creating user proxy agent: {name}")

    # Default code execution configuration if none provided
    if code_execution_config is None:
        code_execution_config = {
            "work_dir": "workspace",
            "use_docker": False,  # Change to True for secure code execution
            "timeout": 60,
            "last_n_messages": 10,
        }
    
    user_proxy = UserProxyAgent(
        name=name,
        system_message=system_message,
        human_input_mode=human_input_mode,
        code_execution_config=code_execution_config,
        default_auto_reply=default_auto_reply or "",
        description=description or f"User proxy agent '{name}'",
    )
    
    logger.debug(f"Created user proxy agent: {name} with code execution: {bool(code_execution_config)}")
    return user_proxy

async def build_llm_config_for_user(
    user: User, 
    db: Session, 
    model_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> Dict[str, Any]:
    """
    Build an LLM configuration for AutoGen based on user's settings.
    
    Args:
        user: User object
        db: Database session
        model_id: Optional model ID to use, otherwise uses the user's default
        temperature: Temperature setting for the LLM
        max_tokens: Maximum tokens to generate
        
    Returns:
        Dict: LLM configuration for AutoGen
    """
    try:
        # This would be the user's client, but we need to extract just the API key and other settings
        user_client = await get_user_client(user, db, model_id)
        
        # Get API key directly from the db rather than client object
        api_key = None
        base_url = "https://api.openai.com/v1"
        
        # For system client, use settings.OPENAI_API_KEY
        from app.config import settings
        if hasattr(settings, "OPENAI_API_KEY"):
            api_key = settings.OPENAI_API_KEY
        
        # Try to get user's key from database directly
        if not api_key and user and hasattr(user, "email"):
            from app.crud.api_key_crud import get_decrypted_api_key
            provider = "openai"  # Default provider
            
            # Determine provider from model_id if provided
            if model_id:
                if model_id.startswith(("gpt-", "text-")):
                    provider = "openai"
                elif model_id.startswith("claude-"):
                    provider = "anthropic"
                elif model_id.startswith("gemini-"):
                    provider = "google"
                    
            # Get API key for the appropriate provider
            api_key = get_decrypted_api_key(db, user.email, provider)
            
            # Get base URL from user_client if available
            if hasattr(user_client, "base_url") and user_client.base_url:
                base_url = user_client.base_url
                
        # Build config with available information
        config = {
            "config_list": [
                {
                    "model": model_id or "gpt-4",
                    "api_key": api_key or "PLACEHOLDER_KEY",  # Use placeholder if no key found
                    "base_url": base_url
                }
            ],
            "cache_seed": 42,
            "temperature": temperature
        }
        
        if max_tokens:
            config["config_list"][0]["max_tokens"] = max_tokens
        
        return config
        
    except Exception as e:
        logger.error(f"Error building LLM config: {e}", exc_info=True)
        # Return fallback config
        return {
            "config_list": [
                {
                    "model": model_id or "gpt-4",
                    "api_key": "PLACEHOLDER_KEY",
                    "base_url": "https://api.openai.com/v1"
                }
            ],
            "cache_seed": 42,
            "temperature": temperature
        }

def create_group_chat(
    agents: List[Agent],
    messages: Optional[List[Dict[str, Any]]] = None,
    max_round: int = 10,
    speaker_selection_method: str = "auto",
    allow_repeat_speaker: bool = True
) -> GroupChat:
    """
    Create a group chat with the given agents.
    
    Args:
        agents: List of agents to include in the group chat
        messages: Optional list of initial messages
        max_round: Maximum number of conversation rounds, default 10
        speaker_selection_method: Method to select the next speaker
        allow_repeat_speaker: Whether the same speaker can speak multiple times in a row
        
    Returns:
        GroupChat: Configured group chat
    """
    logger.info(f"Creating group chat with {len(agents)} agents")
    
    group_chat = GroupChat(
        agents=agents,
        messages=messages or [],
        max_round=max_round,
        speaker_selection_method=speaker_selection_method,
        allow_repeat_speaker=allow_repeat_speaker,
    )
    
    logger.debug(f"Created group chat with agents: {[agent.name for agent in agents]}")
    return group_chat

def create_group_chat_manager(
    groupchat: GroupChat,
    llm_config: Optional[Dict[str, Any]] = None,
    system_message: Optional[str] = None
) -> GroupChatManager:
    """
    Create a group chat manager to orchestrate the group chat.
    
    Args:
        groupchat: The group chat to manage
        llm_config: Configuration for the LLM, defaults to app config if None
        system_message: Optional system message for the manager
        
    Returns:
        GroupChatManager: Configured group chat manager
    """
    logger.info("Creating group chat manager")
    
    if llm_config is None:
        # Default configuration using application settings
        llm_config = {
            "config_list": [
                {
                    "model": "gpt-4",
                    "api_key": "YOUR_API_KEY"
                }
            ],
            "cache_seed": 42,
            "temperature": 0.7
        }
    
    if system_message is None:
        system_message = (
            "You are a helpful AI assistant that manages a group chat."
            " Ensure each agent contributes effectively to the conversation."
            " Choose the most appropriate agent to speak next."
        )
    
    manager = GroupChatManager(
        groupchat=groupchat,
        llm_config=llm_config,
        system_message=system_message,
    )
    
    logger.debug("Created group chat manager")
    return manager 