import logging
from typing import List, Dict, Any, Optional
# Remove Qdrant imports
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.exceptions import UnexpectedResponse
# Import Milvus client
from pymilvus import MilvusClient, Collection, utility
from fastapi import HTTPException
import httpx # Keep for now, maybe remove _httpx_search later
from sentence_transformers import SentenceTransformer, CrossEncoder
from fastapi.concurrency import run_in_threadpool
import threading # Added for locks

import re
from collections import Counter
import json
import asyncio
import copy # <-- ADD IMPORT FOR DEEPCOPY

def text_to_term_freq(text: str) -> Dict[str, int]:
    tokens = re.findall(r"\w+", text.lower())
    return dict(Counter(tokens))

from app.config import settings
# Import Milvus client getter
from app.db.milvus_client import get_milvus_client

# Set up logging
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

# --- Model Initialization (Lazy Loading) ---
# Global variables to hold loaded models, initialized to None
_reranker_model: Optional[CrossEncoder] = None
_dense_model: Optional[SentenceTransformer] = None
_colbert_model: Optional[SentenceTransformer] = None

# Locks to prevent race conditions during loading in concurrent environments
_reranker_lock = threading.Lock()
_dense_lock = threading.Lock()
_colbert_lock = threading.Lock()

RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

def _get_reranker_model() -> Optional[CrossEncoder]:
    """Lazily loads and returns the reranker model."""
    global _reranker_model
    # Double-checked locking pattern
    if _reranker_model is None:
        with _reranker_lock:
            if _reranker_model is None: # Check again inside lock
                logger.info(f"Attempting to load reranker model: {RERANKER_MODEL_NAME}...")
                try:
                    _reranker_model = CrossEncoder(RERANKER_MODEL_NAME)
                    logger.info(f"Successfully loaded reranker model: {RERANKER_MODEL_NAME}")
                except Exception as e:
                    logger.error(f"Failed to load reranker model '{RERANKER_MODEL_NAME}': {e}. Reranking will be skipped.", exc_info=True)
                    # Keep _reranker_model as None if loading failed
    return _reranker_model

def _get_dense_model() -> Optional[SentenceTransformer]:
    """Lazily loads and returns the dense embedding model."""
    global _dense_model
    if _dense_model is None:
        with _dense_lock:
            if _dense_model is None:
                model_name = settings.DENSE_EMBEDDING_MODEL
                logger.info(f"Attempting to load dense embedding model: {model_name}...")
                if not model_name:
                    logger.error("DENSE_EMBEDDING_MODEL setting is not configured.")
                    return None
                try:
                    # Note: SentenceTransformer might still print warnings/errors directly
                    _dense_model = SentenceTransformer(model_name)
                    logger.info(f"Successfully loaded dense embedding model: {model_name}")
                except Exception as e:
                    logger.error(f"Failed to load dense embedding model '{model_name}': {e}", exc_info=True)
    return _dense_model

def _get_colbert_model() -> Optional[SentenceTransformer]:
    """Lazily loads and returns the colbert embedding model."""
    global _colbert_model
    if _colbert_model is None:
        with _colbert_lock:
            if _colbert_model is None:
                model_name = settings.COLBERT_EMBEDDING_MODEL
                logger.info(f"Attempting to load colbert embedding model: {model_name}...")
                if not model_name:
                    logger.error("COLBERT_EMBEDDING_MODEL setting is not configured.")
                    return None
                try:
                    _colbert_model = SentenceTransformer(model_name)
                    logger.info(f"Successfully loaded colbert embedding model: {model_name}")
                except Exception as e:
                    logger.error(f"Failed to load colbert embedding model '{model_name}': {e}", exc_info=True)
    return _colbert_model
# --- End Model Initialization ---

# Modify to accept an optional client
async def create_embedding(text: str, client: Optional[Any] = None) -> List[float]:
    """Creates an embedding for the given text using the configured dense embedding model."""
    dense_model = _get_dense_model() # Ensure model is loaded
    if dense_model is None:
        logger.error("Dense embedding model is not available.")
        raise ValueError("Dense embedding model failed to load or is not configured.")

    logger.debug(f"Creating embedding using local model: {settings.DENSE_EMBEDDING_MODEL}")
    try:
        # Use the loaded model
        embedding = await run_in_threadpool(dense_model.encode, text.replace("\n", " "))
        return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
    except Exception as e:
        logger.error(f"Error creating embedding: {e}", exc_info=True)
        raise

# MODIFIED: Add new function for Hybrid Search
async def search_milvus_knowledge_hybrid(
    query_text: str, # Take single text query
    collection_name: str,
    dense_vector_field: str = "dense",
    # Assuming the text field for BM25 sparse search is 'content'
    sparse_text_field: str = "content",
    output_fields: List[str] = ["id", "content", "metadata"], # Don't need dense vector back necessarily
    limit: int = 10,
    # Parameters for dense search (e.g., HNSW)
    dense_params: Optional[Dict] = None,
    # Parameters for sparse search (e.g., BM25 rank parameters)
    sparse_params: Optional[Dict] = None,
    # ADDED parameter for filename filtering terms
    filename_terms: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors/text in the specified Milvus collection using HYBRID search (dense + sparse).
    Returns a fused list of results including payload.
    Assumes collection has appropriate dense and sparse (BM25) indexes.
    Performs pre-filtering based on filename terms if provided.
    """
    milvus_client: MilvusClient = get_milvus_client()

    # Pre-filter by filename terms if provided
    id_filter = None
    if filename_terms:
        try:
            logger.debug(f"[Prefilter] Filtering by filename terms: {filename_terms}")
            # Fetch IDs and metadata for filtering
            # Remove explicit filter, rely on limit and subsequent Python filtering
            meta_hits = milvus_client.query(
                collection_name=collection_name,
                # filter="id != \"\"", # REMOVED explicit filter
                output_fields=["id", "metadata"],
                limit=1000 # Keep limit, adjust if needed for performance
            )
            
            # RE-ENABLE Python filtering
            allowed_ids = []
            # Filter in Python
            for hit in meta_hits:
                # Ensure metadata is fetched and is a dictionary
                metadata = hit.get("metadata")
                if metadata and isinstance(metadata, dict):
                    original_filename = metadata.get("original_filename")
                    # Check filename exists and is a string
                    if original_filename and isinstance(original_filename, str):
                        # Check if filename contains ALL terms (case-insensitive)
                        if all(term.lower() in original_filename.lower() for term in filename_terms):
                            # Check if ID is valid before appending (basic check)
                            doc_id = hit.get("id")
                            if doc_id is not None: # Add check for None ID
                                allowed_ids.append(doc_id)
                            else:
                                logger.warning(f"[Prefilter] Hit found matching filename terms but is missing 'id': {hit}")
                                
            logger.debug(f"[Prefilter] matched IDs after Python filtering: {allowed_ids}")
            
            if not allowed_ids:
                logger.debug("No documents match filename terms filter; returning empty list.")
                return []
            
            # Ensure IDs are strings for the 'in' operator if they are not already
            # Handle potential non-string IDs robustly
            id_list_parts = []
            for i in allowed_ids:
                if isinstance(i, str):
                    # Escape quotes within the string ID itself if necessary
                    escaped_id = i.replace('"', '\\"')
                    id_list_parts.append(f'"{escaped_id}"')
                elif isinstance(i, (int, float)): # Allow numeric IDs directly
                    id_list_parts.append(str(i))
                else:
                    # Log and skip unexpected ID types
                    logger.warning(f"[Prefilter] Skipping unexpected ID type '{type(i)}' with value '{i}'")
            
            if not id_list_parts:
                 logger.warning("[Prefilter] No valid IDs remained after type checking/formatting.")
                 return [] # Return empty if no valid IDs left

            id_list = ",".join(id_list_parts)
            id_filter = f"id in [{id_list}]"
            logger.debug(f"Pre-filter ID list for subsequent vector searches: {id_filter}")
            # END RE-ENABLE
            
        except Exception as e:
            # Log error but proceed without filter to avoid breaking search entirely
            logger.error(f"Filename pre-filter failed: {e}. Proceeding without filename filter.", exc_info=True)
            id_filter = None # Ensure filter is None if pre-filtering failed

    # Use the generated id_filter (which might be None) in subsequent search calls
    # The logger message needs adjustment as filter_expr is removed.
    logger.debug(f"Attempting Milvus HYBRID search in collection '{collection_name}' for query '{query_text}' with limit {limit} and ID filter: '{id_filter}'") # Corrected log message

    # --- Dense Vector Preparation ---
    try:
        query_dense_embedding = await create_embedding(query_text)
        if hasattr(query_dense_embedding, 'tolist'):
            query_dense_vector = query_dense_embedding.tolist()
        else:
            query_dense_vector = query_dense_embedding
    except Exception as e:
        logger.error(f"Failed to create dense embedding for hybrid search: {e}", exc_info=True)
        # Cannot proceed without dense vector
        raise HTTPException(status_code=500, detail="Failed to generate query embedding for search.")

    # --- Define Search Parameters --- 
    # Default Dense Params (Example for HNSW index)
    default_dense_params = {"metric_type": "COSINE", "params": {"ef": 128}}
    final_dense_params = dense_params or default_dense_params
    
    # Default Sparse Params (Example for BM25)
    default_sparse_params = {"type": "BM25", "params": {"k1": 1.2, "b": 0.75}}
    final_sparse_params = sparse_params or default_sparse_params

    # --- Construct Hybrid Search Requests ---
    # Dense Search Request
    dense_req = {
        "anns_field": dense_vector_field,
        "search_params": final_dense_params,
        "search_data": [query_dense_vector],
        "limit": limit
    }

    # Sparse Search Request (BM25)
    sparse_req = {
        "anns_field": sparse_text_field,
        "search_params": final_sparse_params,
        "search_data": [ text_to_term_freq(query_text) ],
        "limit": limit
    }

    search_requests = [dense_req, sparse_req]

    # --- Composite Scoring Option ---
    if settings.ENABLE_COMPOSITE_SCORING:
        # Dense-only search
        dense_kwargs = {
            "collection_name": collection_name,
            "data": [query_dense_vector],
            "anns_field": dense_vector_field,
            "search_params": final_dense_params,
            "limit": limit,
            "output_fields": output_fields
        }
        if id_filter:
            dense_kwargs["filter"] = id_filter
        dense_res = milvus_client.search(**dense_kwargs)[0]

        # Generate vector embedding for sparse (BM25 alternative) via dense model
        try:
            query_sparse_vector = await create_embedding(query_text)
        except Exception as e:
            logger.warning(f"Failed to create sparse embedding, falling back to dense: {e}")
            query_sparse_vector = query_dense_vector

        # Sparse-only search via vector embedding
        sparse_kwargs = {
            "collection_name": collection_name,
            "data": [query_sparse_vector],
            "anns_field": dense_vector_field,  # vector field
            "search_params": final_sparse_params,  # reuse sparse_params or configure separately
            "limit": limit,
            "output_fields": output_fields
        }
        if id_filter:
            sparse_kwargs["filter"] = id_filter
        sparse_res = milvus_client.search(**sparse_kwargs)[0]

        # Build score maps
        max_sparse = max(
            (hit.get("score", hit.get("distance", 0.0)) for hit in sparse_res),
            default=1.0
        )
        scores = {}
        for hit in dense_res:
            doc_id = hit.get("id")
            score_val = hit.get("score", hit.get("distance", 0.0))
            content = hit.get("content") or hit.get("entity", {}).get("content")
            metadata = hit.get("metadata") or hit.get("entity", {}).get("metadata")
            scores[doc_id] = {
                "dense": (score_val + 1) / 2.0,
                "sparse": 0.0,
                "meta": 0.0,
                "content": content,
                "metadata": metadata
            }
        for hit in sparse_res:
            doc_id = hit.get("id")
            score_val = hit.get("score", hit.get("distance", 0.0))
            content = hit.get("content") or hit.get("entity", {}).get("content")
            metadata = hit.get("metadata") or hit.get("entity", {}).get("metadata")
            entry = scores.setdefault(doc_id, {
                "dense": 0.0,
                "sparse": 0.0,
                "meta": 0.0,
                "content": content,
                "metadata": metadata
            })
            entry["sparse"] = score_val / max_sparse
        # Compute composite and collect
        formatted_results = []
        for doc_id, vals in scores.items():
            # metadata boost
            if settings.ENABLE_METADATA_FILTER and settings.METADATA_FILTER_VALUE and \
               vals["metadata"].get(settings.METADATA_FILTER_FIELD) == settings.METADATA_FILTER_VALUE:
                vals["meta"] = 1.0
            comp = (settings.COMPOSITE_WEIGHT_DENSE * vals["dense"] +
                    settings.COMPOSITE_WEIGHT_SPARSE * vals["sparse"] +
                    settings.COMPOSITE_WEIGHT_META * vals["meta"])
            formatted_results.append({
                "id": doc_id,
                "score": comp,
                "content": vals["content"],
                "metadata": vals["metadata"]
            })
        # Safely determine how many results to return
        top_k = settings.COMPOSITE_TOP_K if isinstance(settings.COMPOSITE_TOP_K, int) else limit
        return sorted(formatted_results, key=lambda x: x["score"], reverse=True)[: top_k]
    else:
        try:
            # Perform separate dense and sparse searches
            dense_hits = milvus_client.search(
                collection_name=collection_name,
                data=[query_dense_vector],
                anns_field=dense_vector_field,
                search_params=final_dense_params,
                limit=limit,
                output_fields=output_fields,
                filter=id_filter
            )[0]
            sparse_hits = milvus_client.search(
                collection_name=collection_name,
                data=[text_to_term_freq(query_text)],
                anns_field=sparse_text_field,
                search_params=final_sparse_params,
                limit=limit,
                output_fields=output_fields,
                filter=id_filter
            )[0]

            # Normalize and fuse scores equally
            max_dense = max((hit.get("score", hit.get("distance", 0.0)) for hit in dense_hits), default=1.0)
            max_sparse = max((hit.get("score", hit.get("distance", 0.0)) for hit in sparse_hits), default=1.0)
            combined = {}
            for hit in dense_hits:
                doc_id = hit.get("id")
                combined.setdefault(doc_id, {
                    "content": hit.get("content") or hit.get("entity", {}).get("content"),
                    "metadata": hit.get("metadata") or hit.get("entity", {}).get("metadata"),
                    "dense": 0.0,
                    "sparse": 0.0
                })["dense"] = hit.get("score", hit.get("distance", 0.0)) / max_dense
            for hit in sparse_hits:
                doc_id = hit.get("id")
                combined.setdefault(doc_id, {
                    "content": hit.get("content") or hit.get("entity", {}).get("content"),
                    "metadata": hit.get("metadata") or hit.get("entity", {}).get("metadata"),
                    "dense": 0.0,
                    "sparse": 0.0
                })["sparse"] = hit.get("score", hit.get("distance", 0.0)) / max_sparse

            # Build formatted list with average of normalized scores
            formatted_results = sorted(
                [
                    {
                        "id": doc_id,
                        "score": (vals["dense"] + vals["sparse"]) / 2.0,
                        "content": vals["content"],
                        "metadata": vals["metadata"],
                    }
                    for doc_id, vals in combined.items()
                ],
                key=lambda x: x["score"],
                reverse=True
            )[:limit]

            # If no hybrid results, fall back to metadata filename search
            if not formatted_results:
                logger.debug("No hybrid results; falling back to metadata-based search.")
                try:
                    # Build fallback expression matching each term in the query
                    import re
                    terms = re.findall(r"\w+", query_text)
                    expr_parts = [f'contains(original_filename, "{term}")' for term in terms]
                    expr = " and ".join(expr_parts)
                    meta_hits = milvus_client.query(
                        collection_name=collection_name,
                        expr=expr,
                        output_fields=output_fields
                    )
                    # Map query results to same format
                    fallback = [
                        {
                            "id": hit.get("id"),
                            "score": 0.0,
                            "content": hit.get("content") or "",
                            "metadata": hit.get("metadata") or {}
                        }
                        for hit in meta_hits
                    ]
                    if fallback:
                        logger.debug(f"Metadata fallback returned {len(fallback)} results.")
                        return fallback[:limit]
                except Exception as me:
                    logger.error(f"Metadata fallback failed: {me}", exc_info=True)
            logger.debug(f"Milvus hybrid search successful. Returning {len(formatted_results)} fused results.")
            return formatted_results

        except Exception as e:
            logger.error(f"Milvus hybrid search error (collection: '{collection_name}'): {str(e)}", exc_info=True)
            if "collection not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                logger.warning(f"Milvus collection '{collection_name}' not found during hybrid search.")
                return []
            raise HTTPException(status_code=500, detail=f"Milvus hybrid search failed unexpectedly: {str(e)}")

# --- Add helper for safe metadata extraction ---
def safe_get_metadata(hit) -> Dict:
    try:
        # If hit is a dictionary, try to get metadata directly
        if isinstance(hit, dict):
            # Try direct access to metadata field
            if isinstance(hit.get('metadata'), dict):
                return hit.get('metadata')
            
            # Try the entity sub-dictionary if it exists
            if isinstance(hit.get('entity'), dict) and isinstance(hit.get('entity').get('metadata'), dict):
                return hit.get('entity').get('metadata')
                
            # Try parse if metadata is a string
            raw_meta = hit.get('metadata')
            if isinstance(raw_meta, str):
                try:
                    parsed_meta = json.loads(raw_meta)
                    if isinstance(parsed_meta, dict):
                        return parsed_meta
                except json.JSONDecodeError:
                    hit_id = hit.get('id', '?')
                    logger.warning(f"Metadata field was a string but failed JSON parsing for hit ID '{hit_id}': {raw_meta}")
                    return {}
                    
            # If we reach here, couldn't find valid metadata in the dictionary
            hit_id = hit.get('id', '?')
            logger.warning(f"Could not extract dictionary metadata from hit ID '{hit_id}'. Hit type: {type(hit)}.")
            return {}
            
        # Object-style access for non-dictionary objects
        elif hasattr(hit, 'entity') and hasattr(hit.entity, 'get') and isinstance(hit.entity.get('metadata'), dict):
            return hit.entity.get('metadata')
        elif hasattr(hit, 'get') and isinstance(hit.get('metadata'), dict):
            return hit.get('metadata')
        elif hasattr(hit, 'entity') and hasattr(hit.entity, 'metadata') and isinstance(hit.entity.metadata, dict):
             return hit.entity.metadata
        elif hasattr(hit, 'metadata') and isinstance(hit.metadata, dict):
             return hit.metadata
        else:
            # Attempt to parse if metadata is a stringified JSON
            raw_meta = None
            if hasattr(hit, 'entity') and hasattr(hit.entity, 'get'):
                raw_meta = hit.entity.get('metadata')
            elif hasattr(hit, 'get'):
                 raw_meta = hit.get('metadata')
            
            if isinstance(raw_meta, str):
                 try:
                      parsed_meta = json.loads(raw_meta)
                      if isinstance(parsed_meta, dict):
                           return parsed_meta
                 except json.JSONDecodeError:
                      # --- Modified Warning Log ---
                      # Avoid logging the full hit which might contain the vector
                      hit_id = getattr(hit, 'id', None) or hit.get('id', '?') # Try to get ID safely
                      logger.warning(f"Metadata field was a string but failed JSON parsing: {raw_meta}")
                      return {}
            # --- Modified Warning Log ---
            # Avoid logging the full hit which might contain the vector
            hit_id = getattr(hit, 'id', None) or hit.get('id', '?') # Try to get ID safely
            logger.warning(f"Could not extract dictionary metadata from hit ID '{hit_id}'. Hit type: {type(hit)}.")
            # logger.warning(f"Could not extract dictionary metadata from hit: {hit}. Structure: {dir(hit)}") # Old log
            # --- End Modified Log ---
            return {} # Return empty dict if extraction fails
    except Exception as e:
         logger.error(f"Unexpected error extracting metadata from hit {getattr(hit, 'id', '?')}: {e}", exc_info=True)
         return {}
# --- End helper ---

# Renamed and refactored for Milvus
async def search_milvus_knowledge(
    query_texts: List[str], 
    collection_name: str,
    vector_field: str = "dense", # Use actual dense vector field name
    output_fields: List[str] = ["id", "content", "dense", "metadata"], # Request actual fields
    limit: int = 10,
    search_params: Optional[Dict] = None,
    filter_expr: Optional[str] = None
) -> List[List[Dict[str, Any]]]: # Return type changed to List[List[...]]
    """Searches Milvus collection for multiple query texts and returns formatted results."""
    all_formatted_results = [] # List to hold results for each query
    try:
        milvus_client = get_milvus_client()
        
        # Use the client instance directly to check for collection existence
        if not milvus_client.has_collection(collection_name):
             logger.error(f"Milvus collection '{collection_name}' not found.")
             # Return a list of empty lists, one for each query
             return [[] for _ in query_texts]

        # Generate embeddings for all query texts at once
        try:
            embeddings = await asyncio.gather(*(create_embedding(text) for text in query_texts))
            # Ensure embeddings are lists of floats
            query_vectors = [emb.tolist() if hasattr(emb, 'tolist') else emb for emb in embeddings]
            if not query_vectors or len(query_vectors) != len(query_texts):
                 raise ValueError("Embedding generation failed or returned incorrect number of vectors.")
        except Exception as e:
            logger.error(f"Failed to generate embeddings for queries: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to generate query embeddings.")

        # Define default search parameters if none provided
        # Example for COSINE metric with HNSW index
        default_params = {"metric_type": "COSINE", "params": {"ef": 128}}
        final_params = search_params or default_params

        logger.debug(f"Attempting Milvus search in collection '{collection_name}' for {len(query_texts)} queries with limit {limit} and filter: '{filter_expr}'")

        search_kwargs = {
            "collection_name": collection_name,
            "data": query_vectors,
            "anns_field": vector_field,
            "limit": limit,
            "output_fields": output_fields,
        }
        if filter_expr:
            logger.debug(f"Adding filter expression to search: {filter_expr}")
            search_kwargs["filter"] = filter_expr

        # Perform the search for all queries, using the correct 'search_params' argument
        search_results = milvus_client.search(
            search_params=final_params, # <-- CORRECTED ARGUMENT NAME
            **search_kwargs
        )
        logger.info(f"Milvus search completed. Received results for {len(search_results)} queries.") # Log count

        # Process results for each query
        for i, hits in enumerate(search_results):
            query_formatted_results = []
            logger.debug(f"Processing {len(hits)} hits for query {i+1}: '{query_texts[i]}'")
            
            # --- START: Modify Log for Raw Hits (Exclude Vector) ---
            if logger.isEnabledFor(logging.DEBUG): # Only process if DEBUG is enabled
                try:
                    hits_for_log = []
                    for hit_original in hits:
                        # Create a deep copy to avoid modifying original results
                        hit_copy = copy.deepcopy(hit_original)
                        
                        if isinstance(hit_copy, dict):
                            # Remove vector field from top level if present
                            if vector_field in hit_copy:
                                del hit_copy[vector_field]
                            # Remove vector field from entity sub-dict if present
                            if 'entity' in hit_copy and isinstance(hit_copy['entity'], dict) and vector_field in hit_copy['entity']:
                                del hit_copy['entity'][vector_field]
                                # If entity becomes empty after removing vector, optionally remove entity itself
                                # if not hit_copy['entity']:
                                #     del hit_copy['entity']
                            hits_for_log.append(hit_copy)
                        else: 
                           # Keep non-dict items as is (though unexpected)
                           hits_for_log.append(hit_copy) 
                    logger.debug(f"Raw hits (vector excluded) for query {i+1}: {hits_for_log}")
                except Exception as log_e:
                    logger.warning(f"Could not exclude vector field from raw hits log: {log_e}")
                    # Log the original hits as a fallback ONLY if the processing failed
                    logger.debug(f"Original raw hits for query {i+1}: {hits}") 
            # --- END: Modify Log --- 
            
            for hit in hits:
                try:
                    # Safely extract basic fields using dictionary access
                    doc_id = hit.get('id')
                    # Use distance as score; adjust if metric type changes
                    score = hit.get('distance', hit.get('score')) # Check for distance first, then score
                    
                    # Check if essential fields are present
                    if doc_id is None or score is None:
                        logger.warning(f"Skipping hit due to missing 'id' or 'score'/'distance'. Hit data: {hit}")
                        continue
                        
                    # Use the safe helper to get metadata
                    metadata = safe_get_metadata(hit)
                    
                    # Get content safely
                    content = hit.get('content', hit.get('entity', {}).get('content', ''))
                    if not isinstance(content, str):
                        logger.warning(f"Content field for hit ID {doc_id} is not a string, setting to empty.")
                        content = '' # Ensure content is always a string
                        
                    # Include content in the formatted results for the reranker
                    query_formatted_results.append({
                        "id": doc_id,
                        "score": score,
                        "metadata": metadata,
                        "content": content
                    })
                except Exception as e:
                    hit_id_str = str(hit.get('id', '[unknown ID]')) # Get ID safely for logging
                    logger.error(f"Unexpected error processing hit ID '{hit_id_str}' for query {i+1}: {e}", exc_info=True)
            
            logger.debug(f"Formatted {len(query_formatted_results)} results for query {i+1}. Previously logged success incorrectly.") # Corrected log
            all_formatted_results.append(query_formatted_results)

        logger.info(f"Milvus search formatting complete. Returning results for {len(all_formatted_results)} queries.")
        return all_formatted_results # Return list of lists

    except HTTPException as http_exc:
        raise http_exc # Re-raise FastAPI exceptions
    except Exception as e:
        logger.error(f"Error during Milvus search in '{collection_name}': {e}", exc_info=True)
        # Return list of empty lists on general error
        return [[] for _ in query_texts]

# --- Reranking Function ---
async def rerank_results(query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Reranks search results using a CrossEncoder model based on the original query.
    Adds a 'rerank_score' to each result and sorts them.
    If the reranker model failed to load or an error occurs, returns the original results.
    """
    reranker_model = _get_reranker_model() # Ensure model is loaded
    if reranker_model is None:
        logger.warning("Reranker model not loaded or failed to load. Skipping reranking.")
        return results # Return original results if model isn't available

    if not results:
        logger.debug("No results provided to rerank.")
        return []

    # Prepare pairs for the CrossEncoder: (query, document_content)
    # Ensure content exists and is a string
    pairs = []
    valid_results_indices = [] # Keep track of indices of results with valid content
    for i, res in enumerate(results):
        content = res.get("content")
        if isinstance(content, str) and content.strip():
            pairs.append((query, content))
            valid_results_indices.append(i)
        else:
            logger.warning(f"Skipping result with invalid/missing content for reranking: ID {res.get('id')}")

    if not pairs:
        logger.warning("No valid content found in results to rerank.")
        return results # Return original results if no valid content

    try:
        logger.debug(f"Reranking {len(pairs)} results with model {RERANKER_MODEL_NAME}...")
        # Run prediction in threadpool as it can be CPU-intensive
        scores = await run_in_threadpool(reranker_model.predict, pairs)
        logger.debug(f"Reranking scores obtained.")

        # Add scores back to the corresponding valid results
        reranked_results_subset = []
        original_results_with_scores = []

        score_idx = 0
        for original_idx, res in enumerate(results):
            if original_idx in valid_results_indices:
                # Add score to results that were actually reranked
                res['rerank_score'] = scores[score_idx]
                reranked_results_subset.append(res)
                original_results_with_scores.append(res) # Keep track to merge later
                score_idx += 1
            else:
                # Assign a very low score to results that couldn't be reranked
                res['rerank_score'] = -float('inf')
                original_results_with_scores.append(res)

        # Sort ALL results (including those not reranked) by the new score, highest first
        # Those with -inf score will end up at the bottom.
        sorted_results = sorted(original_results_with_scores, key=lambda x: x.get('rerank_score', -float('inf')), reverse=True)

        logger.info(f"Reranking complete. Returning {len(sorted_results)} results.")
        return sorted_results

    except Exception as e:
        logger.error(f"Error during reranking with {RERANKER_MODEL_NAME}: {e}", exc_info=True)
        # Return the original results if reranking fails
        return results

# create_retrieval_embedding function remains the same as it doesn't interact with the vector DB client
async def create_retrieval_embedding(text: str, field: str) -> List[float]:
    """
    Generate an embedding for 'text' using the specified vector field's model.
    Supported fields: 'dense', 'colbertv2.0'. REMOVED 'bm25'.
    """
    normalized = text.replace("\n", " ")
    model = None
    # Select the appropriate model using lazy loaders
    if field == "dense":
        model = _get_dense_model()
        if model is None:
            raise ValueError("Dense embedding model is not loaded or failed to load.")
    elif field == "colbertv2.0":
        model = _get_colbert_model()
        if model is None:
            raise NotImplementedError("ColBERT embedding model is not loaded or failed to load.")
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
