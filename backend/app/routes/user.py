from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Path, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
import logging

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user, User
from app.models.user import UserDB
from app.models.api_key import APIKeyCreate, APIKey
from app.utils.security import encrypt_token, decrypt_token  # Reuse the token encryption functions
from app.crud.user_crud import check_column_exists  # Import the column check function
from app.crud import api_key_crud, user_preference_crud

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Define request/response models
class ApiKeyRequest(BaseModel):
    api_key: str
    provider: str = "openai"  # Default to openai for backward compatibility

class ApiKeyResponse(BaseModel):
    api_key: Optional[str] = None
    provider: str = "openai"  # Default to openai for backward compatibility

class APIKeyInfoResponse(BaseModel):
    provider: str
    created_at: str
    last_used: Optional[str] = None

# Add Pydantic models for the request and response
class DefaultModelRequest(BaseModel):
    model_id: str
    model_config = ConfigDict(protected_namespaces=())

class DefaultModelResponse(BaseModel):
    model_id: str
    model_config = ConfigDict(protected_namespaces=())

# Legacy endpoint for backward compatibility - maps to OpenAI provider
@router.post("/api-key", status_code=status.HTTP_204_NO_CONTENT)
async def save_openai_api_key(
    api_key_data: dict = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Save the user's OpenAI API key (legacy endpoint)"""
    try:
        if not api_key_data.get("api_key"):
            raise HTTPException(status_code=400, detail="API key is required")
        
        api_key_in = APIKeyCreate(
            provider="openai",
            key=api_key_data["api_key"],
            model_base_url=api_key_data.get("model_base_url")
        )
        
        # Check if key already exists
        existing_key = api_key_crud.get_api_key(db, current_user.email, "openai")
        if existing_key:
            api_key_crud.update_api_key(db, current_user.email, "openai", new_key=api_key_in.key, model_base_url=api_key_in.model_base_url)
        else:
            api_key_crud.create_api_key(db, current_user.email, api_key_in)
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Error saving API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving API key: {str(e)}")

# New provider-specific endpoint
@router.post("/provider-api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def save_provider_api_key(
    provider: str = Path(..., description="The API provider (openai, anthropic, google)"),
    api_key_data: dict = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Save the user's API key for a specific provider"""
    try:
        if not api_key_data.get("api_key"):
            raise HTTPException(status_code=400, detail="API key is required")
        
        # Validate provider
        provider = provider.lower()
        if provider not in ["openai", "anthropic", "google", "deepseek"]:
            raise HTTPException(status_code=400, detail="Invalid provider. Supported providers: openai, anthropic, google, deepseek")
        
        api_key_in = APIKeyCreate(
            provider=provider,
            key=api_key_data["api_key"],
            model_base_url=api_key_data.get("model_base_url")
        )
        
        # Check if key already exists
        existing_key = api_key_crud.get_api_key(db, current_user.email, provider)
        if existing_key:
            api_key_crud.update_api_key(db, current_user.email, provider, new_key=api_key_in.key, model_base_url=api_key_in.model_base_url)
        else:
            api_key_crud.create_api_key(db, current_user.email, api_key_in)
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Error saving {provider} API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving {provider} API key: {str(e)}")

# Legacy endpoint for backward compatibility - maps to OpenAI provider
@router.get("/api-key", response_model=ApiKeyResponse)
async def get_openai_api_key(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's OpenAI API key (legacy endpoint)."""
    try:
        # Get from the API keys table
        decrypted_key = api_key_crud.get_decrypted_api_key(db, current_user.email, "openai")
        return {"api_key": decrypted_key, "provider": "openai"}
    except Exception as e:
        logger.error(f"Error getting OpenAI API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting OpenAI API key: {str(e)}")

# New provider-specific endpoint
@router.get("/provider-api-keys/{provider}", response_model=ApiKeyResponse)
async def get_provider_api_key(
    provider: str = Path(..., description="The API provider (openai, anthropic, google)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get user's API key for a specific provider."""
    try:
        # Validate provider
        provider = provider.lower()
        if provider not in ["openai", "anthropic", "google", "deepseek"]:
            raise HTTPException(status_code=400, detail="Invalid provider. Supported providers: openai, anthropic, google, deepseek")
        
        # Get from the API keys table
        decrypted_key = api_key_crud.get_decrypted_api_key(db, current_user.email, provider)
        return {"api_key": decrypted_key, "provider": provider}
    except Exception as e:
        logger.error(f"Error getting {provider} API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting {provider} API key: {str(e)}")

# Legacy endpoint for backward compatibility - maps to OpenAI provider
@router.delete("/api-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_openai_api_key(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete user's OpenAI API key (legacy endpoint)."""
    try:
        # Delete from the API keys table
        api_key_crud.delete_api_key(db, current_user.email, "openai")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Error deleting OpenAI API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting OpenAI API key: {str(e)}")

# New provider-specific endpoint
@router.delete("/provider-api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_api_key(
    provider: str = Path(..., description="The API provider (openai, anthropic, google)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete user's API key for a specific provider."""
    try:
        # Validate provider
        provider = provider.lower()
        if provider not in ["openai", "anthropic", "google", "deepseek"]:
            raise HTTPException(status_code=400, detail="Invalid provider. Supported providers: openai, anthropic, google, deepseek")
        
        # Delete from the API keys table
        api_key_crud.delete_api_key(db, current_user.email, provider)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Error deleting {provider} API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting {provider} API key: {str(e)}")

@router.get("/provider-api-keys", response_model=List[APIKey])
async def get_all_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all active API keys for the user across all providers."""
    try:
        # Fetch only active keys directly using CRUD is better if possible,
        # but filtering here works too.
        all_db_keys = api_key_crud.get_all_api_keys(db, current_user.email)
        active_keys = [key for key in all_db_keys if key.is_active]
        
        # Pydantic will automatically map the fields based on the APIKey schema
        return active_keys
    except Exception as e:
        logger.error(f"Error getting API keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting API keys: {str(e)}")

@router.post("/default-model", response_model=DefaultModelResponse)
def set_default_model(
    model_request: DefaultModelRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Set the default LLM model for the current user
    """
    # Save the preference
    user_preference_crud.set_default_llm_model(db, current_user.email, model_request.model_id)
    
    return {"model_id": model_request.model_id}

@router.get("/default-model", response_model=DefaultModelResponse)
def get_default_model(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the default LLM model for the current user
    """
    # Get the preference
    model_id = user_preference_crud.get_default_llm_model(db, current_user.email)
    
    # Return a default model if none is set
    if not model_id:
        model_id = "gpt-3.5-turbo"  # Default model
    
    return {"model_id": model_id} 