import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List, Optional
from pydantic import field_validator, computed_field
import logging

# Get logger instance
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
logger.info(" --- config.py: load_dotenv() executed --- ")

class Settings(BaseSettings):
    # --- Helper validator for required fields ---
    @field_validator('*', mode='before')
    @classmethod
    def check_required_env_vars(cls, v, info):
        field = info.field_name
        # Skip optional fields and computed fields for this check
        field_info = cls.model_fields.get(field)
        if not field_info or field_info.is_required() is False or field_info.annotation == Optional[str]:
            return v
            
        # Check if the value comes from os.getenv and is None or empty string
        env_var_value = os.getenv(field)
        if env_var_value is None:
            raise ValueError(f"Environment variable '{field}' is not set.")
        if isinstance(field_info.annotation, type) and issubclass(field_info.annotation, str) and not env_var_value:
            raise ValueError(f"Environment variable '{field}' cannot be empty.")
        return env_var_value # Return the fetched value

    # Application settings
    DEBUG: bool = os.getenv("DEBUG") == "True"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT") # validated by check_required_env_vars
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper() # Added Log Level Setting

    @computed_field
    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT == "production"

    # API prefix - Environment-aware
    API_PREFIX_DEV: str = "/api/v1"  # Development prefix
    API_PREFIX_PROD: str = "/v1"     # Production prefix

    @computed_field
    @property
    def API_PREFIX(self) -> str:
        return self.API_PREFIX_PROD if self.IS_PRODUCTION else self.API_PREFIX_DEV

    # URLs - Must be provided via environment
    BACKEND_URL: str = os.getenv("BACKEND_URL") # validated by check_required_env_vars
    FRONTEND_URL: str = os.getenv("FRONTEND_URL") # validated by check_required_env_vars

    # Microsoft OAuth2 settings
    MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID") # validated by check_required_env_vars
    MS_CLIENT_SECRET: str = os.getenv("MS_CLIENT_SECRET") # validated by check_required_env_vars
    MS_TENANT_ID: str = os.getenv("MS_TENANT_ID") # validated by check_required_env_vars
    MS_REDIRECT_URI: str = os.getenv("MS_REDIRECT_URI") # validated by check_required_env_vars
    MS_AUTH_BASE_URL: str = os.getenv("MS_AUTH_BASE_URL") # validated by check_required_env_vars
    MS_SCOPE_STR: str = os.getenv("MS_SCOPE") # Renamed & validated by check_required_env_vars

    # Microsoft Graph API Settings
    MS_GRAPH_BASE_URL: str = os.getenv("MS_GRAPH_BASE_URL") # validated by check_required_env_vars

    @computed_field
    @property
    def MS_AUTHORITY(self) -> str:
        if not self.MS_AUTH_BASE_URL:
             raise ValueError("Cannot compute MS_AUTHORITY: MS_AUTH_BASE_URL not set")
        # If using common endpoint, authority is just the base URL
        if self.MS_AUTH_BASE_URL.endswith('/common'):
            return self.MS_AUTH_BASE_URL
        # Otherwise, for specific tenant, append the tenant ID
        if not self.MS_TENANT_ID:
             raise ValueError("Cannot compute MS_AUTHORITY: MS_TENANT_ID not set for non-common endpoint")
        return f"{self.MS_AUTH_BASE_URL}/{self.MS_TENANT_ID}"

    @computed_field
    @property
    def MS_SCOPE(self) -> List[str]:
        if not self.MS_SCOPE_STR:
             raise ValueError("Cannot compute MS_SCOPE: MS_SCOPE environment variable not set or empty")
        return self.MS_SCOPE_STR.split()

    # JWT settings
    JWT_SECRET: str = os.getenv("JWT_SECRET") # validated by check_required_env_vars
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM") # validated by check_required_env_vars
    JWT_EXPIRATION: int = int(os.getenv("JWT_EXPIRATION")) # validated by pydantic & check_required

    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY") # validated by check_required_env_vars
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL") # validated by check_required_env_vars
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION")) # validated by pydantic & check_required

    # Per-field embedding configuration
    DENSE_EMBEDDING_MODEL: str = os.getenv("DENSE_EMBEDDING_MODEL", EMBEDDING_MODEL)
    DENSE_EMBEDDING_DIMENSION: int = int(os.getenv("DENSE_EMBEDDING_DIMENSION", str(EMBEDDING_DIMENSION)))
    COLBERT_EMBEDDING_MODEL: str = os.getenv("COLBERT_EMBEDDING_MODEL", "colbert-ir/colbertv2.0")
    COLBERT_EMBEDDING_DIMENSION: int = int(os.getenv("COLBERT_EMBEDDING_DIMENSION", "512"))
    BM25_EMBEDDING_MODEL: str = os.getenv("BM25_EMBEDDING_MODEL", "Qdrant/bm25")
    BM25_EMBEDDING_DIMENSION: int = int(os.getenv("BM25_EMBEDDING_DIMENSION", "188"))

    # HuggingFace reranker settings
    HUGGINGFACE_API_TOKEN: Optional[str] = os.getenv("HUGGINGFACE_API_TOKEN")  # Token for HuggingFace inference
    ENABLE_RERANK: bool = os.getenv("ENABLE_RERANK", "True") == "True"  # Feature-flag for reranking
    # Weight (0-1) to blend Qdrant native score and cosine similarity for reranking
    RERANK_WEIGHT: float = float(os.getenv("RERANK_WEIGHT", "0.5"))
    # Query expansion using LLM to include synonyms
    ENABLE_QUERY_EXPANSION: bool = os.getenv("ENABLE_QUERY_EXPANSION", "False") == "True"
    # MMR diversification settings
    ENABLE_MMR: bool = os.getenv("ENABLE_MMR", "False") == "True"
    # Lambda for MMR score blending (0-1)
    MMR_LAMBDA: float = float(os.getenv("MMR_LAMBDA", "0.5"))
    # Number of documents to select after MMR
    MMR_TOP_K: int = int(os.getenv("MMR_TOP_K", "5"))
    # Maximum number of Qdrant hits to retrieve (configurable RAG search limit)
    RAG_SEARCH_LIMIT: int = int(os.getenv("RAG_SEARCH_LIMIT", "10"))

    # Qdrant settings
    QDRANT_URL: str = os.getenv("QDRANT_URL") # validated by check_required_env_vars
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY") # Optional, not validated by helper
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME") # validated by check_required_env_vars
    QDRANT_RAW_COLLECTION_NAME: str = "email_knowledge"
    # --- ADDED Qdrant Vector Params ---
    QDRANT_VECTOR_SIZE: int = 768  # Updated default to match BAAI/bge-base-en-v1.5 embedding dims
    QDRANT_DISTANCE_METRIC: str = "Cosine" # Default for OpenAI embeddings
    # --- END ADDED ---

    # Email processing settings
    MAX_PREVIEW_EMAILS: int = int(os.getenv("MAX_PREVIEW_EMAILS")) # validated by pydantic & check_required
    OPENAI_MODEL_NAME: str = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

    # --- AWS Settings --- ADDED
    APP_AWS_ACCESS_KEY_ID: str = os.getenv("APP_AWS_ACCESS_KEY_ID") # validated by check_required_env_vars
    APP_AWS_SECRET_ACCESS_KEY: str = os.getenv("APP_AWS_SECRET_ACCESS_KEY") # validated by check_required_env_vars
    AWS_REGION: str = os.getenv("AWS_REGION") # validated by check_required_env_vars
    # --- End AWS Settings --- 

    # External Analysis Service URL
    EXTERNAL_ANALYSIS_URL: str = os.getenv("EXTERNAL_ANALYSIS_URL") # validated by check_required_env_vars
    EXTERNAL_ANALYSIS_API_KEY: str = os.getenv("EXTERNAL_ANALYSIS_API_KEY") # validated by check_required_env_vars

    # CORS Settings
    CORS_ALLOWED_ORIGINS_STR: str = os.getenv("CORS_ALLOWED_ORIGINS") # validated by check_required_env_vars

    @computed_field
    @property
    def CORS_ALLOWED_ORIGINS(self) -> List[str]:
         if not self.CORS_ALLOWED_ORIGINS_STR:
              raise ValueError("Cannot compute CORS_ALLOWED_ORIGINS: CORS_ALLOWED_ORIGINS environment variable not set or empty")
         # Split by comma and remove any leading/trailing whitespace from each origin
         return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS_STR.split(',')]

    # Routing Settings
    WEBHOOK_PREFIX: str = os.getenv("WEBHOOK_PREFIX") # validated by check_required_env_vars
    EXTERNAL_WEBHOOK_BASE_URL: str = os.getenv("EXTERNAL_WEBHOOK_BASE_URL") # validated by check_required_env_vars

    # Security Settings
    ALLOWED_REDIRECT_DOMAINS_STR: str = os.getenv("ALLOWED_REDIRECT_DOMAINS") # validated by check_required_env_vars

    @computed_field
    @property
    def ALLOWED_REDIRECT_DOMAINS(self) -> List[str]:
        if not self.ALLOWED_REDIRECT_DOMAINS_STR:
            raise ValueError("Cannot compute ALLOWED_REDIRECT_DOMAINS: ALLOWED_REDIRECT_DOMAINS environment variable not set or empty")
        # Split by comma and remove any leading/trailing whitespace
        return [domain.strip() for domain in self.ALLOWED_REDIRECT_DOMAINS_STR.split(',')]

    # Token Encryption Key (Added for Step 0.4.1)
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY") # validated by check_required_env_vars

    # Development Server Settings
    DEV_SERVER_HOST: str = os.getenv("DEV_SERVER_HOST", "0.0.0.0") # Optional with default
    DEV_SERVER_PORT: int = int(os.getenv("DEV_SERVER_PORT", "8000")) # Optional with default
    DEV_SERVER_RELOAD: bool = os.getenv("DEV_SERVER_RELOAD", "True") == "True" # Optional with default

    # --- Database Settings --- 
    # PostgreSQL/SQLAlchemy Database URI
    SQLALCHEMY_DATABASE_URI: str = os.getenv("SQLALCHEMY_DATABASE_URI") # validated by check_required_env_vars

    # --- Celery Settings --- 
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL") # Added Celery Broker URL
    # Optional: Add CELERY_RESULT_BACKEND if you use results
    CELERY_RESULT_BACKEND: Optional[str] = os.getenv("CELERY_RESULT_BACKEND") # Uncommented and made Optional

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "allow"  # Allow extra environment variables
    }

settings = Settings()

# Clean up old validator definitions if they exist
if hasattr(Settings, 'validate_client_secret'): delattr(Settings, 'validate_client_secret')
if hasattr(Settings, 'validate_jwt_secret'): delattr(Settings, 'validate_jwt_secret')
if hasattr(Settings, 'validate_external_api_key'): delattr(Settings, 'validate_external_api_key')
if hasattr(Settings, 'validate_external_analysis_url'): delattr(Settings, 'validate_external_analysis_url')

# Example usage and check (Updated)
if __name__ == "__main__":
    try:
        print("Settings loaded successfully:")
        print(settings.model_dump_json(indent=2))
    except ValueError as e:
        print(f"Error loading settings: {e}")
        print("Please ensure all required environment variables are set in your .env file.")
        # Determine required fields dynamically from the model
        required_fields = [
            name for name, field_info in Settings.model_fields.items()
            if field_info.is_required() and name not in ('MS_AUTHORITY', 'MS_SCOPE', 'CORS_ALLOWED_ORIGINS', 'IS_PRODUCTION') # Exclude computed fields
        ]
        print(f"Required environment variables: {required_fields}")
