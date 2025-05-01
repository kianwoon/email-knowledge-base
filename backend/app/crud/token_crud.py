from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func as sql_func
from typing import List, Optional, Dict, Any, Set
import uuid
import bcrypt
import secrets
from datetime import datetime, timezone, timedelta
import logging
import json
import asyncio
# Import embedding function (adjust path if needed)
from app.services.embedder import create_embedding

from ..models.token_models import TokenDB, TokenCreateRequest, TokenUpdateRequest, TokenType # Added TokenType
from ..models.user import UserDB # Assuming UserDB is needed for other functions
from ..config import settings # Assuming settings might be needed elsewhere
from app.models.email import EmailAnalysis # Adjust import path if needed

# Configure logging
logger = logging.getLogger(__name__)

# Define the order of sensitivity levels (lowest to highest)
# Ensure this matches the levels used elsewhere (e.g., token models)
SENSITIVITY_ORDER = ["public", "internal", "confidential", "strict-confidential"]
SENSITIVITY_RANK = {level: i for i, level in enumerate(SENSITIVITY_ORDER)}

# --- Helper to generate embeddings safely ---
async def _generate_embeddings_for_rules(rules: Optional[List[str]]) -> Optional[List[Any]]:
    if not rules:
        return None
    embeddings = []
    try:
        tasks = [create_embedding(rule) for rule in rules]
        embeddings = await asyncio.gather(*tasks)
        logger.info(f"Generated {len(embeddings)} embeddings for {len(rules)} rules.")
    except Exception as e:
        logger.error(f"Failed to generate embeddings for rules: {rules}. Error: {e}", exc_info=True)
        # Decide handling: return None? Empty list? Raise error?
        # Returning None for now to avoid partial embeddings
        return None 
    return embeddings

def get_token_by_id(db: Session, token_id: int) -> Optional[TokenDB]: # Changed token_id type to int
    """Fetches a single token by its ID.

    Args:
        db: The database session.
        token_id: The ID of the token to fetch.

    Returns:
        The TokenDB object if found, otherwise None.
    """
    return db.get(TokenDB, token_id)

# REMOVED the old inefficient get_token_by_value function
# def get_token_by_value(db: Session, token_value: str) -> Optional[TokenDB]: ...

# +++ ADDED efficient lookup by prefix +++
def get_token_by_prefix(db: Session, token_prefix: str) -> Optional[TokenDB]:
    """
    Fetches a single token efficiently by its unique prefix.
    Assumes the 'token_prefix' column is indexed and unique.
    """
    statement = select(TokenDB).where(TokenDB.token_prefix == token_prefix)
    result = db.execute(statement).scalar_one_or_none()
    return result
# --- END ADDITION ---

def get_user_tokens(db: Session, owner_email: str) -> List[TokenDB]:
    """Fetches all tokens owned by a specific user."""
    statement = select(TokenDB).where(TokenDB.owner_email == owner_email).order_by(TokenDB.created_at.desc())
    results = db.execute(statement).scalars().all()
    return results

async def create_user_token(db: Session, token_data: TokenCreateRequest, owner_email: str) -> TokenDB:
    """Creates a new token for a user, handling v3 fields and using prefix/secret strategy.""" # Updated docstring
    
    # 1. Generate Prefix (ensure uniqueness might require a loop/check in rare cases, relying on DB constraint for now)
    prefix = f"kb_{secrets.token_hex(4)}" # e.g., kb_a1b2c3d4
    
    # 2. Generate Secret Part
    secret_part = secrets.token_urlsafe(32) # Keep secret length reasonable
    
    # 3. Hash ONLY the secret part
    hashed_secret = bcrypt.hashpw(secret_part.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    expiry_datetime = None
    if token_data.expiry_days is not None and token_data.expiry_days > 0:
        try:
            expiry_datetime = datetime.now(timezone.utc) + timedelta(days=int(token_data.expiry_days))
        except (ValueError, TypeError):
            logger.warning(f"Invalid expiry_days value: {token_data.expiry_days}. Setting expiry to None.")
            expiry_datetime = None

    # Generate embeddings from rules - NO embeddings created when saving to collection (as per rules)
    # allow_rules = token_data.allow_rules or []
    # deny_rules = token_data.deny_rules or []
    # allow_embeddings_db = await _generate_embeddings_for_rules(allow_rules)
    # deny_embeddings_db = await _generate_embeddings_for_rules(deny_rules)

    db_token = TokenDB(
        name=token_data.name,
        description=token_data.description,
        sensitivity=token_data.sensitivity,
        # --- Store prefix and hashed secret ---
        token_prefix=prefix,          # Store the generated prefix
        hashed_secret=hashed_secret,   # Store the hash of the secret part
        # --- End storage change ---
        owner_email=owner_email,
        expiry=expiry_datetime,
        is_active=True,
        is_editable=token_data.is_editable,
        allow_rules=token_data.allow_rules or [], 
        deny_rules=token_data.deny_rules or [],
        # Do not store embeddings upon creation
        allow_embeddings=None,
        deny_embeddings=None,
        # --- NEW v3 Fields ---
        token_type=token_data.token_type, 
        provider_base_url=token_data.provider_base_url if token_data.token_type == TokenType.SHARE else None,
        audience=token_data.audience,
        # accepted_by/at are set when a receiver accepts a share token, not on creation
        can_export_vectors=token_data.can_export_vectors,
        allow_columns=token_data.allow_columns,
        allow_attachments=token_data.allow_attachments,
        row_limit=token_data.row_limit,
        # --- End NEW v3 Fields ---
    )
    try:
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
    except Exception as e:
        db.rollback()
        # Handle potential unique constraint violation on prefix (rare)
        if "UniqueViolationError" in str(e) or "duplicate key value violates unique constraint" in str(e).lower():
             logger.error(f"Token prefix collision for prefix '{prefix}'. This should be rare. Consider retry logic if frequent.")
             # Reraise or handle as appropriate, maybe raise HTTPException 500?
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate unique token prefix. Please try again.") from e
        else:
             logger.error(f"Database error creating token: {e}", exc_info=True)
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during token creation.") from e


    # 4. Construct the full token to return ONLY ONCE
    full_token_value = f"{prefix}_{secret_part}"
    setattr(db_token, 'token_value', full_token_value) # Attach raw token for the response model

    return db_token

async def update_user_token(db: Session, token_id: int, token_update_data: TokenUpdateRequest) -> Optional[TokenDB]:
    """Updates an existing token, handling v3 fields. Does NOT regenerate embeddings.""" # Updated docstring
    db_token = db.get(TokenDB, token_id)
    if not db_token:
        logger.warning(f"Attempted to update non-existent token ID {token_id}.")
        return None

    if not db_token.is_editable:
        logger.warning(f"Attempted to update non-editable token ID {token_id}.")
        # Consider raising an HTTPException(status_code=403, detail="Token is not editable") here
        return None # Or raise error

    update_data = token_update_data.model_dump(exclude_unset=True)
    # needs_embedding_update = False # Embedding regeneration removed

    # Handle expiry_days update separately
    new_expiry_datetime = db_token.expiry # Keep existing expiry by default
    if 'expiry_days' in update_data:
        expiry_days = update_data.pop('expiry_days') # Remove from main update dict
        if expiry_days is not None:
            if expiry_days > 0:
                try:
                    new_expiry_datetime = datetime.now(timezone.utc) + timedelta(days=int(expiry_days))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid expiry_days value during update: {expiry_days}. Expiry not changed.")
                    new_expiry_datetime = db_token.expiry # Revert to original on error
            else: # 0 or negative means clear expiry
                 new_expiry_datetime = None
        # If expiry_days is None in update_data, expiry is unchanged
        setattr(db_token, 'expiry', new_expiry_datetime)

    # Apply remaining updates
    for key, value in update_data.items():
        # if key in ["allow_rules", "deny_rules"]:
            # needs_embedding_update = True # Embedding regeneration removed
        if key == "provider_base_url" and db_token.token_type != TokenType.SHARE:
            logger.warning(f"Cannot set provider_base_url for non-share token ID {token_id}. Skipping field.")
            continue # Skip setting provider_base_url if not a share token
        if hasattr(db_token, key):
             setattr(db_token, key, value)
        else:
             logger.warning(f"Attempted to update unknown field '{key}' on token ID {token_id}.")

    # Embedding regeneration removed based on project rules
    # if needs_embedding_update:
    #    logger.info(f"Rules updated for token {token_id}, regenerating embeddings...")
    #    allow_embeddings_new = await _generate_embeddings_for_rules(db_token.allow_rules)
    #    deny_embeddings_new = await _generate_embeddings_for_rules(db_token.deny_rules)
    #    if allow_embeddings_new is not None:
    #         setattr(db_token, 'allow_embeddings', allow_embeddings_new)
    #    if deny_embeddings_new is not None:
    #         setattr(db_token, 'deny_embeddings', deny_embeddings_new)

    try:
        db.commit()
        db.refresh(db_token)
        logger.info(f"Successfully updated token ID {token_id}.")
        return db_token
    except Exception as e:
        logger.error(f"Database error updating token ID {token_id}: {e}", exc_info=True)
        db.rollback()
        return None

def delete_user_token(db: Session, token_id: int) -> bool:
    """Soft deletes a token by setting its is_active flag to False."""
    try:
        db_token = db.get(TokenDB, token_id)
        if db_token:
            # Instead of deleting, set is_active to False
            db_token.is_active = False
            db.commit()
            logger.info(f"Soft deleted token ID {token_id}.")
            return True
        else:
             logger.warning(f"Attempted to soft delete non-existent token ID {token_id}.")
             return False # Token not found
    except Exception as e:
         logger.error(f"Error during soft delete of token ID {token_id}: {e}", exc_info=True)
         db.rollback() # Rollback transaction on error
         return False

def get_active_tokens(db: Session) -> List[TokenDB]:
    """Fetches all tokens that are currently active (not expired and is_active=True)."""
    now = datetime.now(timezone.utc)
    statement = select(TokenDB).where(
        TokenDB.is_active == True,
        (TokenDB.expiry == None) | (TokenDB.expiry > now)
    )
    results = db.execute(statement).scalars().all()
    return results

# --- Token Bundling Logic Helper --- 

def _union_string_lists(string_lists: List[Optional[List[str]]]) -> List[str]:
    # Union for rules/embeddings: Combine all items into a set and back to list
    combined_set: Set[str] = set()
    for lst in string_lists:
        if lst:
            combined_set.update(lst)
    return sorted(list(combined_set))

# --- Token Bundling Logic ---

def prepare_bundled_token_data(db: Session, token_ids: List[int], owner_email: str) -> Dict[str, Any]: # Changed token_ids type to List[int]
    """
    Fetches tokens, validates them, and calculates the combined rules, embeddings, and sensitivity for bundling.
    Raises ValueError if validation fails.
    """
    if not token_ids:
        raise ValueError("No token IDs provided for bundling.")

    tokens_to_bundle: List[TokenDB] = []
    now = datetime.now(timezone.utc)

    for token_id in token_ids:
        token = get_token_by_id(db, token_id)
        if not token:
            raise ValueError(f"Token with ID {token_id} not found.")
        if token.owner_email != owner_email:
            raise ValueError(f"Token {token.id} does not belong to the requesting user.")
        is_expired = token.expiry is not None and token.expiry <= now
        if not token.is_active or is_expired:
            raise ValueError(f"Token {token.id} is not active or has expired.")
        tokens_to_bundle.append(token)

    if not tokens_to_bundle:
        raise ValueError("No valid tokens found to bundle.")

    # Determine highest sensitivity
    highest_sensitivity_rank = -1
    highest_sensitivity_level = SENSITIVITY_ORDER[0]
    for token in tokens_to_bundle:
        rank = SENSITIVITY_RANK.get(token.sensitivity, -1)
        if rank > highest_sensitivity_rank:
            highest_sensitivity_rank = rank
            highest_sensitivity_level = token.sensitivity

    # Extract rules and embeddings lists
    allow_rule_sets = [token.allow_rules for token in tokens_to_bundle]
    deny_rule_sets = [token.deny_rules for token in tokens_to_bundle]
    # Note: Bundling generated embeddings might be complex/undesirable. 
    # For now, we only bundle the rules themselves.
    # allow_embedding_sets = [token.allow_embeddings for token in tokens_to_bundle]
    # deny_embedding_sets = [token.deny_embeddings for token in tokens_to_bundle]

    combined_allow_rules = _union_string_lists(allow_rule_sets)
    combined_deny_rules = _union_string_lists(deny_rule_sets)
    # Bundled token will generate its own embeddings upon creation

    return {
        "sensitivity": highest_sensitivity_level,
        "allow_rules": combined_allow_rules,
        "deny_rules": combined_deny_rules,
        # Do not include pre-combined embeddings in bundle data
    }

async def create_bundled_token(db: Session, name: str, description: Optional[str], owner_email: str, bundle_data: Dict[str, Any]) -> TokenDB:
    """Creates a new, non-editable token based on bundled data, generating new embeddings."""
    raw_token_value = secrets.token_urlsafe(32)
    hashed_value = bcrypt.hashpw(raw_token_value.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Generate embeddings for the combined rules
    allow_rules = bundle_data.get('allow_rules', [])
    deny_rules = bundle_data.get('deny_rules', [])
    allow_embeddings_db = await _generate_embeddings_for_rules(allow_rules)
    deny_embeddings_db = await _generate_embeddings_for_rules(deny_rules)

    db_token = TokenDB(
        name=name,
        description=description,
        hashed_secret=hashed_value,
        sensitivity=bundle_data['sensitivity'],
        owner_email=owner_email,
        expiry=None,
        is_editable=False,
        is_active=True,
        allow_rules=allow_rules,
        deny_rules=deny_rules,
        allow_embeddings=allow_embeddings_db,
        deny_embeddings=deny_embeddings_db,
        bundled_from=bundle_data.get('original_token_ids') # Store original IDs if passed in bundle_data
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)

    setattr(db_token, 'token_value', raw_token_value)
    return db_token

# --- NEW FUNCTION FOR MILVUS ---
def create_milvus_filter_from_token(token: TokenDB) -> Optional[str]:
    """
    Creates a Milvus boolean filter expression string based on token rules.
    Assumes fields like 'sensitivity' and 'department' are top-level or directly accessible.
    """
    filter_parts = []

    # --- Sensitivity Filtering ---
    token_rank = SENSITIVITY_RANK.get(token.sensitivity, -1)
    if token_rank < 0:
        logger.warning(f"Token {token.id} has invalid sensitivity '{token.sensitivity}'. Applying most restrictive filter (no results).")
        return 'pk == "impossible_value"' 

    allowed_levels = SENSITIVITY_ORDER[:token_rank + 1]
    if not allowed_levels:
        return 'pk == "impossible_value"'

    allowed_levels_str = ", ".join([f'"{level}"' for level in allowed_levels])
    # CORRECTED: Assume 'sensitivity' is a top-level field
    filter_parts.append(f'sensitivity in [{allowed_levels_str}]')

    # --- Department Filtering (Allow Rules) ---
    # CORRECTED: Assume 'department' is a top-level field
    if token.allow_rules:
        allowed_departments_str = ", ".join([f'"{dept}"' for dept in token.allow_rules])
        # Filter based on top-level 'department' field
        filter_parts.append(f'department in [{allowed_departments_str}]')

    # --- Deny Rules --- (Still omitted as per previous logic)
    if token.deny_rules:
         logger.warning(f"Token {token.id} has deny_rules, but Milvus filter generation currently does not support semantic denial based on rules.")

    # Combine conditions with 'and'
    if not filter_parts:
        return "" # Return empty string for no filters

    final_filter = " and ".join(filter_parts)
    logger.debug(f"Generated Milvus filter expression for token {token.id}: {final_filter}")
    return final_filter

# --- End Helper --- 

# --- NEW FUNCTION: Regenerate Token Secret ---
async def regenerate_token_secret(db: Session, token_id: int, owner_email: str) -> Dict[str, str]:
    """Regenerates the secret part of a token, hashes it, and updates the DB.
    If the token is missing a prefix (older token), generates one during this process.

    Args:
        db: Database session.
        token_id: The ID of the token to regenerate.
        owner_email: The email of the user requesting regeneration (for verification).

    Returns:
        A dictionary containing the 'token_prefix' and the 'new_secret' (unhashed).

    Raises:
        ValueError: If the token is not found, not owned by the user,
                    or is not marked as editable.
        Exception: For database errors.
    """
    try:
        # Fetch the existing token
        db_token = get_token_by_id(db, token_id=token_id)
        if not db_token:
            raise ValueError("Token not found.")
        if db_token.owner_email != owner_email:
            raise ValueError("User does not own this token.")
        # Assuming PUBLIC and SHARE types *can* be regenerated
        if not getattr(db_token, 'is_editable', True):
             raise ValueError("Token is not marked as editable.")
        
        prefix_to_use = db_token.token_prefix
        prefix_was_generated = False

        # If prefix is missing (old token), generate one now
        if not prefix_to_use:
             logger.warning(f"Token {token_id} is missing prefix. Generating one during regeneration.")
             prefix_to_use = f"kb_{secrets.token_hex(4)}" 
             db_token.token_prefix = prefix_to_use # Update the model instance directly
             prefix_was_generated = True
             # Add a DB check/retry loop here if prefix collisions become a problem

        # Generate a new secret
        new_secret = secrets.token_urlsafe(32) # Generate a new 32-byte URL-safe secret
        hashed_new_secret = bcrypt.hashpw(new_secret.encode('utf-8'), bcrypt.gensalt())

        # Update the database
        db_token.hashed_secret = hashed_new_secret.decode('utf-8') # Store as string
        # token_prefix is already updated on the instance if it was generated
        
        db.add(db_token) # Add the updated instance to the session
        db.commit()    # Commit the changes (saves new prefix and secret)
        db.refresh(db_token) # Refresh to get any DB-side changes

        if prefix_was_generated:
             logger.info(f"Successfully regenerated secret and generated new prefix '{prefix_to_use}' for token ID {token_id}.")
        else:
             logger.info(f"Successfully regenerated secret for token ID {token_id} (prefix '{prefix_to_use}').")

        # Return the prefix (existing or newly generated) and the NEW UNHASHED secret
        return {
            "token_prefix": prefix_to_use,
            "new_secret": new_secret
        }

    except ValueError as ve: # Re-raise specific validation errors
        logger.warning(f"Token regeneration validation failed for token {token_id}, user {owner_email}: {ve}")
        raise ve
    except Exception as e:
        db.rollback() # Rollback on error
        logger.error(f"Database error during token secret regeneration for token {token_id}: {e}", exc_info=True)
        # Check for unique constraint violation on prefix if it was generated
        if prefix_was_generated and ("UniqueViolationError" in str(e) or "duplicate key value violates unique constraint" in str(e).lower()):
             logger.error(f"Token prefix collision for newly generated prefix '{prefix_to_use}'. This should be rare. Consider retry logic.")
             # Reraise a more specific error or a generic one
             raise Exception("Failed to generate unique token prefix during regeneration. Please try again.") from e
        raise Exception("Failed to regenerate token secret due to database error.") from e
# --- END NEW FUNCTION --- 