from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from typing import List, Optional, Dict, Any, Set
import uuid
import bcrypt
import secrets
from datetime import datetime, timezone, timedelta
from qdrant_client import models as qdrant_models # Import Qdrant models
import logging
import json
import asyncio
from app.services.embedder import create_embedding

from ..models.token_models import TokenDB, TokenCreateRequest, TokenUpdateRequest, AccessRule, TokenCreate, TokenUpdate
from ..models.user import UserDB # Assuming UserDB is needed for other functions
from ..config import settings # Assuming settings might be needed elsewhere

# Configure logging
logger = logging.getLogger(__name__)

# Define the order of sensitivity levels (lowest to highest)
# Ensure this matches the levels used elsewhere (e.g., token models)
SENSITIVITY_ORDER = ["public", "internal", "confidential", "strict-confidential"] 
SENSITIVITY_RANK = {level: i for i, level in enumerate(SENSITIVITY_ORDER)}

# Helper to convert list of model rules to list of dicts for DB
def rules_to_db_format(rules: Optional[List[AccessRule]]) -> List[dict]:
    if rules is None:
        return []
    return [rule.dict() for rule in rules]

# Helper to convert list of dicts from DB to list of model rules
def db_format_to_rules(db_rules: Optional[List[dict]]) -> List[AccessRule]:
    if db_rules is None:
        return []
    try:
        return [AccessRule(**rule) for rule in db_rules]
    except Exception:
        # Handle potential parsing errors, maybe log them
        return []

# --- Helper Functions for Rule Bundling --- 

def _intersect_allow_rules(rule_sets: List[List[AccessRule]]) -> List[AccessRule]:
    """Calculates the intersection of allow rules based on fields and values."""
    if not rule_sets: return []

    # Create a dictionary for each token's rules for easier lookup
    # { 'field_name': set(values), ... }
    parsed_rule_sets = []
    for rules in rule_sets:
        token_rules = {rule.field: set(rule.values) for rule in rules}
        parsed_rule_sets.append(token_rules)

    intersected_rules: List[AccessRule] = []
    first_token_rules = parsed_rule_sets[0]

    # Iterate through fields in the first token's rules
    for field, first_values in first_token_rules.items():
        field_present_in_all = True
        current_intersected_values = set(first_values) # Start intersection with the first set

        # Check this field against all other tokens
        for other_token_rules in parsed_rule_sets[1:]:
            if field not in other_token_rules:
                field_present_in_all = False
                break # Field must be in all tokens' allow rules to be considered
            # Perform intersection of values for this field
            current_intersected_values.intersection_update(other_token_rules[field])
            if not current_intersected_values:
                field_present_in_all = False # If intersection is empty, treat as not present
                break 
        
        # If field was present in all and intersection is not empty, add it
        if field_present_in_all:
            intersected_rules.append(AccessRule(field=field, values=sorted(list(current_intersected_values))))

    return intersected_rules

def _union_deny_rules(rule_sets: List[List[AccessRule]]) -> List[AccessRule]:
    """Calculates the union of deny rules based on fields and values."""
    if not rule_sets: return []

    # Aggregate all deny values per field
    # { 'field_name': set(values), ... }
    aggregated_denials: Dict[str, Set[str]] = {}

    for rules in rule_sets:
        for rule in rules:
            if rule.field not in aggregated_denials:
                aggregated_denials[rule.field] = set()
            aggregated_denials[rule.field].update(rule.values)

    # Create the final unioned rules
    unioned_rules: List[AccessRule] = []
    for field, values in aggregated_denials.items():
        if values:
            unioned_rules.append(AccessRule(field=field, values=sorted(list(values))))

    return unioned_rules

# --- End Helper Functions for Rule Bundling --- 

# --- Qdrant Filter Generation --- 

def create_qdrant_filter_from_token(token: TokenDB) -> qdrant_models.Filter:
    """
    Creates a Qdrant Filter object based on the token's sensitivity and rules.
    Assumes data points have metadata fields nested under a 'metadata' key (e.g., metadata.sensitivity).
    """
    filters = qdrant_models.Filter(must=[], must_not=[], should=[])

    # --- Helper to prepend metadata path --- 
    def get_metadata_key(field_name: str) -> str:
        # If the field already seems nested (though unlikely for rules), don't double-prefix
        if field_name.startswith("metadata."):
             return field_name
        return f"metadata.{field_name}"

    # 1. Sensitivity Filter:
    token_rank = SENSITIVITY_RANK.get(token.sensitivity)
    if token_rank is not None:
        allowed_sensitivity_levels = [level for level, rank in SENSITIVITY_RANK.items() if rank <= token_rank]
        if allowed_sensitivity_levels:
            # Use the nested key
            filters.must.append(
                qdrant_models.FieldCondition(key=get_metadata_key("sensitivity"), match=qdrant_models.MatchAny(any=allowed_sensitivity_levels))
            )
        else:
             filters.must.append(qdrant_models.FieldCondition(key="id", match=qdrant_models.MatchValue(value=str(uuid.uuid4())))) # Match non-existent ID

    # 2. Allow Rules
    allow_rules = db_format_to_rules(token.allow_rules)
    for rule in allow_rules:
        metadata_field_key = get_metadata_key(rule.field)
        # TODO: Refine based on actual metadata schema and desired logic (e.g., AND vs OR for multiple values).
        if rule.field == "tags" and isinstance(rule.values, list): # Assuming tags field needs AND logic (contains all)
             for value in rule.values:
                 filters.must.append(
                     qdrant_models.FieldCondition(key=metadata_field_key, match=qdrant_models.MatchValue(value=value))
                 )
        elif rule.values: # Simple match for first value in other fields
             filters.must.append(
                 qdrant_models.FieldCondition(key=metadata_field_key, match=qdrant_models.MatchValue(value=rule.values[0]))
             )

    # 3. Deny Rules
    deny_rules = db_format_to_rules(token.deny_rules)
    for rule in deny_rules:
        metadata_field_key = get_metadata_key(rule.field)
        # Deny if the field matches ANY of the specified values.
        filters.must_not.append(
            qdrant_models.FieldCondition(key=metadata_field_key, match=qdrant_models.MatchAny(any=rule.values))
        )

    return filters

# --- End Qdrant Filter Generation --- 

def get_token_by_id(db: Session, token_id: uuid.UUID) -> Optional[TokenDB]:
    """Fetches a single token by its UUID.
    
    Args:
        db: The database session.
        token_id: The UUID object of the token to fetch.
    
    Returns:
        The TokenDB object if found, otherwise None.
    """
    # No need to convert UUID for PostgreSQL
    return db.get(TokenDB, token_id)

def get_token_by_value(db: Session, token_value: str) -> Optional[TokenDB]:
    """Fetches a single token by its raw value by checking the stored hash."""
    # Proper way (if hashing is done on lookup):
    all_tokens = db.execute(select(TokenDB)).scalars().all() # Query TokenDB
    for token in all_tokens:
        # Ensure hashed_token is bytes if bcrypt expects bytes
        hashed_token_bytes = token.hashed_token.encode('utf-8') if isinstance(token.hashed_token, str) else token.hashed_token
        if bcrypt.checkpw(token_value.encode('utf-8'), hashed_token_bytes):
            return token
    return None

def get_user_tokens(db: Session, owner_email: str) -> List[TokenDB]:
    """Fetches all tokens owned by a specific user."""
    statement = select(TokenDB).where(TokenDB.owner_email == owner_email).order_by(TokenDB.created_at.desc()) # Query TokenDB
    results = db.execute(statement).scalars().all()
    return results

async def create_user_token(db: Session, token_data: TokenCreate, owner_email: str) -> TokenDB:
    """Creates a new token for a user, including topic embeddings."""
    raw_token_value = secrets.token_urlsafe(32) 
    hashed_value = bcrypt.hashpw(raw_token_value.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Removed outdated embedding generation logic based on allow/deny_topics

    db_token = TokenDB(
        name=token_data.name,
        description=token_data.description,
        sensitivity=token_data.sensitivity,
        hashed_token=hashed_value,
        owner_email=owner_email,
        expiry=getattr(token_data, 'expiry', None),
        is_active=True, 
        # Use getattr for safety, default to None (handled by rules_to_db_format)
        allow_rules=rules_to_db_format(getattr(token_data, 'allow_rules', None)), 
        deny_rules=rules_to_db_format(getattr(token_data, 'deny_rules', None))   
    )
    db.add(db_token)
    # Commit synchronously after async operations are done
    db.commit() 
    db.refresh(db_token)
    
    # Temporarily attach the raw token value
    setattr(db_token, 'token_value', raw_token_value)
    
    return db_token

async def update_user_token(db: Session, token_id: int, token_update_data: TokenUpdate) -> Optional[TokenDB]:
    """Updates an existing token using the TokenUpdate model, including embeddings if topics change."""
    db_token = db.get(TokenDB, token_id)
    if not db_token:
        return None 

    update_data = token_update_data.model_dump(exclude_unset=True)
    
    regenerate_allow_embeddings = 'allow_topics' in update_data
    regenerate_deny_embeddings = 'deny_topics' in update_data

    # Update standard attributes first
    for key, value in update_data.items():
        setattr(db_token, key, value)
        
    # --- Regenerate Embeddings if Topics Changed ---
    if regenerate_allow_embeddings:
        new_allow_topics = update_data['allow_topics']
        if new_allow_topics:
            logger.info(f"Regenerating embeddings for {len(new_allow_topics)} updated allow_topics...")
            allow_tasks = [create_embedding(topic) for topic in new_allow_topics]
            db_token.allow_topics_embeddings = await asyncio.gather(*allow_tasks)
            logger.info("Finished regenerating allow_topics embeddings.")
        else:
            db_token.allow_topics_embeddings = None # Clear embeddings if topics are cleared

    if regenerate_deny_embeddings:
        new_deny_topics = update_data['deny_topics']
        if new_deny_topics:
            logger.info(f"Regenerating embeddings for {len(new_deny_topics)} updated deny_topics...")
            deny_tasks = [create_embedding(topic) for topic in new_deny_topics]
            db_token.deny_topics_embeddings = await asyncio.gather(*deny_tasks)
            logger.info("Finished regenerating deny_topics embeddings.")
        else:
            db_token.deny_topics_embeddings = None # Clear embeddings if topics are cleared
    # --- End Embedding Regeneration ---
        
    # Commit synchronously after async operations
    db.commit()
    db.refresh(db_token)
    return db_token

def delete_user_token(db: Session, token_id: int) -> bool:
    """Deletes a token by its ID. Returns True if deleted, False otherwise."""
    db_token = db.get(TokenDB, token_id)
    if db_token:
        db.delete(db_token)
        db.commit()
        return True
    return False

def get_active_tokens(db: Session) -> List[TokenDB]:
    """Fetches all tokens that are currently active."""
    now = datetime.now(timezone.utc)
    # Use TokenDB in the select statement
    statement = select(TokenDB).where(
        TokenDB.is_active == True, 
        (TokenDB.expiry == None) | (TokenDB.expiry > now)
    )
    results = db.execute(statement).scalars().all()
    return results 

# --- Token Bundling Logic --- 

def prepare_bundled_token_data(db: Session, token_ids: List[uuid.UUID], owner_email: str) -> Dict[str, Any]:
    """
    Fetches tokens, validates them, and calculates the combined rules and sensitivity for bundling.
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
    highest_sensitivity_level = SENSITIVITY_ORDER[0] # Default to lowest
    for token in tokens_to_bundle:
        rank = SENSITIVITY_RANK.get(token.sensitivity, -1)
        if rank > highest_sensitivity_rank:
            highest_sensitivity_rank = rank
            highest_sensitivity_level = token.sensitivity

    # Extract rules and calculate combined rules
    allow_rule_sets = [db_format_to_rules(token.allow_rules) for token in tokens_to_bundle]
    deny_rule_sets = [db_format_to_rules(token.deny_rules) for token in tokens_to_bundle]

    combined_allow_rules = _intersect_allow_rules(allow_rule_sets)
    combined_deny_rules = _union_deny_rules(deny_rule_sets)

    return {
        "sensitivity": highest_sensitivity_level,
        "allow_rules": combined_allow_rules,
        "deny_rules": combined_deny_rules
    }

def create_bundled_token(db: Session, name: str, description: Optional[str], owner_email: str, bundle_data: Dict[str, Any]) -> TokenDB:
    """Creates a new, non-editable token based on bundled data."""
    raw_token_value = secrets.token_urlsafe(32)
    hashed_value = bcrypt.hashpw(raw_token_value.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    db_token = TokenDB(
        id=uuid.uuid4(),
        name=name,
        description=description,
        hashed_token=hashed_value,
        sensitivity=bundle_data['sensitivity'],
        owner_email=owner_email,
        expiry=None, # Bundled tokens do not inherit expiry
        is_editable=False, # Bundled tokens are NOT editable
        is_active=True,
        allow_rules=rules_to_db_format(bundle_data.get('allow_rules', [])),
        deny_rules=rules_to_db_format(bundle_data.get('deny_rules', [])),
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)

    # Set the raw token value for the response, similar to create_user_token
    setattr(db_token, 'token_value', raw_token_value)

    return db_token

# --- End Token Bundling Logic --- 