import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Application settings
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # Microsoft OAuth2 settings
    MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID", "")
    MS_CLIENT_SECRET: str = os.getenv("MS_CLIENT_SECRET", "")
    MS_REDIRECT_URI: str = os.getenv("MS_REDIRECT_URI", f"{BACKEND_URL}/auth/callback")
    MS_AUTHORITY: str = "https://login.microsoftonline.com/common"
    MS_SCOPE: list = ["Mail.Read", "Mail.ReadWrite", "offline_access"]
    
    # JWT settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION: int = int(os.getenv("JWT_EXPIRATION", "86400"))
    
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
    EMBEDDING_DIMENSION: int = 1536  # For text-embedding-3-small
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

settings = Settings()
