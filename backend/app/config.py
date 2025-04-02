import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List
from pydantic import validator

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Application settings
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    
    # Determine if we're in production
    IS_PRODUCTION: bool = os.getenv("ENVIRONMENT", "") == "production"
    
    # URLs based on environment
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # Microsoft OAuth2 settings
    MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID", "")
    MS_CLIENT_SECRET: str = os.getenv("MS_CLIENT_SECRET", "")  # Keep this from env for security
    MS_TENANT_ID: str = os.getenv("MS_TENANT_ID", "")
    MS_REDIRECT_URI: str = os.getenv("MS_REDIRECT_URI", "http://localhost:8000/auth/callback")
    
    @property
    def MS_AUTHORITY(self) -> str:
        return f"https://login.microsoftonline.com/{self.MS_TENANT_ID}"
    
    MS_SCOPE: List[str] = [
        "User.Read",  # Basic profile info
        "Mail.Read",  # Read mail
        "offline_access"  # For refresh tokens
    ]
    
    @validator("MS_CLIENT_SECRET")
    def validate_client_secret(cls, v):
        if not v:
            raise ValueError("MS_CLIENT_SECRET must be set in .env file")
        return v
    
    # JWT settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "development_secret_key")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION: int = 3600
    
    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Qdrant settings
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION_NAME: str = "email_knowledge"
    
    # Email processing settings
    MAX_PREVIEW_EMAILS: int = 10
    EMBEDDING_DIMENSION: int = 1536
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "allow"  # Allow extra environment variables
    }

settings = Settings()
