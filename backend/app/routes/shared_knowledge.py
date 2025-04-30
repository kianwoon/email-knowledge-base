import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
# Removed Qdrant imports
# from qdrant_client import QdrantClient
# from qdrant_client import models as qdrant_models
# Import Milvus client
from pymilvus import MilvusClient
from datetime import datetime, timezone
import bcrypt

from ..db.session import get_db
# Use Milvus client dependency
from ..db.milvus_client import get_milvus_client
from ..models.token_models import TokenDB
from ..crud import token_crud
# Import the specific search function we need
from ..services.embedder import create_embedding, search_milvus_knowledge, rerank_results
# Import the counters defined in main
# We need to import them from where they are defined
from app.main import COLUMN_BLOCKS, ATTACHMENT_REDACTIONS

# Configure logging
logger = logging.getLogger(__name__)

# API Key Header for Bearer token
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# --- Token Validation Dependency (MOVED TO auth.py) ---

# async def get_validated_token(...): 
#     ...

# --- Router Definition ---

router = APIRouter(
    prefix="/shared-knowledge",
    tags=["Shared Knowledge"],
    responses={404: {"description": "Not found"}},
)

# Import the dependency from its new location
from app.dependencies.auth import get_validated_token

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_shared_knowledge(
    query: str = Query(..., description="The search query string."),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results to return."),
    token: TokenDB = Depends(get_validated_token), # Use the dependency (import path updated)
    milvus_client: MilvusClient = Depends(get_milvus_client) # Milvus client dependency
):
    """
    Performs a semantic search on the knowledge base using a valid API token.
    Access is controlled by the rules and sensitivity defined in the token,
    as well as column projection and attachment permissions.
    """
    logger.info(f"Shared search request received using token {token.id} (Owner: {token.owner_email}), Query: '{query}'")

    try:
        # 1. Determine target collection based on token owner
        sanitized_email = token.owner_email.replace('@', '_').replace('.', '_')
        target_collection_name = f"{sanitized_email}_knowledge_base_bm"
        logger.info(f"Targeting search in collection: {target_collection_name} based on token owner.")

        # 2. Generate embedding for the query
        query_embedding = await create_embedding(query)
        if not query_embedding:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate query embedding.")

        # 3. Generate Milvus filter based on token rules
        milvus_filter_expression = token_crud.create_milvus_filter_from_token(token)
        logger.debug(f"Generated Milvus filter for token {token.id}: {milvus_filter_expression}")

        # 4. Perform the search using the search_milvus_knowledge helper
        # The limit passed here might be adjusted later by token.row_limit, 
        # but searching with a reasonable limit first is efficient.
        search_limit = min(limit, token.row_limit) # Respect token row limit, capped by query limit
        logger.debug(f"Performing Milvus search with effective limit: {search_limit}")
        results = await search_milvus_knowledge(
            collection_name=target_collection_name,
            query_texts=[query],
            limit=search_limit, # Use the adjusted limit
            filter_expr=milvus_filter_expression
        )
        
        dense_search_results = results[0] if results and isinstance(results, list) and len(results) > 0 else []
        logger.info(f"Initial dense search found {len(dense_search_results)} results for query '{query}' using token {token.id}. Reranking...")

        # 5. Rerank the results
        reranked_results = await rerank_results(query=query, results=dense_search_results)
        logger.info(f"Reranking complete. Found {len(reranked_results)} results before applying token projections for query '{query}' using token {token.id}.")

        # 6. Apply Token Scope: Column Projection and Attachment Filtering
        processed_results = []
        # Define essential keys to always include besides metadata
        essential_keys = ['id', 'score'] 
        # Define potential attachment keys to remove if disallowed
        attachment_keys = ['attachments', 'attachment_info', 'files', 'file_data'] 
        column_block_count = 0
        attachment_redaction_count = 0

        for result in reranked_results:
            processed_result = {}
            metadata = result.get('metadata', {}) # Safely get metadata
            original_metadata_keys = set(metadata.keys())
            
            # Copy essential keys
            for key in essential_keys:
                if key in result:
                    processed_result[key] = result[key]

            # Apply column projection if allow_columns is set
            if token.allow_columns: 
                projected_metadata = {}
                allowed_col_set = set(token.allow_columns)
                blocked_cols = []
                for col_key in original_metadata_keys:
                    if col_key in allowed_col_set:
                        projected_metadata[col_key] = metadata[col_key]
                    else:
                        # Track blocked column (ensure it wasn't an essential/attachment key)
                        if col_key not in essential_keys and col_key not in attachment_keys: 
                            blocked_cols.append(col_key)
                processed_result['metadata'] = projected_metadata
                # Increment counter if any relevant metadata columns were blocked
                if blocked_cols:
                     column_block_count += len(blocked_cols)
                     logger.debug(f"Blocked columns {blocked_cols} for result {result.get('id')} due to token {token.id} policy.")
            else:
                processed_result['metadata'] = metadata.copy()

            # Remove attachments if not allowed
            if not token.allow_attachments and 'metadata' in processed_result:
                metadata_keys_before_attach_filter = set(processed_result['metadata'].keys())
                for attach_key in attachment_keys:
                    if attach_key in processed_result['metadata']:
                        del processed_result['metadata'][attach_key]
                # Increment counter if any attachment key was actually removed
                if len(metadata_keys_before_attach_filter.intersection(attachment_keys)) > 0:
                    attachment_redaction_count += 1
                    logger.debug(f"Redacted attachment keys for result {result.get('id')} due to token {token.id} policy.")
            
            processed_results.append(processed_result)

        # Increment Prometheus counters *after* processing all results for the request
        if column_block_count > 0:
            COLUMN_BLOCKS.labels(token_id=token.id, route="/shared-knowledge/search").inc(column_block_count)
        if attachment_redaction_count > 0:
            ATTACHMENT_REDACTIONS.labels(token_id=token.id, route="/shared-knowledge/search").inc(attachment_redaction_count)

        # 7. Apply Row Limit (although already applied in search_milvus_knowledge, this ensures final count)
        # The search_milvus_knowledge call already respects the row limit.
        # final_limited_results = processed_results[:token.row_limit] 
        # We use the search_limit calculated earlier which respects token.row_limit
        final_limited_results = processed_results

        logger.info(f"Returning {len(final_limited_results)} processed results after applying token {token.id} scope for query '{query}'.")
        return final_limited_results

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error during shared knowledge search for token {token.id}: {e}", exc_info=True)
        target_collection_name_on_error = f"{token.owner_email.replace('@','_').replace('.','_')}_knowledge_base_bm"
        if "not found" in str(e).lower() and target_collection_name_on_error in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge base collection for token owner not found.")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during the search.") 