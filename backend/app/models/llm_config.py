from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class UserLLMConfigBase(BaseModel):
    """Base class for user LLM configuration models."""
    default_model_id: Optional[str] = Field(None, description="Default LLM model ID to use")
    preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences for LLM interactions")

class UserLLMConfigCreate(UserLLMConfigBase):
    """Model for creating a new user LLM configuration."""
    user_id: str = Field(..., description="ID of the user")

class UserLLMConfigUpdate(UserLLMConfigBase):
    """Model for updating a user LLM configuration."""
    pass

class UserLLMConfigInDB(UserLLMConfigBase):
    """Model for user LLM configuration as stored in the database."""
    id: int
    user_id: str
    
    class Config:
        orm_mode = True

class UserLLMConfig(UserLLMConfigInDB):
    """API response model for user LLM configuration."""
    pass 