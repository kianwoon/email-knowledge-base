import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from fastapi import HTTPException
import httpx
from sentence_transformers import SentenceTransformer
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.db.qdrant_client import get_qdrant_client

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
    """Creates an embedding for the given text using the configured embedding model."""
    # Use local SentenceTransformer to generate embeddings
    if not settings.EMBEDDING_MODEL:
        logger.error("EMBEDDING_MODEL setting is not configured in settings.")
        raise ValueError("Embedding model name is not configured.")
    logger.debug(f"Creating embedding using local model: {settings.EMBEDDING_MODEL}")
    try:
        # Run encoding in threadpool to avoid blocking, using the dense model
        if _dense_model is None:
            raise ValueError("Dense embedding model is not loaded.")
        embedding = await run_in_threadpool(_dense_model.encode, text.replace("\n", " "))
        # Convert numpy array to list if necessary
        return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
    except Exception as e:
        logger.error(f"Error creating embedding: {e}", exc_info=True)
        raise

# Renamed placeholder search_similar and implemented real search
async def search_qdrant_knowledge(
    query_embedding: List[float], 
    limit: int = 3, 
    collection_name: str = settings.QDRANT_COLLECTION_NAME, # Default collection, can be overridden
    qdrant_filter: Optional[models.Filter] = None,
    vector_name: Optional[str] = None  # Optional vector field for hybrid search
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in the specified Qdrant collection.
    Returns a list of results including payload.
    """
    qdrant_client: QdrantClient = get_qdrant_client()
    # Check collection vector dimensions to skip mismatches
    try:
        col_info = qdrant_client.get_collection(collection_name=collection_name)
        # Extract per-vector sizes: default and additional
        vec_conf = getattr(col_info, 'vectors_config', None)
        dim_map: Dict[str, int] = {}
        if vec_conf:
            # default vector size
            default_conf = getattr(vec_conf, 'default', None)
            if default_conf is not None:
                dim_map['default'] = getattr(getattr(default_conf, 'params', default_conf), 'size', None)
            # additional named vectors
            additional = getattr(vec_conf, 'additional', {}) or getattr(getattr(vec_conf, 'params', {}), 'vectors', {})
            for name, cfg in additional.items():
                dim_map[name] = getattr(getattr(cfg, 'params', cfg), 'size', None)
        # Determine the target field
        field = vector_name if vector_name else 'default'
        expected_dim = dim_map.get(field)
        # ADDED LOGGING: Check dimensions *before* deciding to skip
        query_dim = len(query_embedding)
        logger.debug(f"Checking dimensions for vector '{field}' in '{collection_name}': Expected={expected_dim}, Got={query_dim}")
        if expected_dim is not None and expected_dim != query_dim: # Use query_dim here
            logger.warning(
                f"Skipping search on vector '{field}' in '{collection_name}': "
                f"expected dim {expected_dim}, got {query_dim}"
            )
            return []
    except Exception as _:
        # If we can't fetch collection info, proceed and rely on error handling
        logger.debug(f"Could not verify vector dims for collection '{collection_name}', proceeding.")

    logger.debug(f"Attempting Qdrant search in collection '{collection_name}' with limit {limit} and filter {qdrant_filter}")
    # Build query_vector: use tuple(name, embedding) for named vectors, list for default
    query_vector = (vector_name, query_embedding) if vector_name else query_embedding
    try:
        # ADDED LOGGING: Log dimension right before the search call
        current_query_dim = len(query_vector[1]) if isinstance(query_vector, tuple) else len(query_vector)
        logger.debug(f"Executing Qdrant search with vector_name='{vector_name}', query_dim={current_query_dim}")

        # Execute vector search via Qdrant client
        search_result = qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True
        )
        # Format and return results
        formatted_results = [
            {"id": hit.id, "score": hit.score, "payload": hit.payload}
            for hit in search_result
        ]
        logger.debug(f"Qdrant search successful. Returning {len(formatted_results)} formatted results.")
        return formatted_results
    except UnexpectedResponse as e:
        # Qdrant HTTP error (e.g., bad request or missing vector_name or dimension mismatch)
        content = e.content.decode() if isinstance(e.content, (bytes, bytearray)) else str(e.content)
        logger.error(f"Qdrant search error (collection: '{collection_name}'): Status={e.status_code}, Response={content}", exc_info=True)
        # 404 = collection not found; treat as no hits
        if e.status_code == 404:
            logger.warning(f"Qdrant collection '{collection_name}' not found.")
            return []
        # 400 with 'requires specified vector name' = vector_name not supported; return no hits
        if e.status_code == 400 and 'requires specified vector name' in content:
            logger.warning(f"Qdrant collection '{collection_name}' requires vector_name; returning empty hits.")
            return []
        # 400 with dimension mismatch: skip this vector search
        if e.status_code == 400 and 'Vector dimension error' in content:
            logger.warning(f"Dimension mismatch for vector '{vector_name}' in collection '{collection_name}': {content}. Skipping this vector search.")
            return []
        # Otherwise propagate as HTTPException
        raise HTTPException(status_code=500, detail=f"Qdrant search failed unexpectedly (collection: '{collection_name}')")
    except Exception as e:
        # Use logger instead of print
        logger.error(f"Generic error during Qdrant search (collection: '{collection_name}'): {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to search knowledge base (collection: '{collection_name}'): {str(e)}")

# Define manual search helper
async def _httpx_search(
    collection_name: str,
    query_embedding: List[float],
    qdrant_filter: Optional[models.Filter],
    limit: int,
    vector_name: str
) -> List[Dict[str, Any]]:
    """Perform manual HTTP search including vector_name."""
    url = settings.QDRANT_URL.rstrip('/') + f"/collections/{collection_name}/points/search"
    headers = {}
    if settings.QDRANT_API_KEY:
        headers['api-key'] = settings.QDRANT_API_KEY
    # Build payload for HTTP search: include vector_name when provided
    payload: Dict[str, Any] = {
        'vector': query_embedding,
        'limit': limit,
        'with_payload': True
    }
    if vector_name:
        payload['vector_name'] = vector_name
    if qdrant_filter:
        # Convert Qdrant Filter model to dict for HTTP
        payload['filter'] = qdrant_filter.model_dump() if hasattr(qdrant_filter, 'model_dump') else qdrant_filter.dict()
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers)
        # Log HTTP fallback response content on non-200 status for debugging
        if resp.status_code != 200:
            try:
                error_content = resp.json()
            except Exception:
                error_content = resp.text
            logger.error(f"HTTP fallback search failed with status {resp.status_code}, response: {error_content}")
        resp.raise_for_status()
        data = resp.json()
        result_slice = data.get('result', [])
        return [
            {'id': hit['id'], 'score': hit['score'], 'payload': hit.get('payload', {})}
            for hit in result_slice
        ]

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

# Placeholder for sparse search function
async def search_qdrant_knowledge_sparse(
    query_text: str,
    limit: int = 3,
    collection_name: str = settings.QDRANT_COLLECTION_NAME,
    qdrant_filter: Optional[models.Filter] = None,
    vector_name: str = "bm25" # Default to bm25, but could be configurable
) -> List[Dict[str, Any]]:
    """
    Search using a sparse vector index (e.g., BM25) in Qdrant using the query text.
    Uses a simplified approach: tokenizes query with dense model's tokenizer,
    uses unique token IDs as indices, and assigns uniform value 1.0.
    This is NOT true BM25 ranking but attempts to leverage the sparse index.
    Returns a list of results including payload.
    """
    qdrant_client: QdrantClient = get_qdrant_client()
    logger.debug(f"Attempting Qdrant SPARSE search ({vector_name}) in collection '{collection_name}' with limit {limit} and filter {qdrant_filter} for query: '{query_text[:50]}...'")

    sparse_query_vector = None
    try:
        if _dense_model and hasattr(_dense_model, 'tokenizer'):
            # Use the tokenizer from the loaded dense model
            tokenizer = _dense_model.tokenizer
            # Encode the query to get token IDs
            # Use add_special_tokens=False to avoid [CLS], [SEP] if they aren't part of the BM25 index
            token_ids = tokenizer.encode(query_text, add_special_tokens=False)
            
            # Use unique token IDs as indices and assign a value of 1.0 to each
            unique_indices = sorted(list(set(token_ids)))
            values = [1.0] * len(unique_indices)
            
            if not unique_indices:
                 logger.warning(f"Simplified sparse search: Query '{query_text[:50]}...' produced no unique tokens. Returning empty list.")
                 return []

            sparse_query_vector = models.SparseVector(indices=unique_indices, values=values)
            logger.debug(f"Simplified sparse search: Created SparseVector with {len(unique_indices)} unique indices from query.")
        else:
            logger.warning("Simplified sparse search: Dense model or its tokenizer not available. Cannot create sparse query vector. Returning empty list.")
            return []
            
    except Exception as e:
        logger.error(f"Simplified sparse search: Error during tokenization or sparse vector creation: {e}", exc_info=True)
        return [] # Return empty on error during vector creation

    # Proceed with search if sparse_query_vector was created
    if sparse_query_vector:
        try:
            # Execute sparse vector search via Qdrant client
            # Ensure the query_vector is correctly structured for sparse search
            search_result = qdrant_client.search(
                collection_name=collection_name,
                query_vector=models.NamedSparseVector(name=vector_name, vector=sparse_query_vector), # Use NamedSparseVector
                query_filter=qdrant_filter,
                limit=limit,
                with_payload=True
            )
            formatted_results = [
                {"id": hit.id, "score": hit.score, "payload": hit.payload}
                for hit in search_result
            ]
            logger.debug(f"Qdrant sparse search ({vector_name}) successful. Returning {len(formatted_results)} formatted results.")
            return formatted_results
        except UnexpectedResponse as e:
            content = e.content.decode() if isinstance(e.content, (bytes, bytearray)) else str(e.content)
            logger.error(f"Qdrant sparse search error (collection: '{collection_name}', vector: '{vector_name}'): Status={e.status_code}, Response={content}", exc_info=True)
            # Handle specific errors if needed, e.g., 404 or invalid input
            if e.status_code == 404:
                 logger.warning(f"Qdrant collection '{collection_name}' not found during sparse search.")
            elif e.status_code == 400 and 'vector name not found' in content.lower():
                 logger.warning(f"Sparse vector index '{vector_name}' not found in collection '{collection_name}'.")
            # Return empty on error
            return [] 
        except Exception as e:
            logger.error(f"Generic error during Qdrant sparse search (collection: '{collection_name}', vector: '{vector_name}'): {str(e)}", exc_info=True)
            return [] # Return empty on generic error
    else:
        # This case should theoretically be caught earlier, but as a fallback
        logger.error("Simplified sparse search: sparse_query_vector is None, cannot proceed with search.")
        return []
