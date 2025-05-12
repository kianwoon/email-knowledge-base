"""
Compatibility utilities for AutoGen with different OpenAI client versions.
This module provides functions to ensure compatibility between AutoGen and OpenAI APIs.
"""

import logging
import functools
import inspect
import sys
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def create_compatible_openai_config(
    model: str,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a configuration that works with AutoGen 0.9.0 and OpenAI 1.78.1.
    
    This function creates a minimal configuration that's compatible with the current
    AutoGen and OpenAI client versions.
    
    Args:
        model: The model ID to use (e.g., "gpt-4o")
        api_key: The API key for authentication
        temperature: The temperature setting for generation
        max_tokens: Optional maximum tokens to generate
        
    Returns:
        Dict: Compatible configuration for AutoGen
    """
    # Create a minimal config with just the essential parameters
    config = {
        "model": model,
        "api_key": api_key,
        "temperature": temperature
    }
    
    # Add max_tokens if provided
    if max_tokens:
        config["max_tokens"] = max_tokens
    
    # Wrap in config_list format for AutoGen
    return {"config_list": [config]}

def patch_autogen_openai_client():
    """
    Apply a comprehensive patch to AutoGen's OpenAI client to work with OpenAI 1.78.1.
    """
    try:
        # Try to import required modules
        import autogen
        from autogen.oai import OpenAIWrapper
        import openai
        
        logger.info(f"Patching AutoGen OpenAI client (AutoGen version: {autogen.__version__}, OpenAI version: {openai.__version__})")
        
        # For AutoGen 0.9.0, the OpenAIWrapper structure is different
        if hasattr(OpenAIWrapper, 'create'):
            original_create = OpenAIWrapper.create
            
            @functools.wraps(original_create)
            def patched_create(cls, config_list=None, **kwargs):
                """Patched create method that handles OpenAI 1.78.1 compatibility"""
                logger.debug("Using patched OpenAIWrapper.create method")
                
                # Clean up config_list items
                if config_list:
                    for config in config_list:
                        if isinstance(config, dict):
                            # Remove problematic parameters if they exist
                            for key in ['proxies', 'proxy']:
                                if key in config:
                                    del config[key]
                
                try:
                    return original_create(cls, config_list=config_list, **kwargs)
                except Exception as e:
                    logger.warning(f"Error in original create method: {e}")
                    
                    # Try with minimal config list
                    if config_list:
                        minimal_config_list = []
                        for config in config_list:
                            if isinstance(config, dict):
                                minimal_config = {
                                    'model': config.get('model', 'gpt-3.5-turbo'),
                                    'api_key': config.get('api_key', '')
                                }
                                minimal_config_list.append(minimal_config)
                        
                        return original_create(cls, config_list=minimal_config_list, **kwargs)
                    return original_create(cls, **kwargs)
            
            # Apply the patch
            OpenAIWrapper.create = classmethod(patched_create)
            logger.info("Successfully patched OpenAIWrapper.create method")
        
        # Patch OpenAI client initialization if needed
        if hasattr(OpenAIWrapper, '_create_client'):
            original_create_client = OpenAIWrapper._create_client
            
            @functools.wraps(original_create_client)
            def patched_create_client(self, config, base_url=None, api_key=None, **kwargs):
                """Patched _create_client method that removes problematic parameters"""
                logger.debug("Using patched OpenAIWrapper._create_client method")
                
                # Remove problematic parameters
                for key in ['proxies', 'proxy']:
                    if key in kwargs:
                        del kwargs[key]
                
                try:
                    # For newer versions of autogen, the signature might have changed
                    sig = inspect.signature(original_create_client)
                    if 'base_url' in sig.parameters and 'api_key' in sig.parameters:
                        return original_create_client(self, config, base_url=base_url, api_key=api_key, **kwargs)
                    else:
                        return original_create_client(self, config, **kwargs)
                except Exception as e:
                    logger.warning(f"Error in original _create_client method: {e}")
                    
                    # Try with minimal kwargs
                    minimal_kwargs = {}
                    if base_url:
                        minimal_kwargs['base_url'] = base_url
                    if api_key:
                        minimal_kwargs['api_key'] = api_key
                    
                    try:
                        if 'base_url' in sig.parameters and 'api_key' in sig.parameters:
                            return original_create_client(self, config, **minimal_kwargs)
                        else:
                            return original_create_client(self, config)
                    except Exception as e2:
                        logger.error(f"Failed to create client even with minimal config: {e2}")
                        raise
            
            # Apply the patch
            OpenAIWrapper._create_client = patched_create_client
            logger.info("Successfully patched OpenAIWrapper._create_client method")
        
        # Additional patch for message construction if needed
        if hasattr(OpenAIWrapper, '_construct_messages'):
            original_construct_messages = OpenAIWrapper._construct_messages
            
            @functools.wraps(original_construct_messages)
            def patched_construct_messages(*args, **kwargs):
                """Ensure message construction is compatible with OpenAI 1.78.1"""
                logger.debug("Using patched _construct_messages method")
                try:
                    return original_construct_messages(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Error in original _construct_messages method: {e}")
                    
                    # Try to fix common issues in message format
                    if len(args) >= 2 and isinstance(args[1], list):
                        # Fix message format if needed
                        fixed_messages = []
                        for msg in args[1]:
                            if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                                # Make sure content is a string
                                if msg['content'] is None:
                                    msg['content'] = ''
                                fixed_messages.append(msg)
                        
                        args_list = list(args)
                        args_list[1] = fixed_messages
                        return original_construct_messages(*args_list, **kwargs)
                    return original_construct_messages(*args, **kwargs)
            
            # Apply the patch
            OpenAIWrapper._construct_messages = patched_construct_messages
            logger.info("Successfully patched OpenAIWrapper._construct_messages method")
        
        logger.info("AutoGen OpenAI client patched successfully")
        return True
            
    except ImportError as e:
        logger.warning(f"Failed to patch AutoGen OpenAI client: ImportError - {str(e)}")
    except Exception as e:
        logger.warning(f"Failed to patch AutoGen OpenAI client: {str(e)}")
    
    return False

# Apply patches as soon as this module is imported
PATCHED = patch_autogen_openai_client() 