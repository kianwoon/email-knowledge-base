import logging
from typing import Dict, Any, List, Optional, Union, Callable
import autogen
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from app.services.client_factory import get_user_client
from app.models.user import User
from sqlalchemy.orm import Session
from app.crud import api_key_crud
from app.crud.user_llm_config_crud import get_user_llm_config
from app.config import settings
from app.autogen.compatibility import create_compatible_openai_config, patch_autogen_openai_client

logger = logging.getLogger(__name__)

# Apply patches to ensure compatibility between AutoGen and OpenAI
patch_autogen_openai_client()

def create_assistant(
    name: str = "Assistant",
    system_message: str = "You are a helpful AI assistant.",
    llm_config: Optional[Dict[str, Any]] = None,
    human_input_mode: str = "NEVER"
) -> AssistantAgent:
    """
    Create an AutoGen assistant agent.
    
    Args:
        name: Name of the assistant
        system_message: System message/instructions for the assistant
        llm_config: LLM configuration
        human_input_mode: Mode for human input
        
    Returns:
        AssistantAgent: The created assistant agent
    """
    logger.info(f"Creating assistant agent: {name}")
    
    # Use default config if none provided
    if llm_config is None:
        llm_config = {
            "config_list": [
                {
                    "model": "gpt-3.5-turbo",
                    "api_key": settings.OPENAI_API_KEY
                }
            ],
            "temperature": 0.7
        }
    
    try:
        # Create the assistant agent using AutoGen 0.9.0 API
        assistant = AssistantAgent(
            name=name,
            system_message=system_message,
            llm_config=llm_config,
            human_input_mode=human_input_mode
        )
        return assistant
    except Exception as e:
        logger.error(f"Error creating assistant agent: {str(e)}", exc_info=True)
        # Try with an even simpler configuration
        try:
            minimal_llm_config = {
                "config_list": [
                    {
                        "model": "gpt-3.5-turbo",
                        "api_key": settings.OPENAI_API_KEY
                    }
                ]
            }
            assistant = AssistantAgent(
                name=name,
                system_message=system_message,
                llm_config=minimal_llm_config,
                human_input_mode=human_input_mode
            )
            return assistant
        except Exception as e2:
            logger.error(f"Second attempt failed: {str(e2)}", exc_info=True)
            raise RuntimeError(f"Failed to create assistant agent: {str(e)}")

def create_user_proxy(
    name: str = "User", 
    human_input_mode: str = "NEVER", 
    llm_config: Optional[Dict[str, Any]] = None,
    system_message: Optional[str] = None
) -> UserProxyAgent:
    """
    Create a UserProxyAgent that represents a user in the conversation.
    
    Args:
        name: Name of the user proxy agent
        human_input_mode: When to request human input
        llm_config: Optional LLM configuration for the user proxy
        system_message: Optional system message for the user proxy
        
    Returns:
        UserProxyAgent: Configured user proxy agent
    """
    logger.info(f"Creating user proxy agent: {name}")
    
    try:
        # For AutoGen 0.9.0, the code_execution_config parameter usage has changed
        user_proxy = UserProxyAgent(
            name=name,
            human_input_mode=human_input_mode,
            llm_config=llm_config,
            system_message=system_message,
            # In 0.9.0, use execute_code=False instead of code_execution_config=False
            code_execution_config={"use_docker": False, "execute_code": False}
        )
        return user_proxy
    except Exception as e:
        logger.error(f"Error creating user proxy agent: {str(e)}", exc_info=True)
        # Try alternative parameter format for older/newer versions
        try:
            user_proxy = UserProxyAgent(
                name=name,
                human_input_mode=human_input_mode,
                llm_config=llm_config,
                system_message=system_message,
                code_execution_config=None
            )
            return user_proxy
        except Exception as e2:
            logger.error(f"Second attempt failed: {str(e2)}", exc_info=True)
            raise RuntimeError(f"Failed to create user proxy agent: {str(e)}")

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
        
        # Use model_id parameter if provided, otherwise use user's default
        target_model_id = model_id if model_id else user_llm_config.model_id if user_llm_config else "gpt-3.5-turbo"
        
        # Determine provider from model ID to get the right API key
        if "gpt" in target_model_id.lower() or "text-davinci" in target_model_id.lower():
            provider = "openai"
        else:
            provider = "anthropic"  # Default fallback, could be improved
        
        # Get the API key for the model
        api_key = None
        if user:
            api_key = api_key_crud.get_decrypted_api_key(db=db, user_email=user.email, provider=provider)
            
        # If no API key found, use system default
        if not api_key:
            api_key = settings.OPENAI_API_KEY if provider == "openai" else settings.ANTHROPIC_API_KEY
            
        # Create config for OpenAI 1.78.1 format
        config = {
            "config_list": [
                {
                    "model": target_model_id,
                    "api_key": api_key
                }
            ],
            "temperature": temperature
        }
        
        # Add max tokens if provided
        if max_tokens:
            config["config_list"][0]["max_tokens"] = max_tokens
            
        logger.debug("LLM config built successfully")
        return config
            
    except Exception as e:
        logger.error(f"Error building LLM config: {str(e)}", exc_info=True)
        
        # Return a fallback config
        return {
            "config_list": [
                {
                    "model": "gpt-3.5-turbo",
                    "api_key": settings.OPENAI_API_KEY
                }
            ],
            "temperature": temperature
        }

def create_group_chat(
    agents: List,
    messages: Optional[List[Dict[str, Any]]] = None,
    max_round: int = 10,
    speaker_selection_method: str = "auto",
    allow_repeat_speaker: bool = True
) -> GroupChat:
    """
    Create a group chat with the given agents.
    
    Args:
        agents: List of agents to include in the chat
        messages: Optional list of initial messages
        max_round: Maximum number of conversation rounds
        speaker_selection_method: Method to select the next speaker
        allow_repeat_speaker: Whether to allow the same speaker consecutively
        
    Returns:
        GroupChat: The created group chat
    """
    logger.info(f"Creating group chat with {len(agents)} agents")
    
    try:
        # For AutoGen 0.9.0
        group_chat = GroupChat(
            agents=agents,
            messages=messages or [],
            max_round=max_round,
            speaker_selection_method=speaker_selection_method,
            allow_repeat_speaker=allow_repeat_speaker
        )
        return group_chat
    except Exception as e:
        logger.error(f"Error creating group chat: {str(e)}", exc_info=True)
        
        # Try with minimal parameters as fallback
        try:
            group_chat = GroupChat(
                agents=agents,
                messages=messages or [],
                max_round=max_round
            )
            return group_chat
        except Exception as e2:
            logger.error(f"Second attempt failed: {str(e2)}", exc_info=True)
            raise RuntimeError(f"Failed to create group chat: {str(e)}")

def create_group_chat_manager(
    groupchat: GroupChat,
    llm_config: Optional[Dict[str, Any]] = None,
    system_message: Optional[str] = None
) -> GroupChatManager:
    """
    Create a manager for a group chat.
    
    Args:
        groupchat: The group chat to manage
        llm_config: Optional LLM configuration for the manager
        system_message: Optional system message for the manager
        
    Returns:
        GroupChatManager: The created group chat manager
    """
    logger.info("Creating group chat manager")
    
    try:
        # For AutoGen 0.9.0
        manager = GroupChatManager(
            groupchat=groupchat,
            llm_config=llm_config,
            system_message=system_message or "You are the manager of this group chat. Ensure the conversation stays on topic and productive."
        )
        return manager
    except Exception as e:
        logger.error(f"Error creating group chat manager: {str(e)}", exc_info=True)
        
        # Try with minimal parameters as fallback
        try:
            minimal_llm_config = None
            if llm_config:
                minimal_llm_config = {
                    "config_list": llm_config.get("config_list", [{"model": "gpt-3.5-turbo", "api_key": settings.OPENAI_API_KEY}])
                }
                
            manager = GroupChatManager(
                groupchat=groupchat,
                llm_config=minimal_llm_config,
                system_message=system_message or "You are the manager of this group chat."
            )
            return manager
        except Exception as e2:
            logger.error(f"Second attempt failed: {str(e2)}", exc_info=True)
            raise RuntimeError(f"Failed to create group chat manager: {str(e)}")

# Helper type hint to support different versions of AutoGen
Agent = Any  # This could be any of AutoGen's agent types 