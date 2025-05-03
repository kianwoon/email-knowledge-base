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
import time # Added time for execution duration
import json

from ..db.session import get_db
# Use Milvus client dependency
from ..db.milvus_client import get_milvus_client
from ..models.token_models import TokenDB, SharedMilvusResult, SharedSearchRequest # Import new response model and request body model
from ..crud import token_crud
# Import the specific search function we need
from ..services.embedder import create_embedding, search_milvus_knowledge, rerank_results
# Import the counters defined in main
# We need to import them from where they are defined
from app.metrics import COLUMN_BLOCKS, ATTACHMENT_REDACTIONS
from ..models.external_audit_log import ExternalAuditLog # Added import for logging

# Configure logging
logger = logging.getLogger(__name__)

# API Key Header for Bearer token
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# --- Token Validation Dependency (MOVED TO auth.py) ---

# async def get_validated_token(...): 
#     ...

# --- Router Definition ---

router = APIRouter(
    tags=["Shared Knowledge"],
    # Add standard error responses for documentation
    responses={
        401: {"description": "Unauthorized: Invalid or missing authentication token."},
        403: {"description": "Forbidden: Token is inactive, expired, or does not have permission."},
        404: {"description": "Not Found: Could not find the knowledge base collection for the token owner."},
        422: {"description": "Validation Error: Invalid input parameters."},
        500: {"description": "Internal Server Error."},
    },
)

# Import the dependency from its new location
from app.dependencies.auth import get_validated_token

# Updated response_model and expanded docstring
@router.post(
    "/search", 
    response_model=List[SharedMilvusResult], # Use the specific model
    summary="Search Shared Knowledge Base (Milvus Only)",
    description="""
Performs a semantic search *only* on the Milvus vector store portion of a shared knowledge base,
using a valid API token (`Authorization: Bearer <prefix_secret>`).

**Request Body:**
*   `query` (string, required): The search query string.
*   `limit` (integer, optional): Maximum number of search results (default 10, max 100, subject to token row limit).

**Access Control:**
The search results are filtered based on the provided token's permissions:
*   **Row-Level Filtering:** Applies sensitivity level checks and `allow_rules` (interpreted as `department` filters) defined in the token.
*   **Column Filtering:** The `metadata` returned for each result includes only the columns specified in the token's `allow_columns` list. If `allow_columns` is null or empty, all available metadata columns are returned (subject to attachment filtering).
*   **Attachment Filtering:** If the token's `allow_attachments` is `false`, known attachment-related keys (e.g., 'attachments', 'file_data') are removed from the `metadata`.
*   **Result Limit:** The number of results is capped by the minimum of the `limit` from the request body and the token's `row_limit`.

**Note:** This endpoint currently **does not** search the structured data stored in Iceberg.
Deny rules (`deny_rules`) in the token are **not** currently applied.
    """
)
async def search_shared_knowledge(
    request_body: SharedSearchRequest, # Accept request body
    db: Session = Depends(get_db), # Added Session dependency
    token: TokenDB = Depends(get_validated_token), # Use the dependency
    milvus_client: MilvusClient = Depends(get_milvus_client) # Milvus client dependency
):
    start_time = time.perf_counter() # Start timer
    # Get query and limit from request body
    query = request_body.query
    limit = request_body.limit
    
    logger.info(f"Shared search request received using token {token.id} (Owner: {token.owner_email}), Query: '{query}'")
    
    audit_log = None # Initialize audit log variable
    
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
        essential_keys = ['id', 'score'] 
        attachment_keys = ['attachments', 'attachment_info', 'files', 'file_data'] 
        column_block_count = 0
        attachment_redaction_count = 0

        for result in reranked_results:
            processed_result = {}
            metadata = result.get('metadata', {}) # Safely get metadata
            original_metadata_keys = set(metadata.keys())
            
            # Copy essential keys (id, score)
            for key in essential_keys:
                if key in result:
                    processed_result[key] = result[key]

            # Apply column projection if allow_columns is set
            filtered_metadata = {}
            if token.allow_columns: 
                allowed_col_set = set(token.allow_columns)
                blocked_cols = []
                for col_key, col_value in metadata.items():
                    if col_key in allowed_col_set:
                        filtered_metadata[col_key] = col_value
                    else:
                        if col_key not in essential_keys and col_key not in attachment_keys: 
                            blocked_cols.append(col_key)
                if blocked_cols:
                     column_block_count += len(blocked_cols)
                     # NOTE: Column blocking logging now handled by audit log below
                     # logger.debug(f"Blocked columns {blocked_cols} for result {result.get('id')} due to token {token.id} policy.")
            else:
                # If allow_columns is not set, include all metadata initially
                filtered_metadata = metadata.copy()

            # Remove attachments if not allowed (from the potentially already filtered metadata)
            if not token.allow_attachments:
                keys_before_filter = set(filtered_metadata.keys())
                for attach_key in attachment_keys:
                    if attach_key in filtered_metadata:
                        del filtered_metadata[attach_key]
                if len(keys_before_filter.intersection(attachment_keys)) > 0:
                    attachment_redaction_count += 1
                    # NOTE: Attachment redaction logging now handled by audit log below
                    # logger.debug(f"Redacted attachment keys for result {result.get('id')} due to token {token.id} policy.")
            
            processed_result['metadata'] = filtered_metadata
            processed_results.append(processed_result)

        # Increment Prometheus counters *after* processing all results for the request
        if column_block_count > 0:
            COLUMN_BLOCKS.labels(token_id=token.id, route="/shared-knowledge/search").inc(column_block_count)
        if attachment_redaction_count > 0:
            ATTACHMENT_REDACTIONS.labels(token_id=token.id, route="/shared-knowledge/search").inc(attachment_redaction_count)

        # Final list already limited by search_limit which respects token.row_limit
        final_limited_results = processed_results
        
        end_time = time.perf_counter() # End timer
        execution_time_ms = int((end_time - start_time) * 1000)

        logger.info(f"Returning {len(final_limited_results)} processed results after applying token {token.id} scope for query '{query}'. Took {execution_time_ms} ms.")

        # --- Create and Add Audit Log Entry ---
        try:
            # Ensure filter_data is valid JSON or None
            try:
                # Attempt to represent the filter as JSON
                filter_json_data = json.dumps({"milvus_filter": milvus_filter_expression}) if milvus_filter_expression else None
            except TypeError:
                logger.warning(f"Could not serialize Milvus filter to JSON: {milvus_filter_expression}. Storing as None.")
                filter_json_data = None # Fallback to None if serialization fails

            # Create response data as a dictionary
            response_details = {
                "resource_id": target_collection_name, # Include resource_id here
                "query": query, # Include query here
                "blocked_column_count": column_block_count,
                "attachment_redaction_count": attachment_redaction_count
            }
            # Serialize response data to JSON string
            response_data_json = json.dumps(response_details)

            audit_log = ExternalAuditLog(
                token_id=token.id,
                # NOTE: Set action_type based on existence in model, expecting DB column to be added later
                action_type='SHARED_KNOWLEDGE_SEARCH' if hasattr(ExternalAuditLog, 'action_type') else None,
                resource_id=target_collection_name, # Use resource_id as defined in the model
                query_text=query, # ADDED: Provide the query text for the NOT NULL column
                # collection_name=target_collection_name, # REMOVED: Model uses resource_id for this
                filter_data=filter_json_data, # Assign JSON string or None
                result_count=len(final_limited_results),
                response_data=response_data_json, # Assign serialized JSON string
                execution_time_ms=execution_time_ms,
                created_at=datetime.now(timezone.utc)
            )
            db.add(audit_log)
            db.commit()
            logger.info(f"Successfully logged audit entry for token {token.id}")
        except Exception as audit_exc:
            logger.error(f"Failed to save audit log for token {token.id}: {audit_exc}", exc_info=True)
            db.rollback() # Rollback audit log commit on error
            # Decide if the main request should still succeed or fail if logging fails
            # For now, let the main response return, but log the failure critically
        # --- End Audit Log Entry ---

        # FastAPI will automatically validate the output against List[SharedMilvusResult]
        return final_limited_results

    except HTTPException as http_exc:
        # Re-raise exceptions from dependencies (like get_validated_token)
        raise http_exc
    except Exception as e:
        logger.error(f"Error during shared knowledge search for token {token.id}: {e}", exc_info=True)
        target_collection_name_on_error = f"{token.owner_email.replace('@','_').replace('.','_')}_knowledge_base_bm"
        # Check for Milvus collection not found specifically
        if "collection not found" in str(e).lower() and target_collection_name_on_error in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge base collection for token owner not found.")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during the search.") 