import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Application settings
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # Microsoft OAuth2 settings
    MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID", "")
    MS_CLIENT_SECRET: str = os.getenv("MS_CLIENT_SECRET", "")
    MS_TENANT_ID: str = os.getenv("MS_TENANT_ID", "")
    # Fix: Use the provided MS_REDIRECT_URI directly instead of constructing it from BACKEND_URL
    MS_REDIRECT_URI: str = os.getenv("MS_REDIRECT_URI", "http://localhost:8000/auth/callback")
    MS_AUTHORITY: str = f"https://login.microsoftonline.com/{os.getenv('MS_TENANT_ID', '')}"
    MS_SCOPE: list = ["User.Read", "Mail.Read", "offline_access"]
    
    # JWT settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    # Hardcoded JWT expiration to 24 hours (86400 seconds)
    JWT_EXPIRATION: int = 86400
    
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
