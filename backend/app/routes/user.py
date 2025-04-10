from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import logging

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User, UserDB
from app.utils.security import encrypt_token, decrypt_token  # Reuse the token encryption functions
from app.crud.user_crud import check_column_exists  # Import the column check function

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Define request/response models
class ApiKeyRequest(BaseModel):
    api_key: str

class ApiKeyResponse(BaseModel):
    api_key: Optional[str] = None

@router.post("/api-key", response_model=ApiKeyResponse)
async def save_openai_api_key(
    api_key_request: ApiKeyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Save the user's OpenAI API key to the database"""
    try:
        # Check if the openai_api_key column exists
        has_openai_api_key = check_column_exists(db, 'users', 'openai_api_key')
        if not has_openai_api_key:
            # If the column doesn't exist, we should run the migration
            logger.error("openai_api_key column does not exist in users table.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key storage not available. Database needs migration."
            )
            
        # Get user from database
        user_db = db.query(UserDB).filter(UserDB.email == current_user.email).first()
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database"
            )
        
        # Encrypt the API key before storing
        encrypted_api_key = encrypt_token(api_key_request.api_key)
        
        # Update user record with encrypted API key
        user_db.openai_api_key = encrypted_api_key
        db.commit()
        
        logger.info(f"OpenAI API key saved for user {current_user.email}")
        return ApiKeyResponse(api_key="*****")  # Return masked API key for confirmation
        
    except Exception as e:
        logger.error(f"Error saving OpenAI API key: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save API key: {str(e)}"
        )

@router.get("/api-key", response_model=ApiKeyResponse)
async def get_openai_api_key(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieve the user's OpenAI API key from the database"""
    try:
        # Check if the openai_api_key column exists
        has_openai_api_key = check_column_exists(db, 'users', 'openai_api_key')
        if not has_openai_api_key:
            # If the column doesn't exist, just return null
            logger.warning("openai_api_key column does not exist in users table.")
            return ApiKeyResponse(api_key=None)
            
        # Get user from database
        user_db = db.query(UserDB).filter(UserDB.email == current_user.email).first()
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database"
            )
        
        # Check if API key exists
        if not user_db.openai_api_key:
            return ApiKeyResponse(api_key=None)
        
        # Decrypt the API key
        decrypted_api_key = decrypt_token(user_db.openai_api_key)
        
        return ApiKeyResponse(api_key=decrypted_api_key)
        
    except Exception as e:
        logger.error(f"Error retrieving OpenAI API key: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve API key: {str(e)}"
        )

@router.delete("/api-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_openai_api_key(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete the user's OpenAI API key from the database"""
    try:
        # Check if the openai_api_key column exists
        has_openai_api_key = check_column_exists(db, 'users', 'openai_api_key')
        if not has_openai_api_key:
            # If the column doesn't exist, just return success
            logger.warning("openai_api_key column does not exist in users table.")
            return None
            
        # Get user from database
        user_db = db.query(UserDB).filter(UserDB.email == current_user.email).first()
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database"
            )
        
        # Remove API key
        user_db.openai_api_key = None
        db.commit()
        
        logger.info(f"OpenAI API key deleted for user {current_user.email}")
        return None  # Return 204 No Content
        
    except Exception as e:
        logger.error(f"Error deleting OpenAI API key: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete API key: {str(e)}"
        ) 