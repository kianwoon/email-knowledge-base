import logging
from typing import Dict, Any, Optional, Union

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.crud import api_key_crud
from app.crud.user_llm_config_crud import get_user_llm_config

# Set up logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

DEFAULT_TIMEOUT = 60.0  # 60 seconds default timeout

def get_system_client() -> AsyncOpenAI:
    """
    Get a default client using the system-wide API key.
    Used for background processes and email ingestion.
    
    Returns:
        AsyncOpenAI: OpenAI client configured with system API key
    """
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=DEFAULT_TIMEOUT
    )

async def get_user_client(
    user: User, 
    db: Session,
    model_id: Optional[str] = None
) -> AsyncOpenAI:
    """
    Get a client for a specific user, using their preferred API key and model settings.
    
    Args:
        user: The user to create a client for
        db: Database session
        model_id: Optional model ID to use for this client
        
    Returns:
        AsyncOpenAI: OpenAI client configured with user's settings
    """
    # Default to system key if no user-specific configuration is found
    if not user:
        logger.debug("No user provided, returning system client")
        return get_system_client()
    
    try:
        # Find the user's preferred LLM config
        user_llm_config = get_user_llm_config(db=db, user_id=user.id)
        
        # Use provided model_id or the user's default from their config
        target_model_id = model_id or (user_llm_config.default_model_id if user_llm_config else None)
        
        if not target_model_id:
            logger.debug(f"No model ID specified for user {user.email}, using system defaults")
            return get_system_client()
        
        # Determine provider from model_id
        provider = "openai"  # Default provider
        if target_model_id:
            if target_model_id.startswith(("gpt-", "text-")):
                provider = "openai"
            elif target_model_id.startswith("claude-"):
                provider = "anthropic"
            elif target_model_id.startswith("gemini-"):
                provider = "google"
                
        # Get the decrypted API key for the selected provider
        decrypted_api_key = api_key_crud.get_decrypted_api_key(db=db, user_email=user.email, provider=provider)
        
        if not decrypted_api_key:
            logger.warning(f"User {user.email} has no API key for provider {provider} (model {target_model_id}), using system client")
            return get_system_client()
        
        # Set up client kwargs
        user_api_key = decrypted_api_key
        provider_timeout = DEFAULT_TIMEOUT  # Use default timeout as APIKeyDB doesn't have a timeout field
        
        client_kwargs = {"api_key": user_api_key, "timeout": provider_timeout}
        
        # Get model base URL if needed
        db_api_key = api_key_crud.get_api_key(db=db, user_email=user.email, provider=provider)
        
        # Add base_url if provided
        if db_api_key and db_api_key.model_base_url:
            client_kwargs["base_url"] = db_api_key.model_base_url
            
        # Special case handling for specific providers
        if provider == "deepseek":
            client_kwargs["base_url"] = "https://api.deepseek.com/v1"
        
        logger.debug(f"Created client for user {user.email} with model {target_model_id}")
        return AsyncOpenAI(**client_kwargs)
        
    except Exception as e:
        logger.error(f"Error creating user client for {user.email}: {e}", exc_info=True)
        # Fall back to system client on error
        return get_system_client()

# Function to determine if we should use user client or system client
def should_use_user_client(context: str) -> bool:
    """
    Determine if a user client should be used based on context.
    
    Args:
        context: The operation context (e.g., 'email_ingestion', 'chat', 'rate_card')
        
    Returns:
        bool: True if user client should be used, False if system client
    """
    # Email ingestion always uses system client
    if context == 'email_ingestion':
        return False
        
    # Most other operations should use user client
    return True 