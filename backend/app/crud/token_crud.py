from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from typing import List, Optional, Dict, Any, Set
import uuid
import bcrypt
import secrets
from datetime import datetime, timezone
from qdrant_client import models as qdrant_models # Import Qdrant models

from ..models.token_models import TokenDB, TokenCreateRequest, TokenUpdateRequest, AccessRule

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

def create_user_token(db: Session, token_data: TokenCreateRequest, owner_email: str) -> TokenDB:
    """Creates a new token for a user."""
    raw_token_value = secrets.token_urlsafe(32)
    hashed_value = bcrypt.hashpw(raw_token_value.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    db_token = TokenDB(
        id=uuid.uuid4(),
        name=token_data.name,
        description=token_data.description,
        hashed_token=hashed_value,
        sensitivity=token_data.sensitivity,
        owner_email=owner_email,
        expiry=token_data.expiry,
        is_editable=token_data.is_editable,
        is_active=True,
        allow_rules=rules_to_db_format(token_data.allow_rules),
        deny_rules=rules_to_db_format(token_data.deny_rules),
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    
    setattr(db_token, 'token_value', raw_token_value)
    
    return db_token

def update_user_token(db: Session, token_id: uuid.UUID, token_update_data: TokenUpdateRequest) -> Optional[TokenDB]:
    """Updates an existing token."""
    # No need to convert UUID for PostgreSQL WHERE clause
    statement = (
        update(TokenDB)
        .where(TokenDB.id == token_id) # Use UUID object directly
        # Ensure we are only updating allowed fields from TokenUpdateRequest
        .values(**token_update_data.dict(exclude_unset=True, exclude={'allow_rules', 'deny_rules'})) # Exclude rules initially
        .returning(TokenDB)
    )
    
    # Handle rules separately if they are present in the update data
    update_payload = token_update_data.dict(exclude_unset=True)
    rule_update_values = {}
    if 'allow_rules' in update_payload:
        rule_update_values['allow_rules'] = rules_to_db_format(token_update_data.allow_rules)
    if 'deny_rules' in update_payload:
        rule_update_values['deny_rules'] = rules_to_db_format(token_update_data.deny_rules)
        
    if rule_update_values:
         statement = statement.values(**rule_update_values)

    # Always update the updated_at timestamp
    statement = statement.values(updated_at=datetime.now(timezone.utc))

    try:
        result = db.execute(statement).scalar_one_or_none()
        if result:
            db.commit()
            return result
        else:
            db.rollback()
            # Re-fetch to check if it existed but wasn't editable (though route should check first)
            # Use the string version of the ID for the check as well
            existing = get_token_by_id(db, token_id) # get_token_by_id already handles string conversion
            if existing and not existing.is_editable:
                 raise ValueError("Token is not editable")
            return None # Not found
    except Exception as e:
        db.rollback()
        print(f"Error during token update: {e}") 
        raise

def delete_user_token(db: Session, token_id: uuid.UUID) -> bool:
    """Deletes a token by its ID. Returns True if deleted, False otherwise."""
    # No need to convert UUID for PostgreSQL WHERE clause
    statement = delete(TokenDB).where(TokenDB.id == token_id) # Use UUID object directly
    result = db.execute(statement)
    db.commit()
    return result.rowcount > 0

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