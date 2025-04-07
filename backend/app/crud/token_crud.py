from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from typing import List, Optional
import uuid
import bcrypt
import secrets
from datetime import datetime, timezone

from ..models.token_models import TokenDB, TokenCreateRequest, TokenUpdateRequest, AccessRule

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