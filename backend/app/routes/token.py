# backend/app/routes/token.py
import logging
from uuid import UUID
from typing import List, Optional, Any, Dict
import json

from fastapi import APIRouter, Depends, HTTPException, status, Body, Request, Response, Query
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
import uuid

from ..services import token_service
from ..models.user import User
from ..db.qdrant_client import get_qdrant_client
from ..dependencies.auth import get_current_active_user_or_token_owner as get_request_user
from ..db.session import get_db
from ..models.token_models import (
    TokenResponse, TokenCreateRequest, TokenUpdateRequest, 
    TokenExport, TokenDB, TokenBundleRequest, 
    TokenCreateResponse
)
from ..crud.token_crud import (
    create_user_token, 
    get_user_tokens, 
    get_token_by_id, 
    update_user_token, 
    delete_user_token,
    get_active_tokens,
    prepare_bundled_token_data,
    create_bundled_token
)

# Import datetime for expiry check
from datetime import datetime, timezone, date, timedelta

# Import the new external model
from ..models.external_audit_log import ExternalAuditLog

# Import necessary types and functions
from sqlalchemy import func, select
from pydantic import BaseModel

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
    current_user: User = Depends(get_request_user)
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

# ==========================================
# Standard User-Facing Token Management API (Routes with path params come AFTER)
# ==========================================

# GET /token/ - List tokens for the current user
@router.get("/", response_model=List[TokenResponse])
async def read_user_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_request_user)
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
    current_user: User = Depends(get_request_user)
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
    current_user: User = Depends(get_request_user)
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
    current_user: User = Depends(get_request_user)
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
    current_user: User = Depends(get_request_user)
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
    current_user: User = Depends(get_request_user)
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
    requesting_user: User = Depends(get_request_user)
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
    """Converts a TokenDB database object to a TokenResponse API model."""
    if not token_db:
        raise ValueError("Cannot convert None TokenDB object to response.")

    try:
        hashed = token_db.hashed_token
        token_preview_value = f"{hashed[:4]}...{hashed[-4:]}" if hashed and len(hashed) > 8 else "[Invalid Hash]"

        # Construct the input dictionary for validation
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
            "allow_rules": token_db.allow_rules,
            "deny_rules": token_db.deny_rules,
            # Include embeddings in the input dict. Pydantic ignores fields not in the target model.
            "allow_embeddings": token_db.allow_embeddings, 
            "deny_embeddings": token_db.deny_embeddings, 
        }
        
        # Validate the dictionary to create the TokenResponse object
        response = TokenResponse.model_validate(response_data)

        # Ensure list fields *that exist on TokenResponse* are never None
        response.allow_rules = response.allow_rules or []
        response.deny_rules = response.deny_rules or []
        # DO NOT access response.allow_embeddings or response.deny_embeddings here

        return response
    except Exception as e:
        token_id = getattr(token_db, 'id', 'UNKNOWN')
        logger.error(f"Error converting TokenDB ID {token_id} to TokenResponse: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Internal error processing token data for token ID {token_id}."
        ) 