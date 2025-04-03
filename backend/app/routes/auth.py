from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import msal
import json
from datetime import datetime, timedelta
from jose import jwt
from typing import Dict, Optional
import urllib.parse
import requests
from urllib.parse import urlencode

from app.config import settings
from app.models.user import User, Token, AuthResponse, TokenData
from app.services.outlook import get_user_info, get_user_photo

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
    # Enhanced logging for debugging
    print(f"=== Login Endpoint Called ===")
    print(f"DEBUG - Environment variables:")
    print(f"DEBUG - BACKEND_URL: {settings.BACKEND_URL}")
    print(f"DEBUG - FRONTEND_URL: {settings.FRONTEND_URL}")
    print(f"DEBUG - MS_REDIRECT_URI: {settings.MS_REDIRECT_URI}")
    print(f"DEBUG - MS_CLIENT_ID: {settings.MS_CLIENT_ID[:5]}...{settings.MS_CLIENT_ID[-5:] if settings.MS_CLIENT_ID else 'Not set'}")
    print(f"DEBUG - MS_TENANT_ID: {settings.MS_TENANT_ID[:5]}...{settings.MS_TENANT_ID[-5:] if settings.MS_TENANT_ID else 'Not set'}")
    print(f"DEBUG - IS_PRODUCTION: {settings.IS_PRODUCTION}")
    
    try:
        # Create state with next_url for callback
        frontend_url = settings.FRONTEND_URL
        print(f"DEBUG - Using frontend URL for state: {frontend_url}")
        
        # Ensure we have a valid frontend URL
        if not frontend_url or not frontend_url.startswith(('http://', 'https://')):
            print(f"DEBUG - Invalid frontend URL, using settings value")
            frontend_url = settings.FRONTEND_URL
            print(f"DEBUG - Using frontend URL from settings: {frontend_url}")
        
        state = json.dumps({"next_url": frontend_url})
        print(f"DEBUG - Generated state: {state}")
        
        # Generate auth URL
        auth_url = f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}/oauth2/v2.0/authorize"
        auth_params = {
            "client_id": settings.MS_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.MS_REDIRECT_URI,
            "scope": "User.Read Mail.Read offline_access",
            "state": state,
            "prompt": "select_account"
        }
        
        # Log the full auth URL for debugging
        full_auth_url = f"{auth_url}?{urlencode(auth_params)}"
        print(f"DEBUG - Full auth URL: {full_auth_url}")
        
        return {"auth_url": full_auth_url}
    except Exception as e:
        print(f"ERROR - Exception in login route: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate login URL: {str(e)}"
        )


@router.get("/callback")
async def auth_callback(request: Request):
    """Handle OAuth callback from Microsoft"""
    print("Received callback request")
    print(f"DEBUG - Full request URL: {request.url}")
    print(f"DEBUG - Request headers: {dict(request.headers)}")
    print(f"Query params: {dict(request.query_params)}")
    print(f"DEBUG - Current settings:")
    print(f"DEBUG - MS_REDIRECT_URI: {settings.MS_REDIRECT_URI}")
    print(f"DEBUG - MS_CLIENT_ID: {settings.MS_CLIENT_ID}")
    print(f"DEBUG - MS_TENANT_ID: {settings.MS_TENANT_ID}")
    print(f"DEBUG - FRONTEND_URL: {settings.FRONTEND_URL}")
    
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description")
    
    if error:
        print(f"Auth error: {error}, Description: {error_description}")
        # Instead of raising an exception, redirect to frontend with error
        error_url = f"{settings.FRONTEND_URL}?error={error}&error_description={error_description}"
        return RedirectResponse(url=error_url)
    
    if not code:
        print("No authorization code provided")
        error_url = f"{settings.FRONTEND_URL}?error=no_code&error_description=No authorization code provided"
        return RedirectResponse(url=error_url)
    
    # Exchange code for tokens using direct HTTP request instead of MSAL
    print(f"Exchanging code for tokens with redirect URI: {settings.MS_REDIRECT_URI}")
    try:
        # Prepare token request
        token_url = f"https://login.microsoftonline.com/{settings.MS_TENANT_ID}/oauth2/v2.0/token"
        token_data = {
            'client_id': settings.MS_CLIENT_ID,
            'client_secret': settings.MS_CLIENT_SECRET,
            'code': code,
            'redirect_uri': settings.MS_REDIRECT_URI,
            'grant_type': 'authorization_code',
            'scope': 'User.Read Mail.Read offline_access'
        }
        
        print(f"DEBUG - Token request data (excluding secret): {dict(token_data, client_secret='[REDACTED]')}")
        
        # Make the token request
        token_response = requests.post(token_url, data=token_data)
        result = token_response.json()
        
        print(f"DEBUG - Token response status: {token_response.status_code}")
        if token_response.status_code != 200:
            print(f"DEBUG - Token response error: {result}")
            error_url = f"{settings.FRONTEND_URL}?error=token_error&error_description={result.get('error_description', 'Token exchange failed')}"
            return RedirectResponse(url=error_url)
        
        print("Successfully acquired token")
        
        # Get user info from Microsoft Graph
        ms_token = result.get("access_token")
        user_info = await get_user_info(ms_token)
        
        # Try to get user's profile photo
        photo_url = await get_user_photo(ms_token)
        
        # Extract organization information if available
        organization = None
        if user_info.get("officeLocation"):
            organization = user_info.get("officeLocation")
        
        # Create or update user
        user_id = user_info.get("id")
        
        # Convert scope string to list if needed
        scope = result.get("scope", "")
        scope_list = scope.split() if isinstance(scope, str) else scope
        
        user = User(
            id=user_id,
            email=user_info.get("mail"),
            display_name=user_info.get("displayName"),
            last_login=datetime.utcnow(),
            photo_url=photo_url,
            organization=organization,
            ms_token_data=TokenData(
                access_token=result.get("access_token"),
                refresh_token=result.get("refresh_token"),
                expires_at=datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600)),
                scope=scope_list
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
        print(f"DEBUG - Default next_url from settings: {next_url}")
        
        if state:
            try:
                print(f"DEBUG - State parameter received: {state}")
                state_data = json.loads(state)
                if "next_url" in state_data:
                    next_url = state_data.get("next_url")
                    print(f"DEBUG - next_url from state: {next_url}")
                    
                    # Ensure the next_url is valid and matches our expected domain
                    if "email-knowledge-base-2-automationtesting-ba741710.koyeb.app" not in next_url and "localhost" not in next_url:
                        print(f"DEBUG - next_url domain doesn't match expected domains, using default: {settings.FRONTEND_URL}")
                        next_url = settings.FRONTEND_URL
            except Exception as e:
                print(f"DEBUG - Error parsing state parameter: {str(e)}")
                next_url = settings.FRONTEND_URL
        
        # Ensure we have a valid frontend URL for the redirect
        if not next_url or not next_url.startswith(('http://', 'https://')):
            print(f"DEBUG - Invalid next_url, using default: {settings.FRONTEND_URL}")
            next_url = settings.FRONTEND_URL
        
        redirect_url = f"{next_url}?token={access_token}&expires={expires_at.timestamp()}"
        print(f"DEBUG - Final redirect URL: {redirect_url}")
        
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        print(f"Error during token exchange: {str(e)}")
        error_url = f"{settings.FRONTEND_URL}?error=token_exchange_error&error_description={str(e)}"
        return RedirectResponse(url=error_url)


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
