import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_settings import UserSettings
from app.crud import user_settings_crud
from app.db.session import get_db
from app.dependencies.auth import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", status_code=status.HTTP_200_OK)
async def get_settings(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the current user's settings.
    """
    try:
        settings = user_settings_crud.get_or_create_user_settings(db, current_user.id)
        return settings.to_dict()
    except Exception as e:
        logger.error(f"Error getting user settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user settings: {str(e)}"
        )

@router.put("/", status_code=status.HTTP_200_OK)
async def update_settings(
    settings_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update the current user's settings.
    """
    try:
        updated_settings = user_settings_crud.update_user_settings(db, current_user.id, settings_data)
        return updated_settings.to_dict()
    except Exception as e:
        logger.error(f"Error updating user settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user settings: {str(e)}"
        ) 