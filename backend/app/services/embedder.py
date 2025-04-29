import logging
from typing import List, Dict, Any, Optional
# Remove Qdrant imports
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.exceptions import UnexpectedResponse
# Import Milvus client
from pymilvus import MilvusClient
from fastapi import HTTPException
import httpx # Keep for now, maybe remove _httpx_search later
from sentence_transformers import SentenceTransformer, CrossEncoder
from fastapi.concurrency import run_in_threadpool

import re
from collections import Counter

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

# --- Initialize Reranker Model ---
# Define the reranker model name (can be moved to settings if needed)
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_reranker_model = None
try:
    _reranker_model = CrossEncoder(RERANKER_MODEL_NAME)
    logger.info(f"Successfully loaded reranker model: {RERANKER_MODEL_NAME}")
except Exception as e:
    logger.warning(f"Failed to load reranker model '{RERANKER_MODEL_NAME}': {e}. Reranking will be skipped.")

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
            # Fetch IDs and metadata for all documents (no initial filter)
            # We fetch all because complex string contains filtering isn't reliable in Milvus expr
            # Consider adding a limit here if performance is an issue, but risks missing matches.
            meta_hits = milvus_client.query(
                collection_name=collection_name,
                filter="", # Fetch all initially
                output_fields=["id", "metadata"],
                limit=1000 # ADDED: Limit the pre-fetch query
            )
            
            allowed_ids = []
            # Filter in Python
            for hit in meta_hits:
                metadata = hit.get("metadata")
                if metadata and isinstance(metadata, dict):
                    original_filename = metadata.get("original_filename")
                    if original_filename and isinstance(original_filename, str):
                        # Check if filename contains ALL terms (case-insensitive)
                        if all(term.lower() in original_filename.lower() for term in filename_terms):
                            allowed_ids.append(hit["id"])
                            
            logger.debug(f"[Prefilter] matched IDs after Python filtering: {allowed_ids}")
            
            if not allowed_ids:
                logger.debug("No documents match filename terms filter; returning empty list.")
                return []
            
            # Ensure IDs are strings for the 'in' operator if they are not already
            id_list = ",".join(f'"{str(i)}"' if isinstance(i, str) else str(i) for i in allowed_ids)
            id_filter = f"id in [{id_list}]"
            logger.debug(f"Pre-filter ID list for subsequent vector searches: {id_filter}")
            
        except Exception as e:
            # Log error but proceed without filter to avoid breaking search entirely
            logger.error(f"Filename pre-filter failed: {e}. Proceeding without filename filter.", exc_info=True)
            id_filter = None # Ensure filter is None if pre-filtering failed

    # Use the generated id_filter (which might be None) in subsequent search calls
    # The logger message needs adjustment as filter_expr is removed.
    logger.debug(f"Attempting Milvus HYBRID search in collection \'{collection_name}\' for query \'{query_text}\' with limit {limit} and ID filter: \'{id_filter}\'")

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

# Renamed and refactored for Milvus
async def search_milvus_knowledge(
    query_texts: List[str], 
    collection_name: str,
    vector_field: str = "dense", # Use actual dense vector field name
    output_fields: List[str] = ["id", "content", "dense", "metadata"], # Request actual fields
    limit: int = 10,
    search_params: Optional[Dict] = None,
    filter_expr: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in the specified Milvus collection.
    Returns a list of results including payload.
    """
    milvus_client: MilvusClient = get_milvus_client()
    
    # Removed Qdrant-specific dimension check logic

    logger.debug(f"Attempting Milvus search in collection '{collection_name}' with limit {limit} and filter: '{filter_expr}'")

    # Ensure structure matches MilvusClient.search requirements (anns_field inside search_params)
    default_search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
    search_params = search_params or default_search_params

    results = []
    for query_text in query_texts:
        try:
            # Embed the query text
            query_embedding = await create_embedding(query_text)
            # Ensure embeddings are list of lists if needed by client
            if hasattr(query_embedding, 'tolist'):
                query_embedding_list = query_embedding.tolist()
            else:
                query_embedding_list = query_embedding # Assume it's already in correct format
            # logger.debug(f"Shape of query embeddings: {query_embedding.shape}") # Removed as query_embedding is now a list

            # Use keyword arguments ONLY for the MilvusClient.search call
            search_kwargs = {
                "collection_name": collection_name,
                "data": [query_embedding_list],
                "anns_field": vector_field,
                "limit": limit,
                "search_params": search_params,
                "output_fields": output_fields
            }

            # Conditionally add the filter using the 'filter' keyword
            if filter_expr:
                search_kwargs['filter'] = filter_expr
                logger.debug(f"Adding filter expression to search: {filter_expr}")
            else:
                logger.debug("No filter expression provided for search.")

            # Execute vector search via Milvus client using only keyword arguments
            search_result = milvus_client.search(**search_kwargs)

            # Format and return results
            formatted_results = []
            if search_result:
                hits = search_result[0] # Results for the first query
                for hit in hits:
                    # Extract fields directly from the hit dictionary
                    # The structure should be flat when output_fields is used
                    doc_id = hit.get('id')
                    # Get content and metadata, handling potential nesting in 'entity'
                    entity_data = hit.get('entity', {})
                    content = hit.get('content') or entity_data.get('content')
                    metadata = hit.get('metadata') or entity_data.get('metadata')
                    dense_vector = hit.get('dense') # Get the actual dense vector
                    score = hit.get('distance') # Or hit.score depending on client version

                    if doc_id is not None and content is not None: # Ensure essential fields exist
                        formatted_results.append({
                            "id": doc_id,
                            "score": score,
                            "content": content,
                            "metadata": metadata, # Metadata is already a dict/json
                            "dense": dense_vector # Include dense vector
                        })
                    else:
                        logger.warning(f"Skipping hit due to missing id or content: {hit}")

            results.append(formatted_results)

        except Exception as e:
            # Handle Milvus exceptions (e.g., collection not found, invalid filter)
            logger.error(f"Milvus search error (collection: '{collection_name}'): {str(e)}", exc_info=True)
            if "collection not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                logger.warning(f"Milvus collection '{collection_name}' not found during search.")
                # Skip to the next query_text if collection doesn't exist
                continue # Skip to the next query_text
            # You might want to check for other specific Milvus errors here
            # For now, raise a generic HTTPException for other errors
            raise HTTPException(status_code=500, detail=f"Milvus search failed unexpectedly (collection: '{collection_name}'): {str(e)}")

    logger.debug(f"Milvus search successful. Returning {len(results)} formatted results.")
    return results

# --- Reranking Function ---
async def rerank_results(query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Reranks search results using a CrossEncoder model based on the original query.
    Adds a 'rerank_score' to each result and sorts them.
    If the reranker model failed to load or an error occurs, returns the original results.
    """
    if _reranker_model is None:
        logger.warning("Reranker model not loaded. Skipping reranking.")
        return results
    
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
        scores = await run_in_threadpool(_reranker_model.predict, pairs)
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
