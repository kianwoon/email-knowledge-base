import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Placeholder for user dependency - replace with your actual user dependency
from ..dependencies.auth import get_current_active_user # Assuming this provides a user object with an 'id'
from ..models.user import User # Assuming your user model is defined here

# Placeholder for DB session dependency
from ..db.session import get_db

# Placeholder for the new model
from ..models.jarvis_token import JarvisExternalToken

# Placeholder for the encryption service
from ..services.encryption_service import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/jarvis/external-tokens",
    tags=["Jarvis Settings"],
    responses={404: {"description": "Not found"}},
)

# --- Pydantic Schemas --- 

class JarvisTokenBase(BaseModel):
    token_nickname: str = Field(..., min_length=1, max_length=255, description="User-friendly name for the token")
    endpoint_url: str = Field(..., min_length=1, max_length=512, description="The API endpoint URL where this token will be used")

class JarvisTokenCreate(JarvisTokenBase):
    raw_token_value: str = Field(..., min_length=1, description="The actual secret token value")

class JarvisTokenDisplay(JarvisTokenBase):
    id: int
    created_at: datetime
    last_used_at: datetime | None = None
    is_valid: bool

    class Config:
        orm_mode = True # Compatibility with SQLAlchemy models

# --- API Endpoints --- 

@router.post(
    "", 
    response_model=JarvisTokenDisplay,
    status_code=status.HTTP_201_CREATED,
    summary="Add an External Token for Jarvis",
    description="Adds a new external API token for the current user to be used by Jarvis."
)
def add_external_token(
    token_in: JarvisTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"User {current_user.id} attempting to add external token: {token_in.token_nickname}")
    
    # Check for duplicate nickname for this user (optional, if DB constraint doesn't handle it well)
    existing_token = db.query(JarvisExternalToken).filter(
        JarvisExternalToken.user_id == current_user.id, 
        JarvisExternalToken.token_nickname == token_in.token_nickname
    ).first()
    if existing_token:
        logger.warning(f"User {current_user.id} tried to add token with duplicate nickname: {token_in.token_nickname}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A token with this nickname already exists."
        )

    try:
        encrypted_value = encrypt_token(token_in.raw_token_value)
    except Exception as e:
        logger.error(f"Failed to encrypt token for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to securely store the token."
        )
    
    db_token = JarvisExternalToken(
        user_id=current_user.id,
        token_nickname=token_in.token_nickname,
        encrypted_token_value=encrypted_value,
        endpoint_url=token_in.endpoint_url,
        is_valid=True # Assume valid initially
    )
    
    try:
        db.add(db_token)
        db.commit()
        db.refresh(db_token)
        logger.info(f"Successfully added external token ID {db_token.id} for user {current_user.id}")
        return db_token
    except Exception as e: # Catch potential DB errors (like constraint violations)
        db.rollback()
        logger.error(f"Database error adding token for user {current_user.id}: {e}", exc_info=True)
        # Check if it was the unique constraint we defined
        if "uq_user_token_nickname" in str(e).lower():
             raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail="A token with this nickname already exists."
             )
        else:
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save the token to the database."
             )

@router.get(
    "", 
    response_model=List[JarvisTokenDisplay],
    summary="List External Tokens for Jarvis",
    description="Retrieves a list of all external tokens added by the current user."
)
def list_external_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    logger.debug(f"User {current_user.id} requesting list of external tokens.")
    tokens = db.query(JarvisExternalToken).filter(JarvisExternalToken.user_id == current_user.id).order_by(JarvisExternalToken.created_at.desc()).all()
    # Response model JarvisTokenDisplay ensures the encrypted value is not returned
    return tokens

@router.delete(
    "/{token_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an External Token",
    description="Deletes an external token previously added by the current user."
)
def delete_external_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"User {current_user.id} attempting to delete external token ID: {token_id}")
    
    token_to_delete = db.query(JarvisExternalToken).filter(
        JarvisExternalToken.id == token_id,
        JarvisExternalToken.user_id == current_user.id # Ensure user owns the token
    ).first()
    
    if not token_to_delete:
        logger.warning(f"User {current_user.id} failed to delete token ID {token_id}: Not found or not owned.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found or you do not have permission to delete it."
        )
        
    try:
        db.delete(token_to_delete)
        db.commit()
        logger.info(f"Successfully deleted external token ID {token_id} for user {current_user.id}")
        # No content is returned on successful DELETE
        return None # FastAPI handles the 204 status code
    except Exception as e:
        db.rollback()
        logger.error(f"Database error deleting token ID {token_id} for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete the token."
        )

# Remember to include this router in your main FastAPI app (e.g., in main.py)
# from app.routes import jarvis_settings
# app.include_router(jarvis_settings.router, prefix="/api/v1") 