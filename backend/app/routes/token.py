# backend/app/routes/token.py
import logging
from uuid import UUID
from typing import List, Optional, Any, Dict
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, status, Body, Request, Response, Query
from sqlalchemy.orm import Session
import uuid

from pymilvus import MilvusClient

from ..services import token_service
from ..models.user import User
from ..db.session import get_db
from app.dependencies.auth import get_current_active_user
from ..models.token_models import (
    TokenResponse, TokenCreateRequest, TokenUpdateRequest, 
    TokenExport, TokenDB, TokenBundleRequest, 
    TokenCreateResponse, TokenType, SharedMilvusResult
)
from ..crud.token_crud import (
    create_user_token, 
    get_user_tokens, 
    get_token_by_id, 
    update_user_token, 
    delete_user_token,
    get_active_tokens,
    prepare_bundled_token_data,
    create_bundled_token,
    create_milvus_filter_from_token
)

# Import datetime for expiry check
from datetime import datetime, timezone, date, timedelta

# Import the new external model
from ..models.external_audit_log import ExternalAuditLog

# Import necessary types and functions
from sqlalchemy import func, select
from pydantic import BaseModel, Field

from app.db.milvus_client import get_milvus_client # Import Milvus client getter
from app.services.embedder import create_embedding, search_milvus_knowledge, rerank_results

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["token"],
    responses={404: {"description": "Not found"}},
)

# ==========================================
# Specific Routes (Must come BEFORE routes with path parameters)
# ==========================================

# --- Moved Usage Report Route UP ---
class TokenUsageStat(BaseModel):
    token_id: int
    token_name: str
    token_description: Optional[str] = None
    token_preview: str # Add preview
    usage_count: int
    last_used_at: Optional[datetime] = None

class TokenUsageReportResponse(BaseModel):
    usage_stats: List[TokenUsageStat]

# --- ADDED for Time Series --- 
class TimeSeriesDataPoint(BaseModel):
    date: date # Representing the day
    usage_count: int

class TimeSeriesResponse(BaseModel):
    time_series: List[TimeSeriesDataPoint]
# --- END ADDED ---

@router.get(
    "/usage-report",
    response_model=TokenUsageReportResponse,
    summary="Get Usage Report for Owned Tokens",
    description="Retrieves usage statistics for sharing tokens created by the current user, based on external audit logs. Optionally filters by date range."
)
async def get_token_usage_report(
    start_date: Optional[date] = Query(None, description="Filter usage logs from this date (inclusive). Format: YYYY-MM-DD"),
    end_date: Optional[date] = Query(None, description="Filter usage logs up to this date (inclusive). Format: YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieves usage statistics for tokens owned by the current user."""
    try:
        logger.info(f"Fetching token usage report for user '{current_user.email}' (Start: {start_date}, End: {end_date})")

        # Fetch all tokens owned by the user
        owned_tokens = get_user_tokens(db, owner_email=current_user.email)
        if not owned_tokens:
            return TokenUsageReportResponse(usage_stats=[])

        token_ids = [token.id for token in owned_tokens]

        # Base query for ExternalAuditLog
        stmt = select(
            ExternalAuditLog.token_id,
            func.count(ExternalAuditLog.id).label('usage_count'),
            func.max(ExternalAuditLog.created_at).label('last_used_at')
        ).where(
            ExternalAuditLog.token_id.in_(token_ids)
        )

        # Apply date filters if provided
        if start_date:
            stmt = stmt.where(ExternalAuditLog.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            stmt = stmt.where(ExternalAuditLog.created_at <= datetime.combine(end_date, datetime.max.time()))

        # Group by token_id
        stmt = stmt.group_by(ExternalAuditLog.token_id)

        # Execute the query
        result = db.execute(stmt).all()

        # Create a map of token_id to usage stats
        usage_map = {row.token_id: {"usage_count": row.usage_count, "last_used_at": row.last_used_at} for row in result}

        # Build the response list
        usage_stats_list: List[TokenUsageStat] = []
        for token in owned_tokens:
            stats = usage_map.get(token.id)
            usage_count = stats["usage_count"] if stats else 0
            last_used_at = stats["last_used_at"] if stats else None

            # >>> Generate token_preview from hashed_token <<< 
            hashed = token.hashed_token
            token_preview_value = f"{hashed[:4]}...{hashed[-4:]}" if hashed and len(hashed) > 8 else "[Invalid Hash]"

            usage_stats_list.append(
                TokenUsageStat(
                    token_id=token.id,
                    token_name=token.name,
                    token_description=token.description,
                    token_preview=token_preview_value, # <<< Use the generated value
                    usage_count=usage_count,
                    last_used_at=last_used_at
                )
            )
        
        # Sort by usage count descending
        usage_stats_list.sort(key=lambda x: x.usage_count, reverse=True)

        return TokenUsageReportResponse(usage_stats=usage_stats_list)

    except Exception as e:
        logger.error(f"Failed to get token usage report for user '{current_user.email}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve token usage report."
        )
# --- End Moved Route --- 

# --- ADDED Time Series Route --- 
@router.get(
    "/usage-timeseries",
    response_model=TimeSeriesResponse,
    summary="Get Token Usage Time Series Data",
    description="Retrieves daily usage counts for a specific token or all owned tokens within a date range."
)
async def get_token_usage_timeseries(
    token_id: Optional[int] = Query(None, description="Filter usage by a specific token ID. If omitted, aggregates usage for all owned tokens."),
    start_date: Optional[date] = Query(None, description="Filter usage logs from this date (inclusive). Format: YYYY-MM-DD"),
    end_date: Optional[date] = Query(None, description="Filter usage logs up to this date (inclusive). Format: YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        logger.info(f"Fetching token usage time series for user '{current_user.email}' (Token: {token_id}, Start: {start_date}, End: {end_date})")
        
        token_ids_to_query = []
        if token_id is not None:
            # Verify ownership if a specific token ID is requested
            token_check = get_token_by_id(db, token_id=token_id)
            if not token_check or token_check.owner_email != current_user.email:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="Token not found or you do not own this token."
                )
            token_ids_to_query.append(token_id)
        else:
            # If no specific token ID, get all tokens owned by the user
            owned_tokens = get_user_tokens(db, owner_email=current_user.email)
            if not owned_tokens:
                return TimeSeriesResponse(time_series=[]) # No tokens, no usage
            token_ids_to_query = [token.id for token in owned_tokens]
            
        if not token_ids_to_query:
             return TimeSeriesResponse(time_series=[]) # Should not happen if checks above pass, but safety first

        # Base query: Group by day and count occurrences
        stmt = select(
            func.date_trunc('day', ExternalAuditLog.created_at).label('usage_date'),
            func.count(ExternalAuditLog.id).label('usage_count')
        ).where(
            ExternalAuditLog.token_id.in_(token_ids_to_query)
        )

        # Apply date filters
        if start_date:
            start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            stmt = stmt.where(ExternalAuditLog.created_at >= start_dt)
        if end_date:
            end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
            stmt = stmt.where(ExternalAuditLog.created_at <= end_dt)

        # Group and order
        stmt = stmt.group_by('usage_date').order_by('usage_date')

        # Execute query
        results = db.execute(stmt).all()

        # Format response
        time_series_data = [
            TimeSeriesDataPoint(date=row.usage_date.date(), usage_count=row.usage_count)
            for row in results
        ]

        return TimeSeriesResponse(time_series=time_series_data)

    except HTTPException as http_exc:
        raise http_exc # Re-raise validation/auth errors
    except Exception as e:
        logger.error(f"Failed to get token usage time series for user '{current_user.email}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve token usage time series data."
        )
# --- END ADDED Time Series Route ---

# ==========================================
# Standard User-Facing Token Management API (Routes with path params come AFTER)
# ==========================================

# GET /token/ - List tokens for the current user
@router.get("/", response_model=List[TokenResponse])
async def read_user_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all API tokens for the authenticated user."""
    try:
        db_tokens = get_user_tokens(db, owner_email=current_user.email)
        response_list = []
        for token in db_tokens:
             # Use the corrected helper function
             try:
                 response_list.append(token_db_to_response(token))
             except Exception as inner_e:
                 logger.error(f"Error processing token ID {getattr(token, 'id', 'UNKNOWN')}: {inner_e}", exc_info=True)
                 # Optionally skip or add placeholder on error

        return response_list
    except Exception as e:
        logger.error(f"Failed to list tokens for user '{current_user.email}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API tokens."
        )

# POST /token/ - Create a new token for the current user
@router.post("/", response_model=TokenCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_token_route(
    token_in: TokenCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new API token for the authenticated user."""
    try:
        logger.info(f"Creating token '{token_in.name}' for user '{current_user.email}'")
        # Await the async CRUD function
        db_token = await create_user_token(
            db=db, 
            token_data=token_in, 
            owner_email=current_user.email
        )
        
        # Prepare response using TokenCreateResponse, including raw token value
        raw_token_value = getattr(db_token, 'token_value', '[Error Retrieving Token]')
        # Use the helper function for consistent response formatting
        response_data = token_db_to_response(db_token)
        # Add the raw token value ONLY for the create response
        return TokenCreateResponse(**response_data.model_dump(), token_value=raw_token_value)

    except Exception as e:
        logger.error(f"Failed to create token for user '{current_user.email}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API token."
        )

# GET /token/{token_id} - Get a specific token by ID
@router.get("/{token_id}", response_model=TokenResponse)
async def read_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_token = get_token_by_id(db, token_id=token_id)
    if db_token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    if db_token.owner_email != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return token_db_to_response(db_token)

# PATCH /token/{token_id} - Update a token
@router.patch("/{token_id}", response_model=TokenResponse)
async def update_token_route(
    token_id: int,
    token_in: TokenUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update an API token owned by the authenticated user."""
    try:
        # Verify ownership (sync operation)
        db_token_check = get_token_by_id(db, token_id=token_id)
        if not db_token_check or db_token_check.owner_email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found or you do not own this token."
            )
        
        # Await the async update function
        updated_token = await update_user_token(
            db=db, token_id=token_id, token_update_data=token_in
        )
        if not updated_token:
             # This case should ideally not happen if the check above passed, but good for safety
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found during update attempt."
            )

        logger.info(f"User '{current_user.email}' updated token ID {token_id}")
        # Use the helper function for consistent response formatting
        return token_db_to_response(updated_token)

    except HTTPException as http_exc:
        raise http_exc # Re-raise 404s etc.
    except Exception as e:
        logger.error(f"Failed to update token ID {token_id} for user '{current_user.email}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API token."
        )

# DELETE /token/{token_id} - Delete a token
@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete an API token owned by the authenticated user."""
    try:
        # Verify ownership before deleting
        db_token = get_token_by_id(db, token_id=token_id)
        if not db_token or db_token.owner_email != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found or you do not own this token."
            )
        
        deleted = delete_user_token(db=db, token_id=token_id)
        if not deleted:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found during deletion attempt."
            )
        logger.info(f"User '{current_user.email}' deleted token ID {token_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException as http_exc: 
        raise http_exc # Re-raise 404s etc.
    except Exception as e:
        logger.error(f"Failed to delete token ID {token_id} for user '{current_user.email}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete API token."
        )

# ==========================================
# Token Bundling API
# ==========================================

# POST /token/bundle - Create a new token by bundling existing ones
@router.post("/bundle", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_bundled_token_route(
    bundle_request: TokenBundleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Creates a new, non-editable token by bundling the rules and sensitivity of existing tokens."""
    logger.info(f"User {current_user.email} requesting to bundle tokens: {bundle_request.token_ids}")
    try:
        # 1. Prepare the bundled data using the CRUD function
        bundle_data = prepare_bundled_token_data(
            db=db, 
            token_ids=bundle_request.token_ids, 
            owner_email=current_user.email
        )
        
        # 2. Create the new bundled token in the database
        new_bundled_token = create_bundled_token(
            db=db,
            name=bundle_request.name,
            description=bundle_request.description,
            owner_email=current_user.email,
            bundle_data=bundle_data
        )

        # 3. Convert to response model (using existing helper)
        # Note: token_db_to_response includes the raw token value set in create_bundled_token
        return token_db_to_response(new_bundled_token)

    except ValueError as ve:
        logger.warning(f"Token bundling validation failed for user {current_user.email}: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error during token bundling for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create bundled token.")

# ==========================================
# Internal/Middleware Export Endpoint
# ==========================================

@router.get("/export/active/", 
            response_model=List[TokenExport], 
            tags=["token-export"], 
            summary="Export Active Tokens for Middleware",
            description="Provides a list of all active tokens with their rules for middleware consumption. Requires internal authentication.",
            include_in_schema=False # Optionally hide from public Swagger UI
            )
async def export_active_tokens(
    db: Session = Depends(get_db),
    requesting_user: User = Depends(get_current_active_user)
):
    """Exports all active tokens (unexpired, is_active=True) for the authenticated user.
    Accessible via user session or Bearer token authentication.
    """
    # The dependency ensures we have a valid user (either from session or token owner)
    # Now, fetch tokens owned by that user
    user_tokens = get_user_tokens(db, owner_email=requesting_user.email)
    
    active_tokens_export = []
    now = datetime.now(timezone.utc)
    
    for token in user_tokens:
        is_expired = token.expiry is not None and token.expiry <= now
        if token.is_active and not is_expired:
            # Manually reconstruct the TokenExport model as we don't store raw token value
            # We need to retrieve the raw value (which isn't ideal, see note below)
            # OR - we should return the HASHED value if the intent is for verification
            # For now, let's assume we *can't* return the raw value easily and return hash
            # NOTE: The client consuming this would need to know how to handle the hash
            #       or the requirement needs re-evaluation.
            # A better approach might be *not* to export the value itself, only metadata.
            active_tokens_export.append(TokenExport(
                # Construct TokenExport correctly using _topics
                id=token.id, 
                hashed_token=token.hashed_token, 
                sensitivity=token.sensitivity,
                owner_email=token.owner_email,
                is_active=token.is_active,
                allow_topics=token.allow_topics or [], # Use topics, provide default
                deny_topics=token.deny_topics or []     # Use topics, provide default
            ))
            
    return active_tokens_export

# ==========================================
# Helper Function
# ==========================================

def token_db_to_response(token_db: TokenDB) -> TokenResponse:
    """Converts a TokenDB database object to a TokenResponse API model, handling potential missing fields for older tokens."""
    if not token_db:
        raise ValueError("Cannot convert None TokenDB object to response.")

    try:
        hashed = token_db.hashed_token
        token_preview_value = f"{hashed[:4]}...{hashed[-4:]}" if hashed and len(hashed) > 8 else "[Invalid Hash]"

        # Construct the input dictionary for validation, using getattr for new/optional fields
        response_data = {
            "id": token_db.id,
            "name": token_db.name,
            "description": token_db.description,
            "sensitivity": token_db.sensitivity,
            "token_preview": token_preview_value,
            "owner_email": token_db.owner_email,
            "created_at": token_db.created_at,
            "expiry": token_db.expiry,
            "is_active": token_db.is_active,
            "is_editable": getattr(token_db, 'is_editable', True), # Default to True if missing
            "allow_rules": getattr(token_db, 'allow_rules', []), # Default to empty list
            "deny_rules": getattr(token_db, 'deny_rules', []),   # Default to empty list
            # V3 fields - Provide defaults if missing from older records
            "token_type": getattr(token_db, 'token_type', TokenType.PUBLIC), # Default to PUBLIC if missing
            "provider_base_url": getattr(token_db, 'provider_base_url', None),
            "audience": getattr(token_db, 'audience', None),
            "accepted_by": getattr(token_db, 'accepted_by', None),
            "accepted_at": getattr(token_db, 'accepted_at', None),
            "can_export_vectors": getattr(token_db, 'can_export_vectors', False), # Default to False if missing
            "allow_columns": getattr(token_db, 'allow_columns', None), # Default to None (allow all) if missing
            "allow_attachments": getattr(token_db, 'allow_attachments', None), # Default to None (allow all) if missing
            "row_limit": getattr(token_db, 'row_limit', None) # Default to None (no limit) if missing
            # NOTE: We no longer include allow/deny_embeddings here as they are not in TokenResponse
        }

        # Validate the dictionary to create the TokenResponse object
        response = TokenResponse.model_validate(response_data)

        # Ensure list fields that exist on TokenResponse are never None (already handled by getattr defaults)
        # response.allow_rules = response.allow_rules or []
        # response.deny_rules = response.deny_rules or []
        # response.allow_columns = response.allow_columns or [] # Not needed if default is None
        # response.allow_attachments = response.allow_attachments or [] # Not needed if default is None

        return response
    except Exception as e:
        token_id = getattr(token_db, 'id', 'UNKNOWN')
        logger.error(f"Error converting TokenDB ID {token_id} to TokenResponse: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing token data for token ID {token_id}."
        ) 

# --- NEW Endpoint for Testing Token Search --- 

class TestSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The search query string to test.")

# Define potential error responses for documentation
TEST_SEARCH_RESPONSES = {
    401: {"description": "Unauthorized: User not authenticated."},
    403: {"description": "Forbidden: User does not own the specified token, or token is inactive/expired."},
    404: {"description": "Not Found: Token ID not found, or Milvus collection for owner not found."},
    422: {"description": "Validation Error: Invalid input query."},
    500: {"description": "Internal Server Error."},
}

@router.post(
    "/{token_id}/test-search", 
    response_model=List[SharedMilvusResult], 
    summary="Test Token Search Permissions (Milvus Only)",
    description="""
Allows the token owner to test the search results returned for a specific token 
against their own Milvus knowledge base, applying the token's permissions.

Authentication requires a valid user session (cookie/JWT).

**Note:** This simulates the filtering applied by the public `/shared-knowledge/search` endpoint 
but operates on the owner's data and uses the owner's authentication.
    """,
    responses=TEST_SEARCH_RESPONSES
)
async def test_token_search(
    token_id: int,
    request_body: TestSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user), # Authenticate the user making the request
    milvus_client: MilvusClient = Depends(get_milvus_client)
):
    logger.info(f"User {current_user.email} initiating test search for token ID {token_id} with query: '{request_body.query}'")

    # 1. Fetch the token
    token = get_token_by_id(db, token_id=token_id)
    if not token:
        logger.warning(f"Test search failed: Token ID {token_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found.")

    # 2. Verify ownership
    if token.owner_email != current_user.email:
        logger.warning(f"Test search forbidden: User {current_user.email} does not own token ID {token_id} (Owner: {token.owner_email}).")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not own this token.")
        
    # 3. Verify token is active/valid (optional but recommended for meaningful test)
    now = datetime.now(timezone.utc)
    is_expired = token.expiry is not None and token.expiry <= now
    if not token.is_active or is_expired:
        status_detail = "expired" if is_expired else "inactive"
        logger.warning(f"Test search blocked: Token ID {token_id} is {status_detail}.")
        # Use 403 to indicate the token itself is unusable, even for testing
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Token is {status_detail} and cannot be tested.")

    # 4. Perform the search logic (adapted from /shared-knowledge/search)
    try:
        # Determine target collection based on token owner (which is the current_user)
        sanitized_email = token.owner_email.replace('@', '_').replace('.', '_')
        target_collection_name = f"{sanitized_email}_knowledge_base_bm"
        logger.info(f"Test search targeting collection: {target_collection_name}")

        # Generate embedding for the query
        query_embedding = await create_embedding(request_body.query)
        if not query_embedding:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Test search failed: Could not generate query embedding.")

        # Generate Milvus filter based on the specific token being tested
        milvus_filter_expression = create_milvus_filter_from_token(token)
        logger.debug(f"Test search using Milvus filter for token {token.id}: {milvus_filter_expression}")

        # Perform the search - Use a reasonable limit for testing, but respect token limit
        # Maybe use a fixed test limit or make it configurable?
        # Let's use the token's row_limit, capped at a reasonable max (e.g., 100)
        test_limit = min(token.row_limit, 100) 
        logger.debug(f"Test search performing Milvus search with effective limit: {test_limit}")
        
        results = await search_milvus_knowledge(
            collection_name=target_collection_name,
            query_texts=[request_body.query],
            limit=test_limit, # Use the calculated test limit
            filter_expr=milvus_filter_expression
        )

        # Log the raw results from Milvus search before processing
        # Use INFO level to ensure visibility
        logger.info(f"Raw results received from search_milvus_knowledge: {results}") 

        dense_search_results = results[0] if results and isinstance(results, list) and len(results) > 0 else []
        logger.info(f"Test search initial dense search found {len(dense_search_results)} results. Reranking...")

        # Rerank the results
        reranked_results = await rerank_results(query=request_body.query, results=dense_search_results)
        logger.info(f"Test search reranking complete. Found {len(reranked_results)} results before applying token projections.")

        # Apply Token Scope: Column Projection and Attachment Filtering
        processed_results = []
        essential_keys = ['id', 'score']
        attachment_keys = ['attachments', 'attachment_info', 'files', 'file_data']
        # Counters not strictly needed for test response, but logic is reused
        column_block_count = 0
        attachment_redaction_count = 0 

        for result in reranked_results:
            processed_result = {}
            metadata = result.get('metadata', {}) # Safely get metadata
            original_metadata_keys = set(metadata.keys())

            for key in essential_keys:
                if key in result:
                    processed_result[key] = result[key]

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
            else:
                filtered_metadata = metadata.copy()

            if not token.allow_attachments:
                keys_before_filter = set(filtered_metadata.keys())
                for attach_key in attachment_keys:
                    if attach_key in filtered_metadata:
                        del filtered_metadata[attach_key]
                if len(keys_before_filter.intersection(attachment_keys)) > 0:
                    attachment_redaction_count += 1

            processed_result['metadata'] = filtered_metadata
            # Validate against the response model field before adding
            # Although FastAPI handles response model validation, adding check here for clarity
            if SharedMilvusResult.model_validate(processed_result, strict=False): # Use strict=False if needed
                processed_results.append(processed_result)
            else:
                 logger.warning(f"Test search skipped result due to validation failure against SharedMilvusResult: {processed_result}")

        final_limited_results = processed_results # Already limited by test_limit

        logger.info(f"Test search for token {token.id} returning {len(final_limited_results)} processed results.")
        return final_limited_results

    except HTTPException as http_exc:
        # Re-raise specific exceptions (like 404 from search_milvus_knowledge if collection missing)
        raise http_exc 
    except Exception as e:
        logger.error(f"Error during test search for token {token_id} (Owner: {current_user.email}): {e}", exc_info=True)
        # Check for specific Milvus collection not found error like in the other endpoint
        target_collection_name_on_error = f"{token.owner_email.replace('@','_').replace('.','_')}_knowledge_base_bm"
        if "collection not found" in str(e).lower() and target_collection_name_on_error in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge base collection for token owner not found.")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during the test search.")

# --- End NEW Endpoint --- 