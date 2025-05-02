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
from app.utils.auth_utils import create_access_token

# Instantiate logger
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/login")
async def login():
    """Generate Microsoft OAuth login URL"""
    logger.debug("Generating Microsoft OAuth login URL...")
    try:
        state_payload = {"next_url": settings.FRONTEND_URL} # Use frontend URL directly
        state = json.dumps(state_payload)
        logger.debug(f"Generated state: {state}")
        
        # Construct the correct base URL based on settings
        if settings.MS_AUTH_BASE_URL.endswith('/common'):
            auth_url_base = settings.MS_AUTH_BASE_URL
        else:
            # Fallback or specific tenant logic (ensure tenant ID is valid)
            if not settings.MS_TENANT_ID:
                raise ValueError("MS_TENANT_ID must be set for non-common auth base URL")
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
        # Construct the correct token URL based on settings
        if settings.MS_AUTH_BASE_URL.endswith('/common'):
            token_url_base = settings.MS_AUTH_BASE_URL
        else:
            # Fallback or specific tenant logic
            if not settings.MS_TENANT_ID:
                raise ValueError("MS_TENANT_ID must be set for non-common auth base URL")
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
            
        # +++ ADD LOGGING +++
        logger.info(f"DEBUG: Received user_info from MS Graph: {json.dumps(user_info, indent=2)}") 
        # --- END LOGGING ---

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
        # --- MODIFIED TO STORE ACCESS TOKEN AND EXPIRY AS WELL --- 
        if ms_refresh_token:
            logger.debug(f"Attempting to encrypt and save refresh token for user {db_user.email}.")
            encrypted_token_bytes = encrypt_token(ms_refresh_token)
            if encrypted_token_bytes:
                # Store the encrypted refresh token bytes
                db_user.ms_refresh_token = encrypted_token_bytes 
                
                # --- ADDED: Store Access Token and Expiry --- 
                if ms_access_token:
                    db_user.ms_access_token = ms_access_token # Store plain access token
                    logger.info(f"Storing access token for user {db_user.email}.")
                else:
                    logger.warning(f"No MS access token found in token result for {db_user.email} - cannot store.")
                
                # Calculate and store expiry time
                expires_in_seconds = token_result.get("expires_in")
                if isinstance(expires_in_seconds, (int, float)) and expires_in_seconds > 0:
                    db_user.ms_token_expiry = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in_seconds))
                    logger.info(f"Storing token expiry ({db_user.ms_token_expiry}) for user {db_user.email}.")
                else:
                    logger.warning(f"Could not determine token expiry from 'expires_in' ({expires_in_seconds}) for {db_user.email}. Expiry not stored.")
                    db_user.ms_token_expiry = None # Ensure it's null if not calculable
                # --- END ADDED ---
                
                try:
                    db.add(db_user) # Add the user object back to the session if needed
                    db.commit()
                    # db.refresh(db_user) # Refresh might still cause issues, let's skip for now
                    logger.info(f"Successfully saved tokens for user {db_user.email}.")
                except Exception as db_err:
                    db.rollback() # Important: Rollback on error
                    logger.error(f"Database error saving tokens for user {db_user.email}: {db_err}", exc_info=True)
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
        # --- End Store MS Tokens ---

        # Use db_user.id (MS Graph ID) or db_user.email for JWT subject?
        # Let's stick with email for consistency with get_current_user lookup
        jwt_subject = db_user.email
        # Convert UUID to string for JWT serialization
        jwt_user_id = str(db_user.id) if db_user.id else None 

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
            "sub": jwt_user_id, # Use the string representation
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
            
        # Add token as URL parameter as a fallback for browsers that don't handle cookies properly
        # Frontend will extract this and set as a cookie
        if '?' in next_url:
            next_url = f"{next_url}&access_token={jwt_access_token}"
        else:
            next_url = f"{next_url}?access_token={jwt_access_token}"
        
        print(f"DEBUG - Redirecting to frontend URL: {next_url}")
        
        # Create RedirectResponse and set the HttpOnly cookie
        response = RedirectResponse(url=next_url)
        
        # Debug cookie settings
        print("=========== DEBUG COOKIE SETTINGS ==========")
        print(f"Setting cookie with key: access_token")
        print(f"Cookie value length: {len(jwt_access_token)}")
        print(f"HttpOnly: True")
        print(f"Secure: {secure_cookie}")
        print(f"SameSite: lax")
        print(f"Max-Age: {max_age_seconds}")
        print(f"Path: /")
        print(f"Domain: None (using current domain)")
        print("===========================================")
        
        response.set_cookie(
            key="access_token",
            value=jwt_access_token,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            max_age=max_age_seconds, # Use calculated max_age
            path="/",
            domain=None # Explicitly set to None to use the current domain
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
        samesite="lax",
        domain=None
    )
    return {"message": "Logout successful"}


@router.get("/debug-cookies")
async def debug_cookies(request: Request):
    """Debug endpoint to check what cookies are being received by the backend."""
    cookies = request.cookies
    headers = dict(request.headers)
    
    # Log for server-side debugging
    print("====== DEBUG COOKIES RECEIVED ======")
    print(f"Cookies received: {cookies}")
    print(f"Headers: {headers}")
    print("====================================")
    
    # Return for client-side debugging
    return {
        "cookies": cookies,
        "headers": headers,
        "note": "Check if access_token is present in cookies"
    }


@router.get("/token")
async def get_token(request: Request):
    """Get the token directly as JSON (for clients that have issues with cookies)"""
    # Get token from cookie
    token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Return token directly to client
    return {"access_token": token}
