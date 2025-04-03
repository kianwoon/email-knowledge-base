from fastapi import Depends, HTTPException, status, Request
from jose import jwt
from datetime import datetime, timedelta
import msal

from app.config import settings
from app.models.user import User, TokenData

# Create MSAL app for authentication
msal_app = msal.ConfidentialClientApplication(
    settings.MS_CLIENT_ID,
    authority=settings.MS_AUTHORITY,
    client_credential=settings.MS_CLIENT_SECRET
)

# In-memory user storage (replace with database in production)
users_db = {}

async def get_current_user(request: Request) -> User:
    """Dependency to get current authenticated user"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = users_db.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if Microsoft token is expired and needs refresh
    if user.ms_token_data and user.ms_token_data.expires_at <= datetime.utcnow():
        try:
            # Use refresh token to get new access token
            result = msal_app.acquire_token_by_refresh_token(
                refresh_token=user.ms_token_data.refresh_token,
                scopes=settings.MS_SCOPE
            )
            
            if "error" in result:
                raise Exception(f"Token refresh failed: {result.get('error_description')}")
            
            # Update user's token data
            user.ms_token_data = TokenData(
                access_token=result.get("access_token"),
                refresh_token=result.get("refresh_token", user.ms_token_data.refresh_token),
                expires_at=datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600)),
                scope=result.get("scope", [])
            )
        except Exception as e:
            print(f"Error refreshing token: {str(e)}")
            # Don't raise an exception here, let the request proceed with the expired token
            # The Microsoft Graph API will return 401 if the token is invalid
    
    return user 