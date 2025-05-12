import logging
from typing import Dict, Any, List, Optional, Union, Callable
import autogen
from autogen import Agent, AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from app.services.client_factory import get_user_client
from app.models.user import User
from sqlalchemy.orm import Session
from app.crud import api_key_crud
from app.crud.user_llm_config_crud import get_user_llm_config
from app.config import settings

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
    logger.info(f"Building LLM config for user {user.email if user else 'unknown'}")
    
    try:
        # Find the user's preferred LLM config
        user_llm_config = get_user_llm_config(db=db, user_id=user.id) if user else None
        
        # Use provided model_id or the user's default from their config
        target_model_id = model_id or (user_llm_config.default_model_id if user_llm_config else settings.DEFAULT_CHAT_MODEL)
        
        # Determine provider from model_id
        provider = "openai"  # Default provider
        if target_model_id:
            if target_model_id.startswith(("gpt-", "text-")):
                provider = "openai"
            elif target_model_id.startswith("claude-"):
                provider = "anthropic"
            elif target_model_id.startswith("gemini-"):
                provider = "google"
        
        # Get the API key for the model
        api_key = None
        if user:
            api_key = api_key_crud.get_decrypted_api_key(db=db, user_email=user.email, provider=provider)
        
        # Fall back to system key if needed
        if not api_key:
            api_key = settings.OPENAI_API_KEY
            logger.info(f"Using system API key for {target_model_id}")
        
        # Return the LLM config for AutoGen
        config = {
            "config_list": [
                {
                    "model": target_model_id,
                    "api_key": api_key,
                    "base_url": "https://api.openai.com/v1"
                }
            ],
            "cache_seed": 42,  # For caching and reproducibility
            "temperature": temperature
        }
        
        # Add max tokens if provided
        if max_tokens:
            config["config_list"][0]["max_tokens"] = max_tokens
            
        return config
    except Exception as e:
        logger.error(f"Error building LLM config: {str(e)}", exc_info=True)
        # Return a fallback config
        return {
            "config_list": [
                {
                    "model": model_id or settings.DEFAULT_CHAT_MODEL,
                    "api_key": settings.OPENAI_API_KEY,
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
    logger.warning("AutoGen is temporarily disabled due to compatibility issues")
    
    # Return a stub GroupChat
    return GroupChat(
        agents=agents,
        messages=messages or [],
        max_round=max_round,
        speaker_selection_method=speaker_selection_method,
        allow_repeat_speaker=allow_repeat_speaker,
    )

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
    logger.warning("AutoGen is temporarily disabled due to compatibility issues")
    
    # Return a stub GroupChatManager
    return GroupChatManager(
        groupchat=groupchat,
        llm_config=llm_config,
        system_message=system_message,
    ) 