import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List, Optional
from pydantic import field_validator, computed_field, AnyHttpUrl
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
    LOG_LEVEL: str = "INFO"

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
    MS_GRAPH_TIMEOUT_SECONDS: float = float(os.getenv("MS_GRAPH_TIMEOUT_SECONDS", "120.0")) # Default 120 seconds timeout for Graph API requests

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
    JWT_COOKIE_NAME: str = "access_token" # Cookie name for JWT
    COOKIE_DOMAIN: str | None = None  # Use None to make cookie work with localhost

    # OpenAI settings (used as default if provider not specified or no specific key)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL_NAME: str = "gpt-4o"
    OPENAI_TIMEOUT_SECONDS: Optional[float] = None # Keep optional
    OPENAI_TEMPERATURE: Optional[float] = 0.1 # ADDED: Default temperature

    # --- NEW: Default Timeout Settings --- 
    DEFAULT_LLM_TIMEOUT_SECONDS: float = 30.0
    DEFAULT_DEEPSEEK_TIMEOUT_SECONDS: float = 60.0
    # --- END: Default Timeout Settings --- 

    # Provider specific timeout settings (Optional)
    DEEPSEEK_TIMEOUT_SECONDS: Optional[float] = None
    # Add others if needed, e.g., ANTHROPIC_TIMEOUT_SECONDS: Optional[float] = None

    # Embedding Model
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"

    # Per-field embedding configuration
    DENSE_EMBEDDING_MODEL: str = os.getenv("DENSE_EMBEDDING_MODEL", "BAAI/bge-m3")
    DENSE_EMBEDDING_DIMENSION: int = int(os.getenv("DENSE_EMBEDDING_DIMENSION", "1024")) # Default for bge-m3
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
    # --- New RAG Settings ---
    RAG_MILVUS_CONTEXT_LIMIT: Optional[int] = int(os.getenv("RAG_MILVUS_CONTEXT_LIMIT", "5")) # Context limit for final prompt
    RAG_EMAIL_CONTEXT_LIMIT: Optional[int] = int(os.getenv("RAG_EMAIL_CONTEXT_LIMIT", "15"))  # Limit for email context retrieval (Increased from 5)
    RAG_DENSE_RESULTS: Optional[int] = int(os.getenv("RAG_DENSE_RESULTS", "5"))        # Number of dense results to fetch
    RAG_SPARSE_RESULTS: Optional[int] = int(os.getenv("RAG_SPARSE_RESULTS", "5"))       # Number of sparse results to fetch
    ENABLE_HYDE: bool = os.getenv("ENABLE_HYDE", "True") == "True"                    # Feature flag for HyDE
    # --- Rate Card RAG Settings --- 
    RATE_CARD_RESULTS_PER_QUERY: Optional[int] = int(os.getenv("RATE_CARD_RESULTS_PER_QUERY", "3"))
    RATE_CARD_FINAL_CONTEXT_LIMIT: Optional[int] = int(os.getenv("RATE_CARD_FINAL_CONTEXT_LIMIT", "5"))

    # Composite scoring metadata filter settings
    ENABLE_METADATA_FILTER: bool = os.getenv("ENABLE_METADATA_FILTER", "False") == "True"
    METADATA_FILTER_FIELD: Optional[str] = os.getenv("METADATA_FILTER_FIELD", None)
    METADATA_FILTER_VALUE: Optional[str] = os.getenv("METADATA_FILTER_VALUE", None)

    # Composite scoring weights (must be floats)
    COMPOSITE_WEIGHT_DENSE: float = float(os.getenv("COMPOSITE_WEIGHT_DENSE") or "0.4")
    COMPOSITE_WEIGHT_SPARSE: float = float(os.getenv("COMPOSITE_WEIGHT_SPARSE") or "0.4")
    COMPOSITE_WEIGHT_META:   float = float(os.getenv("COMPOSITE_WEIGHT_META")   or "0.2")
    # Number of top results to return when composite scoring is enabled
    COMPOSITE_TOP_K:         int   = int(  os.getenv("COMPOSITE_TOP_K")         or "5")

    # --- ADDED: Feature flag for Composite Scoring --- 
    ENABLE_COMPOSITE_SCORING: bool = os.getenv("ENABLE_COMPOSITE_SCORING", "False") == "True"
    # --- END ADDED --- 

    # Milvus settings
    MILVUS_URI: str = os.getenv("MILVUS_URI") # validated by check_required_env_vars
    MILVUS_TOKEN: str = os.getenv("MILVUS_TOKEN") # validated by check_required_env_vars
    # You might need a default collection name for Milvus as well
    MILVUS_DEFAULT_COLLECTION: str = os.getenv("MILVUS_DEFAULT_COLLECTION", "default_knowledge")

    # Qdrant settings (Commented out for Milvus migration)
    # QDRANT_URL: str = os.getenv("QDRANT_URL") # validated by check_required_env_vars
    # QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY") # Optional, not validated by helper
    # QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME") # validated by check_required_env_vars
    # QDRANT_RAW_COLLECTION_NAME: str = "email_knowledge"
    # --- ADDED Qdrant Vector Params ---
    # QDRANT_VECTOR_SIZE: int = 768  # Updated default to match BAAI/bge-base-en-v1.5 embedding dims
    # QDRANT_DISTANCE_METRIC: str = "Cosine" # Default for OpenAI embeddings
    # --- END ADDED ---

    # Email processing settings
    MAX_PREVIEW_EMAILS: int = int(os.getenv("MAX_PREVIEW_EMAILS")) # validated by pydantic & check_required

    # --- AWS Settings --- ADDED
    APP_AWS_ACCESS_KEY_ID: str = os.getenv("APP_AWS_ACCESS_KEY_ID") # validated by check_required_env_vars
    APP_AWS_SECRET_ACCESS_KEY: str = os.getenv("APP_AWS_SECRET_ACCESS_KEY") # validated by check_required_env_vars
    AWS_REGION: str = os.getenv("AWS_REGION") # validated by check_required_env_vars
    # --- End AWS Settings --- 

    # --- Cloudflare R2 Settings --- ADDED
    R2_ENDPOINT_URL: str = os.getenv("R2_ENDPOINT_URL")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME")
    R2_REGION: str = os.getenv("R2_REGION", "auto") # Boto3 requires a region, use 'auto' for R2

    # --- Iceberg Catalog (REST) Settings --- ADDED for Iceberg integration
    ICEBERG_DUCKDB_CATALOG_NAME: Optional[str] = os.getenv("ICEBERG_DUCKDB_CATALOG_NAME", "r2_catalog_duckdb_llm") # Added Catalog Name
    R2_CATALOG_URI: str = os.getenv("R2_CATALOG_URI") # e.g., http://localhost:8181
    R2_CATALOG_WAREHOUSE: str = os.getenv("R2_CATALOG_WAREHOUSE") # e.g., s3://your-r2-bucket/warehouse/
    R2_CATALOG_TOKEN: Optional[str] = os.getenv("R2_CATALOG_TOKEN") # Optional auth token for REST catalog
    ICEBERG_DEFAULT_NAMESPACE: str = os.getenv("ICEBERG_DEFAULT_NAMESPACE", "default") # Default namespace
    ICEBERG_EMAIL_FACTS_TABLE: str = os.getenv("ICEBERG_EMAIL_FACTS_TABLE", "email_facts") # Name for the email facts table
    # --- ADDED: Catalog Table Name --- 
    CATALOG_TABLE_NAME: str = os.getenv("DUCKDB_CATALOG_TABLE_NAME", "email_facts_catalog")
    # --- END ADDED ---

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
    
    # Interval (in seconds) for Outlook sync dispatch (used by Celery beat)
    outlook_sync_dispatch_interval_seconds: float = float(
        os.getenv("OUTLOOK_SYNC_DISPATCH_INTERVAL_SECONDS", "300")
    )
    
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
