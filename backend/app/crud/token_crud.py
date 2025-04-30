from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
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

from ..models.token_models import TokenDB, TokenCreateRequest, TokenUpdateRequest # Removed AccessRule
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

def get_token_by_value(db: Session, token_value: str) -> Optional[TokenDB]:
    """Fetches a single token by its raw value by checking the stored hash."""
    all_tokens = db.execute(select(TokenDB)).scalars().all()
    for token in all_tokens:
        hashed_token_bytes = token.hashed_token.encode('utf-8') if isinstance(token.hashed_token, str) else token.hashed_token
        if bcrypt.checkpw(token_value.encode('utf-8'), hashed_token_bytes):
            return token
    return None

def get_user_tokens(db: Session, owner_email: str) -> List[TokenDB]:
    """Fetches all tokens owned by a specific user."""
    statement = select(TokenDB).where(TokenDB.owner_email == owner_email).order_by(TokenDB.created_at.desc())
    results = db.execute(statement).scalars().all()
    return results

async def create_user_token(db: Session, token_data: TokenCreateRequest, owner_email: str) -> TokenDB:
    """Creates a new token for a user, generating embeddings from rules."""
    raw_token_value = secrets.token_urlsafe(32)
    hashed_value = bcrypt.hashpw(raw_token_value.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    expiry_datetime = None
    if hasattr(token_data, 'expiry_days') and token_data.expiry_days is not None and token_data.expiry_days > 0:
        try:
            expiry_datetime = datetime.now(timezone.utc) + timedelta(days=int(token_data.expiry_days))
        except (ValueError, TypeError):
            logger.warning(f"Invalid expiry_days value: {token_data.expiry_days}. Setting expiry to None.")
            expiry_datetime = None

    # Generate embeddings from rules
    allow_rules = token_data.allow_rules or []
    deny_rules = token_data.deny_rules or []
    
    allow_embeddings_db = await _generate_embeddings_for_rules(allow_rules)
    deny_embeddings_db = await _generate_embeddings_for_rules(deny_rules)

    db_token = TokenDB(
        name=token_data.name,
        description=token_data.description,
        sensitivity=token_data.sensitivity,
        hashed_token=hashed_value,
        owner_email=owner_email,
        expiry=expiry_datetime,
        is_active=True,
        is_editable=token_data.is_editable,
        allow_rules=allow_rules, 
        deny_rules=deny_rules,
        allow_embeddings=allow_embeddings_db, # Save generated embeddings
        deny_embeddings=deny_embeddings_db   # Save generated embeddings
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)

    setattr(db_token, 'token_value', raw_token_value)
    return db_token

async def update_user_token(db: Session, token_id: int, token_update_data: TokenUpdateRequest) -> Optional[TokenDB]:
    """Updates an existing token, regenerating embeddings if rules change."""
    db_token = db.get(TokenDB, token_id)
    if not db_token:
        return None

    update_data = token_update_data.model_dump(exclude_unset=True)
    needs_embedding_update = False

    for key, value in update_data.items():
        if key == "allow_rules":
            setattr(db_token, key, value)
            needs_embedding_update = True
        elif key == "deny_rules":
            setattr(db_token, key, value)
            needs_embedding_update = True
        else:
            setattr(db_token, key, value)

    if needs_embedding_update:
        logger.info(f"Rules updated for token {token_id}, regenerating embeddings...")
        allow_embeddings_new = await _generate_embeddings_for_rules(db_token.allow_rules)
        deny_embeddings_new = await _generate_embeddings_for_rules(db_token.deny_rules)
        if allow_embeddings_new is not None:
             setattr(db_token, 'allow_embeddings', allow_embeddings_new)
        if deny_embeddings_new is not None:
             setattr(db_token, 'deny_embeddings', deny_embeddings_new)

    db.commit()
    db.refresh(db_token)
    return db_token

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
        hashed_token=hashed_value,
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
    Assumes metadata is stored within a 'metadata_json' field in Milvus.
    """
    filter_parts = []

    # --- Sensitivity Filtering ---
    # Assuming sensitivity is stored in metadata_json.sensitivity
    token_rank = SENSITIVITY_RANK.get(token.sensitivity, -1)
    if token_rank < 0:
        logger.warning(f"Token {token.id} has invalid sensitivity '{token.sensitivity}'. Applying most restrictive filter (no results).")
        # Return a filter that matches nothing, e.g., check a non-existent value
        return 'pk == "impossible_value"' # Use pk for a definite non-match

    allowed_levels = SENSITIVITY_ORDER[:token_rank + 1]
    if not allowed_levels:
        # Should not happen with valid rank, but safety check
        return 'pk == "impossible_value"'

    # Create an 'in' condition for allowed sensitivity levels
    # Ensure proper quoting for string values in the list
    allowed_levels_str = ", ".join([f'"{level}"' for level in allowed_levels])
    # IMPORTANT: Assuming sensitivity is stored at the top level of metadata_json
    filter_parts.append(f'metadata_json["sensitivity"] in [{allowed_levels_str}]')

    # --- Department Filtering (Allow Rules) ---
    # IMPORTANT: Assuming departments are stored as a list OR single string
    # in metadata_json.department
    if token.allow_rules:
        # Create an 'in' condition for allowed department strings
        # Ensure proper quoting for string values in the list
        allowed_departments_str = ", ".join([f'"{dept}"' for dept in token.allow_rules])
        # IMPORTANT: Assuming department is stored at the top level of metadata_json
        filter_parts.append(f'metadata_json["department"] in [{allowed_departments_str}]')

        # Alternate if department is a list within JSON (e.g., ["sales", "emea"])
        # Requires Milvus support for JSON array checks (e.g., json_contains)
        # Make sure the field metadata_json.department is indexed appropriately if using this.
        # conditions = [f'json_contains(metadata_json["department"], \\"{dept}\\")' for dept in token.allow_rules]
        # filter_parts.append(f'({" or ".join(conditions)})')


    # --- Deny Rules ---
    # Milvus filters primarily work on scalar or array fields within the JSON or top-level fields.
    # Filtering based on semantic *denial* (deny_rules/embeddings) is complex and not directly
    # supported by simple filter expressions. We will omit deny rules for now.
    if token.deny_rules:
         logger.warning(f"Token {token.id} has deny_rules, but Milvus filter generation currently does not support semantic denial based on rules.")


    # Combine conditions with 'and'
    if not filter_parts:
        return "" # Return empty string for no filters

    final_filter = " and ".join(filter_parts)
    logger.debug(f"Generated Milvus filter expression for token {token.id}: {final_filter}")
    return final_filter

# --- End Helper --- 