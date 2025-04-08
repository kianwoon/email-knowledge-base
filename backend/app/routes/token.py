# backend/app/routes/token.py
import logging
from uuid import UUID
from typing import List, Optional, Any
import json

from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session
import uuid

from ..services import token_service
from ..models.token import Token, TokenCreate, TokenUpdate
from ..models.user import User
from ..db.qdrant_client import get_qdrant_client
from ..dependencies.auth import get_current_active_user_or_token_owner
from ..db.session import get_db
from ..models.token_models import TokenResponse, TokenCreateRequest, TokenUpdateRequest, TokenExport, TokenDB, AccessRule, TokenBundleRequest
from ..crud.token_crud import (
    create_user_token, 
    get_user_tokens, 
    get_token_by_id, 
    update_user_token, 
    delete_user_token,
    get_active_tokens,
    prepare_bundled_token_data,
    create_bundled_token,
    db_format_to_rules
)

# Import datetime for expiry check
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["token"],
    responses={404: {"description": "Not found"}},
)

# ==========================================
# Standard User-Facing Token Management API
# ==========================================

# GET /token/ - List tokens for the current user
@router.get("/", response_model=List[TokenResponse])
async def read_user_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    db_tokens = get_user_tokens(db, owner_email=current_user.email)
    return [token_db_to_response(token) for token in db_tokens]

# POST /token/ - Create a new token for the current user
@router.post("/", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_token_route(
    token_in: TokenCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    # Ensure allow/deny rules are lists
    token_in.allow_rules = token_in.allow_rules or []
    token_in.deny_rules = token_in.deny_rules or []
    
    # Create token in DB
    db_token = create_user_token(db=db, token_data=token_in, owner_email=current_user.email)
    
    # Return the response model (helper adds the raw token value)
    return token_db_to_response(db_token)

# GET /token/{token_id} - Get a specific token by ID
@router.get("/{token_id}", response_model=TokenResponse)
async def read_token(
    token_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
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
    token_id: uuid.UUID,
    token_in: TokenUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    # Check ownership first
    db_token = get_token_by_id(db, token_id=token_id)
    if db_token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    if db_token.owner_email != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to edit this token")
    
    # Check if token is editable
    if not db_token.is_editable:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token is not editable")

    # Perform the update
    updated_token = update_user_token(db=db, token_id=token_id, token_update_data=token_in)
    if updated_token is None:
        # This case might be redundant if checks above are thorough
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found or update failed") 
    return token_db_to_response(updated_token)

# DELETE /token/{token_id} - Delete a token
@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    token_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
):
    # Check ownership first
    db_token = get_token_by_id(db, token_id=token_id)
    if db_token is None:
        # Return 204 even if not found, as the end state is the same (token doesn't exist)
        return 
    if db_token.owner_email != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to delete this token")

    # Perform deletion
    deleted = delete_user_token(db=db, token_id=token_id)
    if not deleted:
         # This case implies the token existed moments ago but couldn't be deleted (unlikely)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete token")
    return # Return 204 No Content on success

# ==========================================
# Token Bundling API
# ==========================================

# POST /token/bundle - Create a new token by bundling existing ones
@router.post("/bundle", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_bundled_token_route(
    bundle_request: TokenBundleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_or_token_owner)
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
    requesting_user: User = Depends(get_current_active_user_or_token_owner)
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
                name=token.name,
                description=token.description,
                # token_value=token.hashed_token, # Returning HASHED value for now
                # OR return a placeholder if value shouldn't be exported:
                token_value="**********", 
                sensitivity=token.sensitivity,
                owner_email=token.owner_email,
                expiry=token.expiry,
                allow_rules=db_format_to_rules(token.allow_rules),
                deny_rules=db_format_to_rules(token.deny_rules)
            ))
            
    return active_tokens_export

# --- Helper Function --- 
def db_format_to_rules(db_rules: Optional[Any]) -> List[AccessRule]:
    """Converts the stored rule format (likely JSON) into a list of AccessRule objects."""
    if not db_rules:
        return []
    
    parsed_rules = []
    try:
        # Attempt to parse if it's a JSON string, otherwise assume it's already parsed (e.g., by SQLAlchemy JSON type)
        if isinstance(db_rules, str):
            loaded_rules = json.loads(db_rules)
        else:
            loaded_rules = db_rules # Assumes it's already a list/dict structure
            
        if not isinstance(loaded_rules, list):
            logger.warning(f"Stored rules are not a list: {type(loaded_rules)}. Returning empty list.")
            return []

        for rule_dict in loaded_rules:
            if isinstance(rule_dict, dict):
                 try:
                    # Validate and create AccessRule object
                    parsed_rules.append(AccessRule(**rule_dict))
                 except Exception as validation_error: # Catch validation errors
                     logger.warning(f"Skipping invalid rule data during conversion: {rule_dict}. Error: {validation_error}")
            else:
                logger.warning(f"Skipping non-dictionary item in stored rules list: {rule_dict}")
                
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON rules from DB: {db_rules}")
        return [] # Return empty on decode error
    except Exception as e:
        logger.error(f"Error converting DB rules to AccessRule objects: {e}. Input: {db_rules}", exc_info=True)
        return [] # Return empty on other errors
        
    return parsed_rules

def token_db_to_response(token_db: TokenDB) -> TokenResponse:
    return TokenResponse(
        id=token_db.id,
        name=token_db.name,
        description=token_db.description,
        token_value=getattr(token_db, 'token_value', '********'), # Use getattr for safety
        sensitivity=token_db.sensitivity,
        created_at=token_db.created_at,
        updated_at=token_db.updated_at,
        expiry=token_db.expiry,
        is_editable=token_db.is_editable,
        is_active=token_db.is_active,
        allow_rules=db_format_to_rules(token_db.allow_rules),
        deny_rules=db_format_to_rules(token_db.deny_rules),
        owner_email=token_db.owner_email
    ) 