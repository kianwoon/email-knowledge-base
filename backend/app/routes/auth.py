from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
import json
from datetime import datetime, timedelta, timezone
from jose import jwt
from typing import Dict, Optional, Tuple
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
from app.dependencies.auth import get_current_active_user, msal_app
from app.db.session import get_db # Import get_db
from sqlalchemy.orm import Session # Import Session
from app.crud import user_crud # Import the user CRUD function
# --- Import for manual encryption --- 
from app.utils.security import encrypt_token
# --- End Import --- 

# Instantiate logger
logger = logging.getLogger(__name__)

router = APIRouter()

# --- Add Request Model for Refresh Token --- 
class RefreshTokenRequest(BaseModel):
    refresh_token: str
# --- End Request Model --- 

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> Tuple[str, datetime]:
    to_encode = data.copy() # Use the data passed in
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration if not provided (e.g., 15 minutes)
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_DEFAULT_EXPIRATION_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, expire # Return token and expiry datetime


@router.get("/login")
async def login():
    """Generate Microsoft OAuth login URL"""
    logger.debug("Generating Microsoft OAuth login URL...")
    try:
        state_payload = {"next_url": settings.FRONTEND_URL} # Use frontend URL directly
        state = json.dumps(state_payload)
        logger.debug(f"Generated state: {state}")
        
        auth_url_base = f"{settings.MS_AUTH_BASE_URL}/{settings.MS_TENANT_ID}"
        auth_url_endpoint = f"{auth_url_base}/oauth2/v2.0/authorize"
        
        # --- Start Add Logging ---
        redirect_uri_to_use = settings.MS_REDIRECT_URI
        logger.info(f"DEBUG auth.py /login: Using MS_REDIRECT_URI: {redirect_uri_to_use}")
        # --- End Add Logging ---
        
        auth_params = {
            "client_id": settings.MS_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri_to_use, # Use the logged variable
            "scope": settings.MS_SCOPE_STR,
            "state": state,
            "prompt": "select_account"
        }
        
        full_auth_url = f"{auth_url_endpoint}?{urlencode(auth_params)}"
        logger.debug(f"Constructed auth URL: {full_auth_url}")
        
        return {"auth_url": full_auth_url}
    except Exception as e:
        logger.error(f"Failed to generate login URL: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate login URL: {str(e)}"
        )


@router.get("/callback")
async def auth_callback(
    request: Request,
    db: Session = Depends(get_db) # Inject DB session
):
    """Handle OAuth callback from Microsoft and set HttpOnly cookie."""
    # --- Start Add Logging ---
    # Log the exact incoming request URL as soon as the function is hit
    logger.info(f"DEBUG auth.py /callback: Received request for URL: {request.url}") 
    # --- End Add Logging ---

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
    token_result = None
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
        
        # Correctly get token from result
        ms_access_token = token_result.get("access_token") 
        ms_refresh_token = token_result.get("refresh_token") # Also get refresh token
        if not ms_access_token:
            # Handle missing access token error
            raise ValueError("Microsoft access token not found in the response.")
        
    except Exception as ex_token:
        print(f"Error during token exchange HTTP request: {str(ex_token)}")
        error_url = f"{settings.FRONTEND_URL}?error=token_exchange_exception&error_description={urllib.parse.quote(str(ex_token))}"
        return RedirectResponse(url=error_url)

    # --- Process user info, SAVE TO DB, create JWT, set cookie --- 
    try:
        # Use the ms_access_token obtained above
        outlook_service = OutlookService(ms_access_token)
        user_info = await outlook_service.get_user_info()
        if not user_info:
            raise ValueError("Could not retrieve user info from MS Graph.")

        photo_url = await outlook_service.get_user_photo() # Optional
        
        # Create Pydantic User model instance
        # Note: Using user_info.get("id") for the 'id' field which is the MS Graph user GUID
        user_pydantic = User(
            id=user_info.get("id"), 
            email=user_info.get("mail"),
            display_name=user_info.get("displayName"),
            last_login=datetime.now(timezone.utc), # Set initial login time
            photo_url=photo_url,
            organization=user_info.get("officeLocation"),
            # preferences: Dict[str, Any] = Field(default_factory=dict) # Handled by default
            # is_active: bool = True # Handled by default
            # ms_token_data is not part of the DB model currently
        )

        # Create or update user in the DATABASE using CRUD
        db_user = user_crud.create_or_update_user(db=db, user_data=user_pydantic)
        logger.info(f"User {db_user.email} created/updated in database.")

        # --- Store MS Refresh Token in DB (Step 0.4.3 - Manual Encryption) ---
        if ms_refresh_token:
            logger.debug(f"Attempting to encrypt and save refresh token for user {db_user.email}.")
            encrypted_token_bytes = encrypt_token(ms_refresh_token)
            if encrypted_token_bytes:
                db_user.ms_refresh_token = encrypted_token_bytes # Store the encrypted bytes
                try:
                    db.add(db_user) # Add the user object back to the session if needed
                    db.commit()
                    # db.refresh(db_user) # Refresh might still cause issues, let's skip for now
                    logger.info(f"Successfully saved encrypted refresh token for user {db_user.email}.")
                except Exception as db_err:
                    db.rollback() # Important: Rollback on error
                    logger.error(f"Database error saving refresh token for user {db_user.email}: {db_err}", exc_info=True)
                    # Decide if this should be a fatal error for the login process
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Could not save user session information securely."
                    )
            else:
                # Encryption failed (error already logged by encrypt_token)
                logger.error(f"Encryption failed for refresh token of user {db_user.email}. Cannot save token.")
                # Raise an error because we couldn't securely store the token
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to secure user session information."
                )
        else:
            logger.warning(f"No refresh token received from Microsoft for user {db_user.email}. Cannot save.")
        # --- End Store MS Refresh Token ---

        # Use db_user.id (MS Graph ID) or db_user.email for JWT subject?
        # Let's stick with email for consistency with get_current_user lookup
        jwt_subject = db_user.email
        jwt_user_id = db_user.id # Or use MS Graph ID if needed elsewhere

        # --- Store MS Refresh Token (Example: In localStorage - adjust as needed) ---
        # NOTE: Storing refresh tokens securely is crucial. localStorage is NOT secure.
        #       This is a placeholder. Use HttpOnly cookies or secure server-side storage.
        # if ms_refresh_token: # COMMENTED OUT - Now handled above with DB storage
        #     # This is just for the example to make the interceptor work later
        #     # In a real app, handle this more securely! 
        #     # We might pass it back in the JWT or via another secure mechanism.
        #     print("DEBUG - (Placeholder) Got MS Refresh Token, would store securely.") 
        
        # Create JWT payload, INCLUDING the MS Access Token
        jwt_payload = {
            "sub": jwt_user_id, 
            "email": jwt_subject,
            "ms_token": ms_access_token # Include the MS token here
        }
        
        jwt_access_token, jwt_expires_at_dt = create_access_token(
            data=jwt_payload, # Pass the payload with the MS token
            expires_delta=timedelta(seconds=settings.JWT_EXPIRATION) 
        )
        
        # Calculate max_age using timezone-aware comparison
        max_age_seconds = max(0, int((jwt_expires_at_dt - datetime.now(timezone.utc)).total_seconds()))
        
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
            max_age=max_age_seconds, # Use calculated max_age
            path="/" 
        )
        print(f"DEBUG - Set access_token cookie (HttpOnly) with Max-Age: {max_age_seconds}.")
        return response

    except Exception as e:
        print(f"Error during user processing/DB/token creation/redirect: {str(e)}")
        import traceback
        traceback.print_exc()
        error_url = f"{settings.FRONTEND_URL}?error=callback_processing_error&error_description={urllib.parse.quote(str(e))}"
        return RedirectResponse(url=error_url)


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_active_user)):
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
    max_age_seconds = max(0, int((new_expires_at - datetime.now(timezone.utc)).total_seconds()))
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
