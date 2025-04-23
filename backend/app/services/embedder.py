import logging
from typing import List, Dict, Any, Optional
# Remove Qdrant imports
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.exceptions import UnexpectedResponse
# Import Milvus client
from pymilvus import MilvusClient
from fastapi import HTTPException
import httpx # Keep for now, maybe remove _httpx_search later
from sentence_transformers import SentenceTransformer
from fastapi.concurrency import run_in_threadpool

from app.config import settings
# Import Milvus client getter
from app.db.milvus_client import get_milvus_client

# Set up logging
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

# Initialize retrieval models per vector field
try:
    _dense_model = SentenceTransformer(settings.DENSE_EMBEDDING_MODEL)
except Exception as e:
    logger.warning(f"Failed to load dense embedding model '{settings.DENSE_EMBEDDING_MODEL}': {e}")
    _dense_model = None
try:
    _colbert_model = SentenceTransformer(settings.COLBERT_EMBEDDING_MODEL)
except Exception as e:
    logger.warning(f"Failed to load colbert embedding model '{settings.COLBERT_EMBEDDING_MODEL}': {e}")
    _colbert_model = None

# Modify to accept an optional client
async def create_embedding(text: str, client: Optional[Any] = None) -> List[float]:
    """Creates an embedding for the given text using the configured dense embedding model."""
    if not settings.DENSE_EMBEDDING_MODEL:
        logger.error("DENSE_EMBEDDING_MODEL setting is not configured in settings.")
        raise ValueError("Dense embedding model name is not configured.")
    logger.debug(f"Creating embedding using local model: {settings.DENSE_EMBEDDING_MODEL}")
    try:
        if _dense_model is None:
            raise ValueError("Dense embedding model is not loaded.")
        embedding = await run_in_threadpool(_dense_model.encode, text.replace("\n", " "))
        return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
    except Exception as e:
        logger.error(f"Error creating embedding: {e}", exc_info=True)
        raise

# Renamed and refactored for Milvus
async def search_milvus_knowledge(
    query_embedding: List[float],
    limit: int = 3,
    collection_name: str = settings.MILVUS_DEFAULT_COLLECTION, # Use Milvus default collection
    filter_expression: Optional[str] = None, # Expect Milvus filter string
    # vector_name parameter removed as we use a single vector field
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in the specified Milvus collection.
    Returns a list of results including payload.
    """
    milvus_client: MilvusClient = get_milvus_client()
    
    # Removed Qdrant-specific dimension check logic

    logger.debug(f"Attempting Milvus search in collection '{collection_name}' with limit {limit} and filter: '{filter_expression}'")

    # Define search parameters (example, adjust as needed)
    search_params = {
        "metric_type": "COSINE", 
        "params": {"nprobe": 10} 
    }

    try:
        # Execute vector search via Milvus client
        search_result = milvus_client.search(
            collection_name=collection_name,
            data=[query_embedding],       # List of query vectors
            anns_field="vector",        # Vector field name in schema
            param=search_params,        # Search parameters
            limit=limit,
            filter=filter_expression,   # Milvus filter expression string
            output_fields=["pk", "metadata_json"] # Retrieve PK and the JSON metadata blob
        )
        
        # Format and return results
        formatted_results = []
        if search_result:
            hits = search_result[0] # Results for the first query
            for hit in hits:
                 # Ensure entity and metadata_json exist before accessing
                metadata = hit.entity.get('metadata_json', {}) if hit.entity else {}
                formatted_results.append({
                    "id": hit.id,        # Primary Key (pk)
                    "score": hit.distance, # Score/Distance
                    "payload": metadata  # The full metadata blob
                })

        logger.debug(f"Milvus search successful. Returning {len(formatted_results)} formatted results.")
        return formatted_results
    
    except Exception as e:
        # Handle Milvus exceptions (e.g., collection not found, invalid filter)
        logger.error(f"Milvus search error (collection: '{collection_name}'): {str(e)}", exc_info=True)
        if "collection not found" in str(e).lower() or "doesn't exist" in str(e).lower():
            logger.warning(f"Milvus collection '{collection_name}' not found during search.")
            return [] # Return empty list if collection doesn't exist
        # You might want to check for other specific Milvus errors here
        # For now, raise a generic HTTPException for other errors
        raise HTTPException(status_code=500, detail=f"Milvus search failed unexpectedly (collection: '{collection_name}'): {str(e)}")

# Removed search_qdrant_knowledge_sparse function
# Removed _httpx_search function

# create_retrieval_embedding function remains the same as it doesn't interact with the vector DB client
async def create_retrieval_embedding(text: str, field: str) -> List[float]:
    """
    Generate an embedding for 'text' using the specified vector field's model.
    Supported fields: 'dense', 'colbertv2.0'. REMOVED 'bm25'.
    """
    normalized = text.replace("\n", " ")
    # Select the appropriate model
    if field == "dense":
        if _dense_model is None:
            raise ValueError("Dense embedding model is not loaded.")
        model = _dense_model
    elif field == "colbertv2.0":
        if _colbert_model is None:
            raise NotImplementedError("ColBERT embedding model is not loaded.")
        model = _colbert_model
    else:
        raise ValueError(f"Unsupported vector field for embedding generation: {field}")
    # Generate embedding, skip non-critical failures for hybrid branches
    try:
        embedding = await run_in_threadpool(model.encode, normalized)
    except Exception as e:
        logger.error(f"{field} embedding failed: {e}", exc_info=True)
        if field == "dense":
            # Dense is critical
            raise
        # Skip this branch
        raise NotImplementedError(f"{field} embedding failed.")
    # Convert to list if necessary
    vector = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
    # Ensure colbertv2.0 embeddings match the expected dim (truncate or pad)
    if field == "colbertv2.0":
        dim = 128 # Use fixed dimension 128 to match collection schema
        original_dim = len(vector) # Log original dim
        if len(vector) >= dim:
            final_vector = vector[:dim]
        else:
            final_vector = vector + [0.0] * (dim - len(vector))
        # ADDED LOGGING: Log dimensions before returning for Colbert
        logger.debug(f"ColBERT vector resized from {original_dim} to {len(final_vector)} dimensions.")
        return final_vector # Return the resized vector
    return vector
