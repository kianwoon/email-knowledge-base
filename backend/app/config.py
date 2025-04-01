import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Application settings
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    
    # Determine if we're running on Koyeb
    IS_KOYEB: bool = os.getenv("K_SERVICE", "") != ""
    
    # URLs based on environment
    BACKEND_URL: str = "https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api" if IS_KOYEB else "http://localhost:8000/api"
    FRONTEND_URL: str = "https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app" if IS_KOYEB else "http://localhost:5173"
    
    # Microsoft OAuth2 settings
    MS_CLIENT_ID: str = "a4b11a39-ee9e-42b6-ab30-788ccef14d89"
    MS_CLIENT_SECRET: str = os.getenv("MS_CLIENT_SECRET", "")  # Keep this from env for security
    MS_TENANT_ID: str = "fda15b03-7d0b-4604-b6a0-00a0712abcf5"
    MS_REDIRECT_URI: str = f"{BACKEND_URL}/auth/callback"
    MS_AUTHORITY: str = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
    MS_SCOPE: list = ["User.Read", "Mail.Read", "offline_access"]
    
    # JWT settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")  # Keep this from env for security
    JWT_ALGORITHM: str = "HS256"
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
    EMBEDDING_DIMENSION: int = 1536
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

settings = Settings()
