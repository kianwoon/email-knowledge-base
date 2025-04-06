from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from app.config import settings
import logging
from fastapi import HTTPException

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
    """Checks if the collection exists and creates it if not. Handles potential client-side parsing errors gracefully."""
    collection_name = settings.QDRANT_COLLECTION_NAME
    vector_size = settings.EMBEDDING_DIMENSION
    distance_metric = models.Distance.COSINE

    logger.info(f"[ensure_collection_exists] Starting check for collection '{collection_name}'...")
    try:
        logger.info(f"[ensure_collection_exists] Attempting client.get_collection('{collection_name}')...")
        collection_info = client.get_collection(collection_name=collection_name)
        logger.info(f"[ensure_collection_exists] SUCCESS: Collection '{collection_name}' confirmed via API call.")
        
        # Optional: Log vector parameter mismatch as a warning, but don't delete/recreate.
        # This part might still raise ResponseHandlingException if parsing fails here,
        # but we handle that below.
        try:
             if hasattr(collection_info, 'vectors_config') and collection_info.vectors_config:
                  current_params = collection_info.vectors_config.params # qdrant > v1.1
                  if current_params.size != vector_size or current_params.distance != distance_metric:
                      logger.warning(f"Collection '{collection_name}' exists but vector parameters mismatch! Expected: size={vector_size}, distance={distance_metric}. Found: size={current_params.size}, distance={current_params.distance}.")
             elif hasattr(collection_info, 'vector_params') and collection_info.vector_params: # older qdrant client versions
                 current_params = collection_info.vector_params
                 if current_params.size != vector_size or current_params.distance != distance_metric:
                      logger.warning(f"Collection '{collection_name}' exists but vector parameters mismatch! Expected: size={vector_size}, distance={distance_metric}. Found: size={current_params.size}, distance={current_params.distance}.")
             else:
                 logger.warning(f"Could not verify vector parameters for collection '{collection_name}' due to unexpected response structure.")
        except Exception as parse_warn:
              logger.warning(f"Could not fully parse existing collection info for '{collection_name}', but assuming it exists. Parse error: {parse_warn}")

        logger.info(f"[ensure_collection_exists] Check complete. Collection exists.")
        return # Collection exists, nothing more to do

    except (ResponseHandlingException, UnexpectedResponse) as e:
        status_code = getattr(getattr(e, 'response', None), 'status_code', None)
        logger.warning(f"[ensure_collection_exists] Client-side ResponseHandling/Unexpected exception (Status: {status_code}): {e}")
        if status_code is not None and status_code != 404:
            logger.warning(f"[ensure_collection_exists] Assuming collection exists despite parsing error (Status was not 404). Proceeding cautiously.")
            return # Assume exists
        else:
            logger.warning(f"[ensure_collection_exists] Client-side exception might indicate non-existence (Status: {status_code}). Falling through to general check...")
            # Fall through to general Exception block to handle 404 specifically
            pass 

    except Exception as e:
         # Catch other exceptions, including potential 404s
         logger.warning(f"[ensure_collection_exists] General exception caught during get_collection: {type(e).__name__} - {e}")
         status_code = getattr(getattr(e, 'response', None), 'status_code', None) 
         is_not_found = False
         if status_code == 404:
             is_not_found = True
             logger.info(f"[ensure_collection_exists] Detected 404 status code in exception.")
         elif isinstance(e, UnexpectedResponse) and e.status_code == 404:
              is_not_found = True
              logger.info(f"[ensure_collection_exists] Detected 404 status code in UnexpectedResponse.")
         elif "not found" in str(e).lower() or "status_code=404" in str(e).lower():
              is_not_found = True
              logger.info(f"[ensure_collection_exists] Detected 'not found' or 'status_code=404' in error string.")

         if is_not_found:
             logger.info(f"[ensure_collection_exists] Confirmed collection '{collection_name}' does not exist. Attempting creation...")
             try:
                 client.create_collection(
                     collection_name=collection_name,
                     vectors_config=models.VectorParams(size=vector_size, distance=distance_metric)
                 )
                 logger.info(f"[ensure_collection_exists] SUCCESS: Created collection '{collection_name}'.")
                 return # Collection created successfully
             except Exception as create_err:
                 logger.error(f"[ensure_collection_exists] FAILED to create collection '{collection_name}': {create_err}", exc_info=True)
                 raise create_err # Re-raise the creation error
         else:
             # Log other errors (network, auth, etc.)
             logger.error(f"[ensure_collection_exists] FAILED: Error checking collection '{collection_name}' was not a 404: {e}. Cannot confirm status.", exc_info=True)
             raise HTTPException(status_code=503, detail=f"Could not verify status of Qdrant collection '{collection_name}'")
    
    logger.info(f"[ensure_collection_exists] Check finished for '{collection_name}'.")

# --- Initialize client and ensure collection on module load? Or on app startup? ---
# Option 1: Initialize on module load (simpler for now)
# qdrant_db_client = get_qdrant_client()
# ensure_collection_exists(qdrant_db_client)

# Option 2: Use dependency injection or app startup event (more robust)
# We will use dependency injection approach in the route file. 