from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from app.config import settings
import logging

logger = logging.getLogger(__name__)

def get_qdrant_client() -> QdrantClient:
    """Initializes and returns a Qdrant client based on settings."""
    logger.info(f"Initializing Qdrant client for URL: {settings.QDRANT_URL}")
    client = QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY, # Will be None if not set, which is handled by the client
        # prefer_grpc=True, # Optional: Can be faster for large data transfers
    )
    logger.info("Qdrant client initialized.")
    return client

def ensure_collection_exists(client: QdrantClient):
    """Checks if the collection exists and creates it if not."""
    collection_name = settings.QDRANT_COLLECTION_NAME
    vector_size = settings.EMBEDDING_DIMENSION
    distance_metric = models.Distance.COSINE # As per documentation

    logger.info(f"Ensuring collection '{collection_name}' exists...")
    try:
        collection_info = client.get_collection(collection_name=collection_name)
        logger.info(f"Collection '{collection_name}' already exists.")
        # Optional: Check if vector params match and potentially recreate/update
        current_params = collection_info.vectors_config.params
        if current_params.size != vector_size or current_params.distance != distance_metric:
            logger.warning(f"Collection '{collection_name}' exists but has different vector parameters! Expected: size={vector_size}, distance={distance_metric}. Found: size={current_params.size}, distance={current_params.distance}.")
            # Decide on update/recreation strategy if needed - for now, just log warning.

    except Exception as e:
        # Handle case where collection does not exist (specific error varies by Qdrant version/client usage)
        # A simple approach is to try creating it if get_collection fails
        logger.info(f"Collection '{collection_name}' not found or error checking existence: {e}. Attempting to create...")
        try:
            client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=distance_metric)
            )
            logger.info(f"Successfully created collection '{collection_name}' with size={vector_size}, distance={distance_metric}.")
        except Exception as create_err:
            logger.error(f"Failed to create collection '{collection_name}': {create_err}", exc_info=True)
            raise # Re-raise the creation error to halt startup if needed

# --- Initialize client and ensure collection on module load? Or on app startup? ---
# Option 1: Initialize on module load (simpler for now)
# qdrant_db_client = get_qdrant_client()
# ensure_collection_exists(qdrant_db_client)

# Option 2: Use dependency injection or app startup event (more robust)
# We will use dependency injection approach in the route file. 