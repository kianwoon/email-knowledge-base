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
    create_milvus_filter_from_token,
    regenerate_token_secret
)

# Import decryption utility
from ..utils.security import decrypt_token

# Import datetime for expiry check
from datetime import datetime, timezone, date, timedelta

# Import the new external model
from ..models.external_audit_log import ExternalAuditLog

# Import necessary types and functions
from sqlalchemy import func, select, text
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
    blocked_column_count: int = 0 # New field for P6

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

        # --- Query 1: Get Usage Count and Last Used --- 
        usage_stmt = select(
            ExternalAuditLog.token_id,
            func.count(ExternalAuditLog.id).label('usage_count'),
            func.max(ExternalAuditLog.created_at).label('last_used_at')
        ).where(
            ExternalAuditLog.token_id.in_(token_ids)
            # Optional: Add where clause for action_type != 'COLUMN_BLOCKED' if usage count shouldn't include block events
        )

        # Apply date filters to usage query
        if start_date:
            start_dt_usage = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            usage_stmt = usage_stmt.where(ExternalAuditLog.created_at >= start_dt_usage)
        if end_date:
            end_dt_usage = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
            usage_stmt = usage_stmt.where(ExternalAuditLog.created_at <= end_dt_usage)

        usage_stmt = usage_stmt.group_by(ExternalAuditLog.token_id)
        usage_result = db.execute(usage_stmt).all()
        usage_map = {row.token_id: {"usage_count": row.usage_count, "last_used_at": row.last_used_at} for row in usage_result}
        # --- End Query 1 --- 
        
        # --- Query 2: Get Blocked Column Count --- 
        # Temporarily disable action_type filter until DB schema is updated
        # NOTE: blocked_column_count will be 0 until `action_type` column is added to audit_logs
        blocked_stmt = select(
            ExternalAuditLog.token_id,
            text("0 as blocked_count") # Return 0 until action_type exists
            # func.count(ExternalAuditLog.id).label('blocked_count')
        ).where(
            ExternalAuditLog.token_id.in_(token_ids)
            # ExternalAuditLog.action_type == 'COLUMN_BLOCKED' # <-- Temporarily commented out
        )

        # Apply date filters to blocked count query
        if start_date:
            start_dt_blocked = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            blocked_stmt = blocked_stmt.where(ExternalAuditLog.created_at >= start_dt_blocked)
        if end_date:
            end_dt_blocked = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
            blocked_stmt = blocked_stmt.where(ExternalAuditLog.created_at <= end_dt_blocked)
            
        # Only need distinct token IDs if we are not actually counting
        blocked_stmt = blocked_stmt.distinct(ExternalAuditLog.token_id)
        # blocked_stmt = blocked_stmt.group_by(ExternalAuditLog.token_id)
        blocked_result = db.execute(blocked_stmt).all()
        # Initialize map with 0 for all tokens, as the query won't return actual counts yet
        blocked_map = {token_id: 0 for token_id in token_ids}
        # --- End Query 2 --- 

        # Build the response list, combining results from both queries
        usage_stats_list: List[TokenUsageStat] = []
        for token in owned_tokens:
            stats = usage_map.get(token.id)
            usage_count = stats["usage_count"] if stats else 0
            last_used_at = stats["last_used_at"] if stats else None
            blocked_column_count = blocked_map.get(token.id, 0) # Get count from blocked_map, default 0

            # Generate token_preview from token_prefix
            prefix = getattr(token, 'token_prefix', None) # Use getattr for safety
            token_preview_value = prefix if prefix else "[No Prefix]"

            usage_stats_list.append(
                TokenUsageStat(
                    token_id=token.id,
                    token_name=token.name,
                    token_description=token.description,
                    token_preview=token_preview_value,
                    usage_count=usage_count,
                    last_used_at=last_used_at,
                    blocked_column_count=blocked_column_count # Include the new count
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
        
        # Use the helper function for consistent response formatting
        response_data = token_db_to_response(db_token)
        
        # Check if token_value is already in the response_data
        if hasattr(response_data, 'token_value') and response_data.token_value:
            return TokenCreateResponse.model_validate(response_data)
        else:
            # Add the raw token value ONLY for the create response if it's missing
            raw_token_value = getattr(db_token, 'token_value', '[Error Retrieving Token]')
            
            # Get the model dump and remove token_value if it exists to avoid duplicate
            response_dict = response_data.model_dump()
            if 'token_value' in response_dict:
                response_dict.pop('token_value')
                
            return TokenCreateResponse(
                **response_dict,
                token_value=raw_token_value
            )

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
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve details of a specific token by its ID."""
    token_db = get_token_by_id(db, token_id=token_id)
    if not token_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Token not found"
        )

    # --- ADDED: Logic to include full token value for owner --- 
    full_token_value: Optional[str] = None
    if token_db.owner_email == current_user.email:
        logger.debug(f"User {current_user.email} is owner of token {token_id}. Attempting to construct full token.") 
        if token_db.token_prefix and token_db.hashed_secret:
            try:
                # Check if it's a bcrypt hash (starts with $2b$)
                if token_db.hashed_secret.startswith('$2b$'):
                    logger.info(f"Token {token_id} uses bcrypt hash which cannot be decrypted. Using prefix-only mode for owner.")
                    # For bcrypt hashed tokens, owner can use prefix-only access mode
                    # Return just the prefix instead of full value
                    full_token_value = token_db.token_prefix
                    # Add an error message to indicate bcrypt cannot be decrypted
                    response.headers["X-Token-Error"] = "Token uses bcrypt hash which cannot be decrypted"
                else:
                    # Normal case, attempt to decrypt
                    decrypted_secret = decrypt_token(token_db.hashed_secret)
                    if decrypted_secret is None:
                        # Decryption failed, log and don't include token value
                        logger.error(f"Failed to decrypt secret for token {token_id} owned by {current_user.email}. Decryption returned None.")
                    else:
                        # Successfully decrypted, build full token value
                        full_token_value = f"{token_db.token_prefix}.{decrypted_secret}"
                        logger.debug(f"Successfully constructed full token value for owner. Length: {len(full_token_value)}, Preview: {full_token_value[:10]}...")
            except Exception as e:
                # Log error but don't fail the request, just don't return the value
                logger.error(f"Failed to decrypt secret for token {token_id} owned by {current_user.email}: {e}", exc_info=True)
    # --- END ADDED ---

    # Return the response, passing the full_token_value if constructed
    # Pydantic will automatically handle converting token_db attributes
    # and including token_value if it's not None.
    return TokenResponse(
        **token_db.__dict__, 
        token_value=full_token_value,
        token_preview=token_db.token_prefix or "[No Prefix]" # Ensure token_preview is always present
    )

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
        # Use token_prefix for the preview
        prefix = token_db.token_prefix
        # If prefix exists, use it directly. Otherwise, show an indicator.
        token_preview_value = prefix if prefix else "[No Prefix]"

        # Construct the input dictionary for validation, using getattr for new/optional fields
        response_data = {
            "id": token_db.id,
            "name": token_db.name,
            "description": token_db.description,
            "sensitivity": token_db.sensitivity,
            "token_preview": token_preview_value, # Use the prefix
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

    # 1. Fetch the token and verify ownership
    token = get_token_by_id(db, token_id=token_id)
    if not token:
        logger.warning(f"Test search failed: Token ID {token_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    if token.owner_email != current_user.email:
        logger.warning(f"Test search denied: User {current_user.email} does not own token {token_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this token.")
    if not token.is_active:
        logger.warning(f"Test search failed: Token ID {token_id} is inactive.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is inactive.")

    # 2. Determine the target Milvus collection for the owner
    # Directly generate the collection name from the user's email
    sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
    collection_name = f"{sanitized_email}_knowledge_base_bm"
    logger.info(f"Test search targeting collection: {collection_name}")

    # 3. Create Milvus filter expression based on token rules
    milvus_filter_expression = create_milvus_filter_from_token(token)
    logger.debug(f"Test search using Milvus filter: {milvus_filter_expression}")

    # 4. Search Milvus using the user's collection and token's filter
    try:
        # Search Milvus (uses BAAI/bge-m3 for embedding by default)
        results = await search_milvus_knowledge(
            query_texts=[request_body.query],
            collection_name=collection_name,
            limit=100, # Increase limit for initial retrieval before reranking/filtering
            filter_expr=milvus_filter_expression
        )

        # Log the raw results received, EXCLUDING content for brevity
        if logger.isEnabledFor(logging.DEBUG):
            try:
                results_for_log = []
                for result_list in results: # Results is List[List[Dict]]
                    log_list = []
                    for hit_dict in result_list:
                        if isinstance(hit_dict, dict):
                            log_hit = {k: v for k, v in hit_dict.items() if k != 'content'}
                            log_list.append(log_hit)
                        else:
                            log_list.append(hit_dict)
                    results_for_log.append(log_list)
                logger.debug(f"Results received from search_milvus_knowledge (content excluded): {results_for_log}")
            except Exception as log_e:
                logger.warning(f"Could not exclude content field from results log: {log_e}")
                logger.debug(f"Original results received from search_milvus_knowledge: {results}") # Fallback
        # logger.debug(f"Raw results received from search_milvus_knowledge: {results}") # Old log

        dense_search_results = results[0] if results and isinstance(results, list) and len(results) > 0 else []
        logger.info(f"Test search initial dense search found {len(dense_search_results)} results. Reranking...")

        # 5. Rerank the results
        reranked_results = await rerank_results(query=request_body.query, results=dense_search_results)
        logger.info(f"Test search reranking complete. Found {len(reranked_results)} results before applying token allow/deny rules.")

        # --- START: Apply Allow Rule Filtering ---
        allowed_results = []
        allow_keywords = []
        apply_allow_filter = False # Flag to check if allow rules are active

        if token.allow_rules:
            raw_rules = token.allow_rules
            try:
                if isinstance(raw_rules, str):
                    # Attempt to parse if it's a string
                    allow_keywords = json.loads(raw_rules)
                elif isinstance(raw_rules, list):
                    # Use directly if it's already a list
                    allow_keywords = raw_rules
                else:
                    logger.warning(f"Token {token.id} allow_rules has unexpected type: {type(raw_rules)}. Ignoring.")
                    allow_keywords = []

                # Now validate if we have a non-empty list
                if isinstance(allow_keywords, list) and allow_keywords:
                    apply_allow_filter = True
                    allow_keywords = [str(keyword).lower() for keyword in allow_keywords]
                    logger.info(f"Applying allow keywords: {allow_keywords}")
                elif isinstance(allow_keywords, list): # It was an empty list
                     logger.info(f"Token {token.id} allow_rules is an empty list. No allow filtering applied.")
                     allow_keywords = []
                else: # Parsing failed or resulted in non-list
                    logger.warning(f"Token {token.id} allow_rules parsed, but is not a list: {allow_keywords}. Ignoring.")
                    allow_keywords = []
                    apply_allow_filter = False

            except json.JSONDecodeError:
                logger.warning(f"Token {token.id} allow_rules string could not be parsed as JSON: {raw_rules}. Ignoring allow rules.")
                allow_keywords = []
                apply_allow_filter = False

        if apply_allow_filter:
            for result in reranked_results:
                content_lower = result.get('content', '').lower()
                is_allowed = False
                for keyword in allow_keywords:
                    if keyword in content_lower:
                        is_allowed = True
                        break # Found an allowed keyword, keep this result
                if is_allowed:
                    allowed_results.append(result)
                # else: logger.debug(f"Filtering out result ID {result.get('id')} because it doesn't match allow keywords: {allow_keywords}") # Optional debug log
            logger.info(f"Applied allow rules. Kept {len(allowed_results)} out of {len(reranked_results)} results.")
        else:
            # No allow rules to apply, pass all reranked results through
            allowed_results = reranked_results
            logger.info("No active allow rules to apply.")
        # --- END: Apply Allow Rule Filtering ---


        # --- START: Apply Deny Rule Filtering (operates on allowed_results) ---
        filtered_results = []
        deny_keywords = []
        if token.deny_rules:
            raw_rules = token.deny_rules # Use a temporary variable
            try:
                if isinstance(raw_rules, str):
                     # Attempt to parse if it's a string
                    deny_keywords = json.loads(raw_rules)
                elif isinstance(raw_rules, list):
                     # Use directly if it's already a list
                    deny_keywords = raw_rules
                else:
                    logger.warning(f"Token {token.id} deny_rules has unexpected type: {type(raw_rules)}. Ignoring.")
                    deny_keywords = []

                # Now validate if we have a list (could be empty)
                if isinstance(deny_keywords, list):
                    # Convert all keywords to lowercase for case-insensitive matching
                    deny_keywords = [str(keyword).lower() for keyword in deny_keywords]
                    if deny_keywords: # Log only if there are keywords to apply
                        logger.info(f"Applying deny keywords: {deny_keywords}")
                else:
                    logger.warning(f"Token {token.id} deny_rules parsed, but is not a list: {deny_keywords}. Ignoring.")
                    deny_keywords = []

            except json.JSONDecodeError:
                logger.warning(f"Token {token.id} deny_rules string could not be parsed as JSON: {raw_rules}. Ignoring deny rules.")
                deny_keywords = []

        if deny_keywords:
            results_before_deny = len(allowed_results) # Log based on input to this stage
            for result in allowed_results: # Iterate through results that passed the allow filter
                content_lower = result.get('content', '').lower()
                is_denied = False
                for keyword in deny_keywords:
                    if keyword in content_lower:
                        is_denied = True
                        logger.debug(f"Filtering out result ID {result.get('id')} due to deny keyword '{keyword}'.")
                        break # No need to check other keywords for this result
                if not is_denied:
                    filtered_results.append(result)
            logger.info(f"Applied deny rules. Kept {len(filtered_results)} out of {results_before_deny} results (after allow filter).")
        else:
            # No deny rules or invalid format, use all results that passed the allow filter
            filtered_results = allowed_results
            logger.info("No active deny rules to apply.")
        # --- END: Apply Deny Rule Filtering ---


        # 6. Apply token projection (select specific fields) - NOW ON FINAL filtered_results
        projected_results = []
        allowed_fields = set(getattr(token, 'allowed_fields', None) or SharedMilvusResult.model_fields.keys())
        # Always include 'id' and 'score' if available, regardless of allowed_fields, for basic identification
        base_fields = {'id', 'score'}
        fields_to_include = base_fields.union(allowed_fields)

        for result in filtered_results: # Use filtered_results here
            projected_data = {
                field: result.get(field)
                for field in fields_to_include
                if field in result # Only include if the field actually exists in the result
            }
            # Ensure score is present if possible
            if 'score' not in projected_data and 'distance' in result:
                projected_data['score'] = result['distance']

            # Validate against the response model before appending
            try:
                projected_results.append(SharedMilvusResult(**projected_data))
            except Exception as pydantic_error:
                 logger.warning(f"Skipping result due to validation error after projection: {pydantic_error}. Original data: {result}, Projected: {projected_data}", exc_info=True)


        logger.info(f"Test search for token {token_id} returning {len(projected_results)} processed results.")
        return projected_results

    except HTTPException as http_exc:
        logger.error(f"HTTP exception during test search for token {token_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error during test search for token {token_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the test search."
        )

# --- End NEW Endpoint --- 

# --- NEW RESPONSE MODEL for REGENERATION ---
class RegenerateTokenResponse(BaseModel):
    new_token_value: str = Field(..., description="The new full token value (prefix.secret) generated.")

# --- NEW ENDPOINT: Regenerate Token Secret ---
@router.post(
    "/{token_id}/regenerate",
    response_model=RegenerateTokenResponse,
    summary="Regenerate Secret for an API Token",
    description="""Generates a new secret for the specified token, invalidating the old one. \
Returns the new full token value (prefix.new_secret). \
This is the ONLY time the new secret will be shown. \
Requires ownership of the token. \
Cannot be used on non-editable or bundled tokens.""",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Token not found"},
        403: {"description": "User does not own this token or token type cannot be regenerated"},
        400: {"description": "Validation error (e.g., token has no prefix)"},
        500: {"description": "Internal server error during regeneration"}
    }
)
async def regenerate_token_secret_route(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Call the CRUD function to handle regeneration logic
        regeneration_result = await regenerate_token_secret(
            db=db, 
            token_id=token_id, 
            owner_email=current_user.email
        )
        
        # Construct the full new token string
        new_full_token = f"{regeneration_result['token_prefix']}.{regeneration_result['new_secret']}"
        
        logger.info(f"Secret regenerated for token {token_id}. Returning new token value to user {current_user.email}.")
        return RegenerateTokenResponse(new_token_value=new_full_token)

    except ValueError as ve:
        # Handle specific errors from CRUD function (Not Found, Forbidden, Bad Request)
        if "not found" in str(ve).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
        elif "does not own" in str(ve).lower() or "cannot be regenerated" in str(ve).lower() or "not editable" in str(ve).lower():
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(ve))
        else: # Other ValueErrors (like missing prefix)
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        # Catch potential DB errors from CRUD or other unexpected issues
        logger.error(f"Failed to regenerate secret for token {token_id} via API: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate token secret."
        )
# --- END NEW ENDPOINT --- 

# --- NEW ENDPOINT for Token Value Debugging ---
@router.get(
    "/{token_id}/debug-token-value",
    summary="Debug Token Value Format",
    description="Debug endpoint to validate token value format (owner only)",
    include_in_schema=False # Hide from docs
)
async def debug_token_value(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Debug endpoint to check token value format."""
    # Get the token
    token_db = get_token_by_id(db, token_id=token_id)
    if not token_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Token not found"
        )
    
    # Verify ownership 
    if token_db.owner_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only token owner can debug token value"
        )
    
    # Get the token components
    full_token_value = None
    try:
        if token_db.token_prefix and token_db.hashed_secret:
            decrypted_secret = decrypt_token(token_db.hashed_secret)
            full_token_value = f"{token_db.token_prefix}.{decrypted_secret}"
            
            # Log and return the token details
            logger.info(f"Debug token value for ID {token_id}:")
            logger.info(f"- Prefix: {token_db.token_prefix}")
            logger.info(f"- Secret: {decrypted_secret}")
            logger.info(f"- Full token: {full_token_value}")
            
            return {
                "token_id": token_id,
                "prefix": token_db.token_prefix,
                "secret_length": len(decrypted_secret),
                "full_token_length": len(full_token_value),
                "contains_period": "." in full_token_value,
                "period_position": full_token_value.find("."),
                "components_valid": bool(token_db.token_prefix and decrypted_secret)
            }
    except Exception as e:
        logger.error(f"Error debugging token {token_id}: {e}", exc_info=True)
        return {
            "token_id": token_id,
            "error": str(e)
        }
# --- END DEBUG ENDPOINT --- 