from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import msal
import json
from datetime import datetime, timedelta
from jose import jwt
from typing import Dict, Optional

from app.config import settings
from app.models.user import User, Token, AuthResponse, TokenData
from app.services.outlook import get_user_info

router = APIRouter()

# Create MSAL app for authentication
msal_app = msal.ConfidentialClientApplication(
    settings.MS_CLIENT_ID,
    authority=settings.MS_AUTHORITY,
    client_credential=settings.MS_CLIENT_SECRET
)

# In-memory user storage (replace with database in production)
users_db = {}


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token for internal auth"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(seconds=settings.JWT_EXPIRATION)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt, expire


@router.get("/login")
async def login():
    """Generate Microsoft OAuth login URL"""
    auth_url = msal_app.get_authorization_request_url(
        scopes=settings.MS_SCOPE,
        redirect_uri=settings.MS_REDIRECT_URI,
        state=json.dumps({"next_url": settings.FRONTEND_URL})
    )
    return {"auth_url": auth_url}


@router.get("/callback")
async def auth_callback(request: Request):
    """Handle OAuth callback from Microsoft"""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code not provided"
        )
    
    # Exchange code for tokens
    result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=settings.MS_SCOPE,
        redirect_uri=settings.MS_REDIRECT_URI
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {result.get('error_description')}"
        )
    
    # Get user info from Microsoft Graph
    ms_token = result.get("access_token")
    user_info = get_user_info(ms_token)
    
    # Create or update user
    user_id = user_info.get("id")
    user = User(
        id=user_id,
        email=user_info.get("mail"),
        display_name=user_info.get("displayName"),
        last_login=datetime.utcnow(),
        ms_token_data=TokenData(
            access_token=result.get("access_token"),
            refresh_token=result.get("refresh_token"),
            expires_at=datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600)),
            scope=result.get("scope", [])
        )
    )
    
    # Store user in memory (replace with database in production)
    users_db[user_id] = user
    
    # Create internal JWT token
    access_token, expires_at = create_access_token(
        data={"sub": user_id, "email": user.email}
    )
    
    # Redirect to frontend with token
    next_url = settings.FRONTEND_URL
    if state:
        try:
            state_data = json.loads(state)
            next_url = state_data.get("next_url", settings.FRONTEND_URL)
        except:
            pass
    
    redirect_url = f"{next_url}?token={access_token}&expires={expires_at.timestamp()}"
    return RedirectResponse(url=redirect_url)


@router.get("/me", response_model=User)
async def get_current_user(request: Request):
    """Get current authenticated user information"""
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
    
    return user


@router.post("/refresh", response_model=Token)
async def refresh_token(request: Request):
    """Refresh Microsoft access token using refresh token"""
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
    if user is None or not user.ms_token_data or not user.ms_token_data.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available"
        )
    
    # Use refresh token to get new access token
    result = msal_app.acquire_token_by_refresh_token(
        refresh_token=user.ms_token_data.refresh_token,
        scopes=settings.MS_SCOPE
    )
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {result.get('error_description')}"
        )
    
    # Update user's token data
    user.ms_token_data = TokenData(
        access_token=result.get("access_token"),
        refresh_token=result.get("refresh_token", user.ms_token_data.refresh_token),
        expires_at=datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600)),
        scope=result.get("scope", [])
    )
    
    # Create new internal JWT token
    access_token, expires_at = create_access_token(
        data={"sub": user_id, "email": user.email}
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_at=expires_at
    )
