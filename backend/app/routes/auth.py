from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
import json
from datetime import datetime, timedelta
from jose import jwt
from typing import Dict, Optional
import urllib.parse
import requests
import httpx
from urllib.parse import urlencode, urlparse
import logging
from pydantic import BaseModel
import calendar # Import calendar module

from app.config import settings
from app.models.user import User, Token, AuthResponse, TokenData
from app.services.outlook import OutlookService
from app.dependencies.auth import get_current_user, users_db, msal_app

# Instantiate logger
logger = logging.getLogger(__name__)

router = APIRouter()

# --- Add Request Model for Refresh Token --- 
class RefreshTokenRequest(BaseModel):
    refresh_token: str
# --- End Request Model --- 

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token for internal auth"""
    to_encode = data.copy()
    
    # --- Restore original logic ---
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Log the expiration setting being used
        logger.debug(f"Creating token with expiration from settings: {settings.JWT_EXPIRATION} seconds")
        expire = datetime.utcnow() + timedelta(seconds=settings.JWT_EXPIRATION)
    # --- End original logic ---

    # Convert expire datetime to integer UTC timestamp
    expire_timestamp = calendar.timegm(expire.utctimetuple())
    logger.debug(f"Converted expiration to UTC timestamp: {expire_timestamp}")

    to_encode.update({"exp": expire_timestamp}) # Use the integer timestamp
    # Log the calculated expiration timestamp
    logger.debug(f"Calculated token expiration timestamp (UTC): {expire}") 
    
    # Log the exact payload dictionary before encoding
    logger.debug(f"Payload passed to jwt.encode: {to_encode}")

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
        
        # Generate auth URL using settings
        # Note: Endpoint paths are still hardcoded as per decision
        auth_url_base = f"{settings.MS_AUTH_BASE_URL}/{settings.MS_TENANT_ID}"
        auth_url = f"{auth_url_base}/oauth2/v2.0/authorize"
        
        auth_params = {
            "client_id": settings.MS_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.MS_REDIRECT_URI,
            "scope": settings.MS_SCOPE_STR, # Use scope from settings
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
    """Handle OAuth callback from Microsoft and set HttpOnly cookie."""
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
    
    # Early exit on OAuth error
    if error:
        error_url = f"{settings.FRONTEND_URL}?error={urllib.parse.quote(error)}&error_description={urllib.parse.quote(error_description or '')}"
        print(f"DEBUG - OAuth error, redirecting to: {error_url}")
        return RedirectResponse(url=error_url)
    
    if not code:
        error_url = f"{settings.FRONTEND_URL}?error=no_code&error_description=No authorization code provided"
        print(f"DEBUG - No code, redirecting to: {error_url}")
        return RedirectResponse(url=error_url)

    # --- Exchange code for tokens --- 
    token_result = None # Initialize to None
    try:
        print(f"Exchanging code for tokens with redirect URI: {settings.MS_REDIRECT_URI}")
        token_url_base = f"{settings.MS_AUTH_BASE_URL}/{settings.MS_TENANT_ID}"
        token_url = f"{token_url_base}/oauth2/v2.0/token"
        token_data = {
            'client_id': settings.MS_CLIENT_ID,
            'client_secret': settings.MS_CLIENT_SECRET,
            'code': code,
            'redirect_uri': settings.MS_REDIRECT_URI,
            'grant_type': 'authorization_code',
            'scope': settings.MS_SCOPE_STR
        }
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            token_result = token_response.json() # Get result regardless of status for logging
            
            if token_response.status_code != 200:
                 print(f"DEBUG - Token response error details: {token_result}")
                 error_description = token_result.get('error_description', 'Token exchange failed')
                 error_url = f"{settings.FRONTEND_URL}?error={urllib.parse.quote(token_result.get('error', 'token_error'))}&error_description={urllib.parse.quote(error_description)}"
                 return RedirectResponse(url=error_url)
        
        print(f"DEBUG - Token exchange successful.")
        
    except Exception as ex_token:
        print(f"Error during token exchange HTTP request: {str(ex_token)}")
        error_url = f"{settings.FRONTEND_URL}?error=token_exchange_exception&error_description={urllib.parse.quote(str(ex_token))}"
        return RedirectResponse(url=error_url)

    # --- Process user info, create JWT, set cookie --- 
    try:
        # Get user info from Microsoft Graph
        ms_token = token_result.get("access_token")
        if not ms_token:
             raise ValueError("MS Access Token not found in token response.")
        
        outlook_service = OutlookService(ms_token)
        user_info = await outlook_service.get_user_info()
        if not user_info:
            raise ValueError("Could not retrieve user info from MS Graph.")

        photo_url = await outlook_service.get_user_photo() # Optional
        
        # Create or update user in our system
        user_id = user_info.get("id")
        organization = user_info.get("officeLocation")
        scope = token_result.get("scope", "")
        scope_list = scope.split() if isinstance(scope, str) else scope

        user = User(
            id=user_id,
            email=user_info.get("mail"),
            display_name=user_info.get("displayName"),
            last_login=datetime.utcnow(),
            photo_url=photo_url,
            organization=organization,
            ms_token_data=TokenData(
                access_token=ms_token,
                refresh_token=token_result.get("refresh_token"),
                expires_at=datetime.utcnow() + timedelta(seconds=token_result.get("expires_in", 3600)),
                scope=scope_list
            )
        )
        users_db[user_id] = user
        print(f"DEBUG - User {user.email} stored/updated in users_db.")

        # Create internal JWT token
        jwt_access_token, jwt_expires_at_dt = create_access_token(
            data={"sub": user_id, "email": user.email},
            expires_delta=timedelta(seconds=settings.JWT_EXPIRATION) 
        )
        max_age_seconds = max(0, int((jwt_expires_at_dt - datetime.utcnow()).total_seconds())) # Ensure non-negative
        
        # Determine cookie security based on environment
        secure_cookie = settings.IS_PRODUCTION
        print(f"DEBUG - Setting cookie attributes: HttpOnly=True, Secure={secure_cookie}, SameSite=Lax, Max-Age={max_age_seconds}")

        # Determine final redirect URL (without token params)
        next_url = settings.FRONTEND_URL
        if state:
             try:
                 state_data = json.loads(state)
                 potential_next_url = state_data.get("next_url")
                 if potential_next_url:
                      parsed_url = urlparse(potential_next_url)
                      hostname = parsed_url.hostname
                      if hostname and hostname in settings.ALLOWED_REDIRECT_DOMAINS:
                          next_url = potential_next_url
                      else:
                           print(f"DEBUG - State next_url hostname '{hostname}' not allowed, using default.")
             except Exception as e:
                 print(f"DEBUG - Error processing state: {e}, using default redirect.")
        if not next_url or not next_url.startswith(('http://', 'https://')):
            next_url = settings.FRONTEND_URL
        
        print(f"DEBUG - Redirecting to frontend URL: {next_url}")
        
        # Create RedirectResponse and set the HttpOnly cookie
        response = RedirectResponse(url=next_url)
        response.set_cookie(
            key="access_token",
            value=jwt_access_token,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            max_age=max_age_seconds,
            path="/" 
        )
        print(f"DEBUG - Set access_token cookie (HttpOnly).")
        return response

    except Exception as e:
        print(f"Error during user processing/token creation/redirect: {str(e)}")
        import traceback
        traceback.print_exc()
        error_url = f"{settings.FRONTEND_URL}?error=callback_processing_error&error_description={urllib.parse.quote(str(e))}"
        return RedirectResponse(url=error_url)


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_token(token_request: RefreshTokenRequest):
    """Refresh Microsoft access token using the provided MS refresh token."""
    logger.info("Attempting token refresh using provided MS refresh token.")
    
    if not token_request.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token provided in request body"
        )
        
    # Use provided refresh token to get new access token from Microsoft
    try:
        result = msal_app.acquire_token_by_refresh_token(
            refresh_token=token_request.refresh_token,
            scopes=settings.MS_SCOPE
        )
    except Exception as msal_err:
        # Catch potential errors during the MSAL call itself
        logger.error(f"Error calling MSAL acquire_token_by_refresh_token: {msal_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MSAL token acquisition failed: {msal_err}"
        )

    if "error" in result:
        logger.error(f"Microsoft token refresh failed: {result.get('error')}, Description: {result.get('error_description')}")
        # If refresh fails (e.g., token revoked/expired), force re-login
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {result.get('error_description')}"
        )
    
    # --- Fetch User Info with NEW MS Token --- 
    new_ms_access_token = result.get("access_token")
    if not new_ms_access_token:
         logger.error("MSAL refresh result missing new access token.")
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh succeeded but did not return a new access token."
        )
        
    try:
        logger.info("Fetching user info with new MS access token.")
        outlook_service = OutlookService(new_ms_access_token)
        user_info = await outlook_service.get_user_info()
        user_id = user_info.get("id")
        user_email = user_info.get("mail")
        if not user_id or not user_email:
            logger.error("Could not retrieve user ID or email using new MS access token.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve user details after token refresh."
            )
        logger.info(f"Successfully fetched info for user {user_email} (ID: {user_id}).")
    except Exception as fetch_err:
        logger.error(f"Error fetching user info after token refresh: {fetch_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user details after token refresh: {fetch_err}"
        )
    # --- End Fetch User Info --- 
        
    # Create new internal JWT access token using the fetched user info
    logger.info(f"Creating new internal JWT for user {user_email}.")
    new_internal_access_token, new_expires_at = create_access_token(
        data={"sub": user_id, "email": user_email}
    )
    
    # --- SET HttpOnly Cookie --- 
    response = Response(status_code=status.HTTP_200_OK)
    secure_cookie = settings.IS_PRODUCTION
    max_age_seconds = max(0, int((new_expires_at - datetime.utcnow()).total_seconds()))
    logger.info(f"Setting new access_token cookie. Max-Age: {max_age_seconds}, Secure: {secure_cookie}")
    response.set_cookie(
        key="access_token",
        value=new_internal_access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax", # Match callback settings
        max_age=max_age_seconds,
        path="/"
    )
    # --- End SET Cookie --- 

    # Return a success indicator or minimal info, token is in the cookie
    # The old return type `Token` might no longer be accurate if we don't return the token here.
    # Let's return a simple dict for now. Frontend interceptor doesn't strictly need the token in body anymore.
    return {
        "status": "success",
        "message": "Token refreshed successfully."
        # Optionally include user_id or email if needed by frontend immediately after refresh,
        # but primary token transport is the cookie.
    }

@router.post("/logout")
async def logout(response: Response):
    """Clear the access token cookie to log the user out."""
    logger.info("Logout request received, clearing access token cookie.")
    
    # Determine secure flag based on environment
    secure_cookie = settings.IS_PRODUCTION
    
    response.delete_cookie(
        key="access_token", 
        path="/", 
        httponly=True, 
        secure=secure_cookie, 
        samesite="lax"
    )
    return {"message": "Logout successful"}
