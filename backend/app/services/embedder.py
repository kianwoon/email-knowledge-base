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

    # Ensure structure matches MilvusClient.search requirements (anns_field inside search_params)
    search_params_for_call = {
        # "anns_field": "dense",      # REMOVED: Vector field name from params dict based on documentation parameter list
        "metric_type": "COSINE",
        "params": {"nprobe": 10}     # Index-specific parameters
    }

    try:
        # Use keyword arguments ONLY for the MilvusClient.search call
        search_kwargs = {
            "collection_name": collection_name,
            "data": [query_embedding],
            "anns_field": "dense", # ADDED as a separate top-level argument based on documentation parameter list
            "limit": limit,
            "search_params": search_params_for_call, # search_params dict no longer includes anns_field
            "output_fields": ["id", "content", "vector"] # Corrected PK to 'id' and payload to 'content' and added vector
        }

        # Conditionally add the filter using the 'filter' keyword
        if filter_expression:
            search_kwargs['filter'] = filter_expression
            logger.debug(f"Adding filter expression to search: {filter_expression}")
        else:
            logger.debug("No filter expression provided for search.")

        # Execute vector search via Milvus client using only keyword arguments
        search_result = milvus_client.search(**search_kwargs)

        # Format and return results
        formatted_results = []
        if search_result:
            hits = search_result[0] # Results for the first query
            for hit in hits:
                 # --- ADDED DEBUG LOG --- 
                 logger.debug(f"Raw Milvus search hit: {hit}")
                 # --- END DEBUG LOG ---
                 # Access results as dictionary keys, getting content from nested entity
                 hit_id = hit.get('id') 
                 score = hit.get('distance') 
                 entity_dict = hit.get('entity', {}) # Get the nested entity dict
                 payload_content = entity_dict.get('content', '') # Get content from entity dict

                 # Extract the vector if it exists from the main hit dictionary
                 vector = hit.get('vector') # Get vector from the main hit dictionary
                 if vector is None:
                     logger.warning(f"Vector not found in top-level Milvus hit for ID: {hit_id}")

                 # Handle potential missing fields gracefully 
                 if hit_id is None or score is None:
                     logger.warning(f"Skipping hit due to missing 'id' or 'distance': {hit}")
                     continue
                 
                 formatted_results.append({
                     "id": hit_id,       
                     "score": score, 
                     # Pass the extracted content string as payload
                     "payload": payload_content,
                     # Include the vector (potentially None) in the formatted result
                     "vector": vector
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

# NEW FUNCTION for Sparse Search (using simplified token ID approach)
async def search_milvus_knowledge_sparse(
    query_text: str, # Accept raw query text
    # query_sparse_vector: Dict[int, float], # REMOVE - generated internally now
    limit: int = 5,
    collection_name: str = settings.MILVUS_DEFAULT_COLLECTION, 
    filter_expression: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search using a simplified sparse vector approach based on dense model token IDs.
    NOTE: This is NOT true BM25 and unlikely to match the Milvus sparse index.
    It uses token IDs as indices and assigns a uniform value of 1.0.
    Returns a list of results including payload.
    """
    milvus_client: MilvusClient = get_milvus_client()
    
    logger.debug(f"Attempting Milvus SPARSE search (Simplified Token ID method) in collection '{collection_name}' for query: '{query_text[:50]}...'")

    # --- START: Simplified Sparse Vector Generation (from Qdrant approach) ---
    sparse_query_dict = {}
    try:
        if _dense_model and hasattr(_dense_model, 'tokenizer'):
            tokenizer = _dense_model.tokenizer
            token_ids = tokenizer.encode(query_text, add_special_tokens=False)
            unique_indices = sorted(list(set(token_ids)))
            
            if not unique_indices:
                 logger.warning(f"Simplified sparse search: Query '{query_text[:50]}...' produced no unique tokens.")
                 return [] # Return empty if no tokens

            # Use unique token IDs as indices and assign a value of 1.0 to each
            sparse_query_dict = {index: 1.0 for index in unique_indices}
            logger.debug(f"Simplified sparse search: Created SparseVector dict with {len(unique_indices)} unique indices.")
        else:
            logger.warning("Simplified sparse search: Dense model or its tokenizer not available. Cannot create sparse query vector.")
            return [] # Return empty if tokenizer missing
            
    except Exception as e:
        logger.error(f"Simplified sparse search: Error during tokenization or sparse vector creation: {e}", exc_info=True)
        return [] # Return empty on error
    # --- END: Simplified Sparse Vector Generation ---

    # Define search parameters - MIGHT NEED ADJUSTMENT FOR SPARSE
    search_params_for_call = {
        "metric_type": "IP",  # Inner Product is common for sparse
        "params": {} # Sparse indexes might not need specific params like nprobe
    }

    # Proceed only if we have a valid sparse dict
    if not sparse_query_dict:
        logger.error("Simplified sparse search: sparse_query_dict is empty, cannot proceed.")
        return []

    try:
        search_kwargs = {
            "collection_name": collection_name,
            "data": [sparse_query_dict], # Use the generated dict
            "anns_field": "sparse", # Target the sparse field
            "limit": limit,
            "search_params": search_params_for_call,
            "output_fields": ["id", "content", "vector"] # Assuming same output fields needed
        }

        if filter_expression:
            search_kwargs['filter'] = filter_expression
            logger.debug(f"Adding filter expression to SPARSE search: {filter_expression}")
        else:
            logger.debug("No filter expression provided for SPARSE search.")

        search_result = milvus_client.search(**search_kwargs)

        # Format results (same logic as dense for now)
        formatted_results = []
        if search_result:
            hits = search_result[0] 
            for hit in hits:
                logger.debug(f"Raw Milvus SPARSE search hit: {hit}") # Log raw hit
                # Access results as dictionary keys, getting content from nested entity
                hit_id = hit.get('id')
                score = hit.get('distance') 
                entity_dict = hit.get('entity', {}) # Get the nested entity dict
                payload_content = entity_dict.get('content', '') # Get content from entity dict

                # Extract vector from the main hit dictionary
                vector = hit.get('vector')
                if vector is None:
                    logger.warning(f"Vector not found in top-level Milvus SPARSE hit for ID: {hit_id}")

                if hit_id is None or score is None:
                    logger.warning(f"Skipping SPARSE hit due to missing 'id' or 'distance': {hit}")
                    continue
                formatted_results.append({
                    "id": hit_id, 
                    "score": score, 
                    # Pass the extracted content string as payload
                    "payload": payload_content,
                    # Include the vector (potentially None) in the formatted result
                    "vector": vector
                })

        logger.debug(f"Milvus SPARSE search successful. Returning {len(formatted_results)} formatted results.")
        return formatted_results
    
    except Exception as e:
        logger.error(f"Milvus SPARSE search error (collection: '{collection_name}'): {str(e)}", exc_info=True)
        # Basic error handling, similar to dense search
        if "collection not found" in str(e).lower() or "doesn't exist" in str(e).lower():
            logger.warning(f"Milvus collection '{collection_name}' not found during SPARSE search.")
            return [] 
        # Raise generic error for others
        raise HTTPException(status_code=500, detail=f"Milvus SPARSE search failed unexpectedly (collection: '{collection_name}'): {str(e)}")

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
