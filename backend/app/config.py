import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List
from pydantic import validator
import logging

# Get logger instance
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
logger.info(" --- config.py: load_dotenv() executed --- ")

class Settings(BaseSettings):
    # Application settings
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    
    # Determine if we're in production
    IS_PRODUCTION: bool = os.getenv("ENVIRONMENT", "") == "production"
    
    # API prefix - empty in production since Koyeb adds it
    API_PREFIX: str = os.getenv("API_PREFIX", "" if IS_PRODUCTION else "/api")
    
    # URLs based on environment
    DEFAULT_PROD_URL: str = os.getenv("DEFAULT_PROD_URL", "https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app")
    DEFAULT_DEV_BACKEND_PORT: str = os.getenv("DEFAULT_DEV_BACKEND_PORT", "8000")
    DEFAULT_DEV_FRONTEND_PORT: str = os.getenv("DEFAULT_DEV_FRONTEND_PORT", "5173")
    
    BACKEND_URL: str = os.getenv("BACKEND_URL", f"{DEFAULT_PROD_URL}" if IS_PRODUCTION else f"http://localhost:{DEFAULT_DEV_BACKEND_PORT}")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", f"{DEFAULT_PROD_URL}" if IS_PRODUCTION else f"http://localhost:{DEFAULT_DEV_FRONTEND_PORT}")
    
    # Microsoft OAuth2 settings
    MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID", "")
    MS_CLIENT_SECRET: str = os.getenv("MS_CLIENT_SECRET", "")
    MS_TENANT_ID: str = os.getenv("MS_TENANT_ID", "")
    MS_REDIRECT_URI: str = os.getenv("MS_REDIRECT_URI", f"{BACKEND_URL}/api/auth/callback")
    MS_AUTH_BASE_URL: str = os.getenv("MS_AUTH_BASE_URL", "https://login.microsoftonline.com")
    
    @property
    def MS_AUTHORITY(self) -> str:
        return f"{self.MS_AUTH_BASE_URL}/{self.MS_TENANT_ID}"
    
    # Microsoft scopes from environment or default list
    MS_SCOPE: List[str] = os.getenv("MS_SCOPE", "User.Read Mail.Read offline_access").split()
    
    @validator("MS_CLIENT_SECRET")
    def validate_client_secret(cls, v):
        if not v:
            raise ValueError("MS_CLIENT_SECRET must be set in .env file")
        return v
    
    # JWT settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION: int = int(os.getenv("JWT_EXPIRATION", "3600"))
    
    @validator("JWT_SECRET")
    def validate_jwt_secret(cls, v):
        if not v:
            raise ValueError("JWT_SECRET must be set in .env file")
        return v
    
    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Qdrant settings
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "email_knowledge")
    
    # Email processing settings
    MAX_PREVIEW_EMAILS: int = int(os.getenv("MAX_PREVIEW_EMAILS", "10"))
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
    
    # --- Debug log for external API key --- 
    _external_api_key_debug = os.getenv("EXTERNAL_ANALYSIS_API_KEY")
    logger.info(f" --- config.py: Value of os.getenv('EXTERNAL_ANALYSIS_API_KEY') = {_external_api_key_debug} --- ")
    EXTERNAL_ANALYSIS_API_KEY: str = _external_api_key_debug or ""
    # --- End Debug log ---
    
    @validator("EXTERNAL_ANALYSIS_API_KEY")
    def validate_external_api_key(cls, v):
        if not v:
            raise ValueError("EXTERNAL_ANALYSIS_API_KEY must be set in .env file or environment")
        return v
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "allow"  # Allow extra environment variables
    }

settings = Settings()
