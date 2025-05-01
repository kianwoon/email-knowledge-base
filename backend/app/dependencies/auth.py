from fastapi import Depends, HTTPException, status, Request, Response, Security
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import msal
import logging
from typing import Optional
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.orm import Session
from pydantic import ValidationError
import requests
import asyncio
from starlette.concurrency import run_in_threadpool
import bcrypt

from app.config import settings
from app.models.user import User, UserDB, TokenData
from app.db.session import get_db
from app.crud import user_crud, token_crud # Import the module directly
from app.models.token_models import TokenDB # Import TokenDB for type hint
from app.utils.security import decrypt_token, encrypt_token # Import decrypt_token and encrypt_token functions
from app.utils.auth_utils import create_access_token # Import the moved JWT creation helper
from app.crud.user_crud import get_user_with_refresh_token, update_user_refresh_token # Import specific CRUD functions needed
from app.crud import crud_export_job # Import token_crud
from app.tasks.export_tasks import export_data_task # Import export_data_task
from app.db.models.export_job import ExportJobStatus # Import ExportJobStatus

# Create MSAL app for authentication
msal_app = msal.ConfidentialClientApplication(
    settings.MS_CLIENT_ID,
    authority=settings.MS_AUTHORITY,
    client_credential=settings.MS_CLIENT_SECRET
)

# In-memory user storage (replace with database in production)
users_db = {}

# Get logger instance
logger = logging.getLogger(__name__)

# Existing dependency for user session/cookie auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/v1/auth/login", auto_error=False)

# NEW: Dependency for API Key (Bearer Token) in Header
api_key_header_scheme = APIKeyHeader(name="Authorization", auto_error=False)

# REVISED get_current_user signature
async def get_current_user(
    request: Request, 
    response: Response,
    db: Session = Depends(get_db)
) -> Optional[User]:
    # +++ Add Log +++
    raw_cookie_header = request.headers.get("cookie")
    logger.debug(f"get_current_user: Raw cookie header received: {raw_cookie_header}")
    # --- End Log ---
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    refresh_failed_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not refresh token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token: str | None = None
    token_source: str = ""

    # 1. Check Authorization header (Bearer JWT/API Key)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ")[1]
        token_source = "Header"
        # Check if it looks like our internal JWT or a potential API key
        try:
            # Attempt to decode as JWT first
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM], options={"verify_signature": False, "verify_exp": False}) # Decode without full verify just to check structure
            if "email" in payload and "sub" in payload:
                logger.debug("Token in header looks like a user session JWT.")
            else:
                 logger.debug("Token in header does NOT look like a user session JWT, treating as potential API key.")
                 # If it doesn't look like our JWT, treat it as an API Key for get_current_active_user_or_token_owner
                 token = None # Clear token so we proceed to check cookies/API Key logic path
                 token_source = "Header (API Key?)"
        except JWTError:
            logger.debug("Token in header is not a valid JWT, treating as potential API key.")
            # If it's not a valid JWT at all, treat as API Key
            token = None
            token_source = "Header (API Key?)"
    
    # 2. Check cookie if header wasn't a user JWT
    if not token:
        # Log the specific cookie value we attempt to get
        cookie_token_value = request.cookies.get("access_token")
        logger.debug(f"get_current_user: Attempting to get 'access_token' cookie. Value: {cookie_token_value}")
        if cookie_token_value:
            token = cookie_token_value
            token_source = "Cookie"

    # 3. Check X-API-Key Header if still no token (explicit API key header)
    if not token:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            logger.debug("Found X-API-Key header.")
            # No *user* found via JWT/Cookie, let get_current_active_user_or_token_owner handle API key validation.
            return None 
        else:
            logger.warning("No token found in Bearer Header (JWT), Cookie, or X-API-Key header.")
            return None # No authentication provided at all

    # --- If we have a token (JWT from header or cookie), validate it --- 
    logger.debug(f"Attempting to validate JWT found in: {token_source}. Token: {token[:10]}...{token[-10:] if len(token)>20 else ''}")
    ms_token: str | None = None # Initialize ms_token
    email: str | None = None # Initialize email
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        email = payload.get("email") # Assign email
        user_id: str | None = payload.get("sub") 
        ms_token = payload.get("ms_token") # Assign ms_token

        # +++ Log extracted values +++
        logger.debug(f"Extracted from JWT payload: email='{email}', ms_token_present={'Yes' if ms_token else 'No'}")
        # --- End Log ---

        if email is None:
            logger.error("JWT payload missing 'email'.")
            raise credentials_exception
        
    except JWTError as e:
        logger.error(f"JWT Error during token decode: {e}")
        response.delete_cookie("access_token", path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=True, httponly=True)
        raise credentials_exception from e
    except ValidationError as e: 
        logger.error(f"Unexpected Pydantic validation error: {e}")
        raise credentials_exception from e

    # Ensure email was successfully extracted before proceeding
    if not email:
        logger.error("Email could not be extracted from JWT payload even after decode.")
        raise credentials_exception # Should not happen if JWTError didn't catch it

    # --- Validate MS Access Token & Attempt Refresh if Needed ---
    validated_ms_token = None
    graph_url = "https://graph.microsoft.com/v1.0/me?$select=id"
    headers = {"Authorization": f"Bearer {ms_token}"}
    
    try:
        logger.debug(f"Validating MS token for user {email} via GET /me")
        
        # --- Run blocking requests.get in threadpool ---
        sync_graph_call = lambda: requests.get(graph_url, headers=headers)
        graph_response = await run_in_threadpool(sync_graph_call)
        # --- End threadpool execution ---

        if graph_response.status_code == 200:
            logger.info(f"MS token for user {email} is valid.")
            validated_ms_token = ms_token
        
        elif graph_response.status_code == 401:
            logger.warning(f"MS token for user {email} is expired or invalid (401). Attempting refresh.")
            
            # --- Attempt Token Refresh --- 
            user_db_for_refresh = get_user_with_refresh_token(db, email=email)
            
            if not user_db_for_refresh or not user_db_for_refresh.ms_refresh_token:
                logger.error(f"Cannot refresh token: User {email} not found or no refresh token stored in DB.")
                response.delete_cookie("access_token", path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=True, httponly=True)
                raise refresh_failed_exception

            encrypted_refresh_token = user_db_for_refresh.ms_refresh_token
            decrypted_refresh_token = decrypt_token(encrypted_refresh_token)

            if not decrypted_refresh_token:
                logger.error(f"Failed to decrypt refresh token for user {email}. InvalidToken or other error.")
                response.delete_cookie("access_token", path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=True, httponly=True)
                raise refresh_failed_exception

            try:
                logger.info(f"Attempting MSAL refresh for user {email}")
                # Filter out reserved OIDC scopes before requesting refresh
                all_scopes = settings.MS_SCOPE_STR.split()
                reserved_scopes = {'openid', 'profile', 'offline_access'}
                resource_scopes = [s for s in all_scopes if s not in reserved_scopes]
                logger.debug(f"Requesting refresh token with filtered resource scopes: {resource_scopes}")
                
                # --- Wrap MSAL call in threadpool and add timeout --- 
                REFRESH_TIMEOUT = 60 # MODIFIED: Increased timeout to 60 seconds
                try:
                    # Define the synchronous function call
                    sync_msal_call = lambda: msal_app.acquire_token_by_refresh_token(
                        decrypted_refresh_token,
                        scopes=resource_scopes
                    )
                    # Run the sync call in threadpool and await its completion with timeout
                    refresh_result = await asyncio.wait_for(
                        run_in_threadpool(sync_msal_call),
                        timeout=REFRESH_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.error(f"MSAL refresh for user {email} timed out after {REFRESH_TIMEOUT} seconds (executed via threadpool).")
                    raise refresh_failed_exception # Raise the same exception as other refresh failures
                # --- End threadpool/timeout wrapper ---

                if "access_token" in refresh_result:
                    new_ms_access_token = refresh_result['access_token']
                    validated_ms_token = new_ms_access_token # Use the new token
                    logger.info(f"Successfully refreshed MS token for user {email}.")

                    # Check if a new refresh token was issued
                    if "refresh_token" in refresh_result:
                        new_ms_refresh_token = refresh_result['refresh_token']
                        logger.info(f"New MS refresh token received for user {email}. Updating database.")
                        encrypted_new_refresh = encrypt_token(new_ms_refresh_token)
                        if encrypted_new_refresh:
                            try:
                                update_success = update_user_refresh_token(db, user_email=email, encrypted_refresh_token=encrypted_new_refresh)
                                if update_success:
                                    logger.info(f"Successfully updated refresh token in DB for {email}.")
                                else:
                                    # Should not happen if rowcount check works, but log just in case
                                    logger.warning(f"Update refresh token call returned False for user {email}, user might not exist? Inconsistency.")
                            except Exception as db_update_err:
                                logger.error(f"Failed to update new refresh token in DB for {email}: {db_update_err}", exc_info=True)
                                # Log error but proceed with new access token
                        else:
                            logger.error(f"Failed to encrypt new refresh token for {email}. DB not updated.")

                    # --- Create and Set New Internal JWT Cookie --- 
                    # Use the correct user_id from the initial JWT decode
                    internal_token_data = {
                        "sub": user_id, 
                        "email": email,
                        "ms_token": new_ms_access_token, 
                        "scopes": resource_scopes, # Embed filtered scopes in new JWT
                    }
                    # Use the imported create_access_token function
                    new_internal_token, expires_at = create_access_token(data=internal_token_data)

                    response.set_cookie(
                        key="access_token",
                        value=new_internal_token,
                        httponly=True,
                        secure=True,
                        samesite='Lax',
                        path='/',
                        expires=expires_at,
                    )
                    logger.info(f"New internal JWT cookie set for user {email} after token refresh.")

                else: # MSAL refresh attempt failed
                    error_details = refresh_result.get('error_description', 'Unknown MSAL error')
                    logger.error(f"MSAL refresh token acquisition failed for user {email}: {error_details}")
                    # If refresh fails permanently (e.g., invalid_grant), clear tokens and force re-login
                    if refresh_result.get("error") == "invalid_grant":
                        logger.warning(f"Refresh token for {email} is invalid or revoked. Clearing tokens.")
                        try:
                            update_user_refresh_token(db, user_email=email, encrypted_refresh_token=None) # Clear RT from DB
                        except Exception as clear_err:
                             logger.error(f"Failed to clear refresh token from DB for {email} after invalid_grant: {clear_err}", exc_info=True)
                        response.delete_cookie("access_token", path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=True, httponly=True)
                    raise refresh_failed_exception

            except Exception as msal_err:
                logger.error(f"Unexpected error during MSAL refresh for {email}: {msal_err}", exc_info=True)
                raise refresh_failed_exception

        else: # Graph API returned non-200/401 status
            logger.error(f"Unexpected error validating MS token for {email}. Status: {graph_response.status_code}, Body: {graph_response.text}")
            raise credentials_exception

    except requests.exceptions.RequestException as req_err:
        logger.error(f"HTTP request error during MS token validation for {email}: {req_err}", exc_info=True)
        raise credentials_exception

    # --- Fetch User from DB and Return ---
    if not validated_ms_token:
         logger.error(f"Failed to obtain a validated MS token for {email} after validation/refresh attempts.")
         # Ensure cookie is cleared if we end up here without a valid token
         response.delete_cookie("access_token", path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=True, httponly=True)
         raise credentials_exception
         
    # Fetch user details (excluding refresh token)
    user_db = user_crud.get_user_full_instance(db, email=email)
    if user_db is None:
        logger.error(f"Consistency Error: User {email} not found in DB after token validation/refresh.")
        raise credentials_exception
    
    user = User.model_validate(user_db)
    user.ms_access_token = validated_ms_token # Attach the final validated/refreshed token
    
    logger.debug(f"get_current_user returning validated user: {user.email}")
    return user

# REVISED get_current_active_user_or_token_owner signature
async def get_current_active_user_or_token_owner(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    api_key_header: Optional[str] = Depends(api_key_header_scheme) 
) -> User:
    # Pass request and response to get_current_user
    session_user: Optional[User] = await get_current_user(request=request, response=response, db=db)
    
    # 1. Check session user resolved by get_current_user
    if session_user:
        logger.debug(f"Authenticated via session: {session_user.email}")
        # Add is_active check here (moved from deprecated get_current_active_user)
        if not session_user.is_active:
             logger.warning(f"Inactive user authenticated via session: {session_user.email}")
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
        return session_user

    # 2. Check for Authorization: Bearer <token> header
    if api_key_header and api_key_header.lower().startswith("bearer "):
        token_value = api_key_header.split(" ", 1)[1]
        logger.debug(f"Attempting authentication via Bearer token.")
        
        # Use the explicitly injected db session here
        db_token: Optional[TokenDB] = token_crud.get_token_by_value(db, token_value)
        
        if db_token:
            now = datetime.now(timezone.utc)
            is_expired = db_token.expiry is not None and db_token.expiry <= now
            if db_token.is_active and not is_expired:
                 # Use the explicitly injected db session here
                token_owner_db: Optional[UserDB] = user_crud.get_user_full_instance(db, email=db_token.owner_email)
                if token_owner_db:
                    logger.info(f"Authenticated via valid API token owned by: {token_owner_db.email}")
                    # Convert UserDB to Pydantic User before returning
                    pydantic_token_owner = User.model_validate(token_owner_db)
                    return pydantic_token_owner
                else:
                    logger.error(f"Valid API token {db_token.id} found, but owner '{db_token.owner_email}' does not exist in user DB!", exc_info=True)
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token owner configuration error.")
            else:
                 logger.warning(f"Authentication failed: API token {db_token.id} is inactive or expired.")
        else:
            logger.warning("Authentication failed: Invalid Bearer token provided.")
            
    # 3. If neither session nor valid bearer token, raise 401
    logger.warning("Authentication failed: No valid session or API token found.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

# REVISED get_current_active_user signature
async def get_current_active_user(
    current_user: User | None = Depends(get_current_user)
) -> User:
    """Get current active user or raise 401."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    
    return current_user

async def get_current_user_from_cookie(
    request: Request, 
    db: Session = Depends(get_db) # Inject DB Session
) -> User:
    """Dependency to get current authenticated user from HttpOnly cookie."""
    logger.info("Attempting to get current user from cookie...")
    
    # --- Read token from HttpOnly cookie --- 
    token = request.cookies.get("access_token")
    
    if not token:
        logger.warning("Access token cookie missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Access token cookie missing",
        )
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials from cookie",
    )
    
    try:
        validation_time_utc = datetime.utcnow()
        logger.debug(f"Validating token from cookie at (UTC): {validation_time_utc}")
        # ... (keep existing logging for algorithm and secret) ...
        
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM],
            options={"leeway": 30} # Keep leeway
        )
        user_id = payload.get("sub")
        email = payload.get("email") # Keep email for potential logging
        logger.info(f"Token from cookie decoded successfully. Payload sub: {user_id}, email: {email}")
        
        if user_id is None:
            logger.error("User ID ('sub') not found in token payload from cookie.")
            raise credentials_exception
            
    except jwt.ExpiredSignatureError:
        logger.warning("Token validation failed (from cookie): ExpiredSignatureError")
        # ... (keep existing detailed logging for expired token) ...
        # Clear the expired cookie? Maybe not here, let frontend trigger logout/refresh.
        raise credentials_exception # Re-raise the original exception
    except jwt.JWTClaimsError as e:
        logger.error(f"Token validation failed (from cookie): JWTClaimsError - {e}")
        raise credentials_exception
    except jwt.JWTError as e:
        logger.error(f"Token validation failed (from cookie): JWTError - {e}", exc_info=True)
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error during token decoding (from cookie): {e}", exc_info=True)
        raise credentials_exception
        
    # --- Use DB Session for user lookup ---
    user_db_instance = user_crud.get_user_by_id(db, user_id=user_id) 
    
    if user_db_instance is None:
        # Use the email from the token for logging if available
        log_identifier = f"ID '{user_id}'" + (f" (email: {email})" if email else "")
        logger.error(f"User with {log_identifier} (from cookie token) not found in database.")
        # Keep 401 to avoid revealing user existence based on ID
        raise credentials_exception # Changed from 404 to 401 for consistency
    
    # Convert UserDB to Pydantic User model for internal logic consistency
    # This assumes User model has a way to validate from ORM instance
    try:
        user = User.model_validate(user_db_instance)
    except Exception as e:
        logger.error(f"Failed to validate UserDB instance for user {user_id} into User model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error processing user data.")

    # --- MS token refresh logic using user_db_instance ---
    logger.info(f"User '{user_id}' found in db. Checking MS token expiry.")
    # Check if Microsoft token is expired and needs refresh
    # Directly access ms_token_data which should be a JSONB field or similar in UserDB
    # Assuming ms_token_data is stored as a dict or can be accessed like one
    current_ms_token_data = user_db_instance.ms_token_data 
    
    if current_ms_token_data and isinstance(current_ms_token_data, dict):
        # Attempt to parse the stored data into TokenData Pydantic model
        try:
            stored_token_obj = TokenData(**current_ms_token_data)
            is_expired = stored_token_obj.expires_at <= datetime.utcnow()
            refresh_token_available = stored_token_obj.refresh_token
        except Exception as parse_error:
            logger.error(f"Failed to parse stored ms_token_data for user {user_id}: {parse_error}", exc_info=True)
            is_expired = False # Cannot determine expiry if parsing fails
            refresh_token_available = None

        if is_expired and refresh_token_available:
            logger.info(f"MS token for user '{user_id}' expired or expires soon. Attempting refresh.")
            try:
                # Use refresh token to get new access token
                result = msal_app.acquire_token_by_refresh_token(
                    refresh_token=refresh_token_available, # Use parsed refresh token
                    scopes=settings.MS_SCOPE
                )
                
                if "error" in result:
                    raise Exception(f"Token refresh failed: {result.get('error_description')}")
                
                # Create new TokenData Pydantic model with refreshed info
                new_token_data = TokenData(
                    access_token=result.get("access_token"),
                    # Use new refresh token if provided, otherwise keep the old one
                    refresh_token=result.get("refresh_token", refresh_token_available), 
                    expires_at=datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600)),
                    scope=result.get("scope", [])
                )

                # --- Persist the updated token data back to the DB ---
                update_data = {"ms_token_data": new_token_data.model_dump()} # Convert Pydantic model to dict for storage
                updated_user = user_crud.update_user(db=db, user_id=user_id, update_data=update_data)
                if updated_user:
                    logger.info(f"Successfully refreshed and persisted MS token data for user {user_id}")
                    # Update the user object in memory with the newly saved data
                    user = User.model_validate(updated_user) 
                else:
                     # This case should ideally not happen if update_user works correctly
                     logger.error(f"Failed to persist refreshed MS token data for user {user_id} (update returned None/False).")
                     # Decide how to handle this: raise 500? proceed with in-memory token?
                     # For now, proceed with the in-memory refreshed token but log error.
                     user.ms_token_data = new_token_data # Keep the in-memory update at least

            except Exception as e:
                # ... (Refresh failure handling remains the same: raise 401) ...
                logger.error(f"Failed to refresh MS token for user '{user_id}': {str(e)}", exc_info=True)
                raise credentials_exception
    elif current_ms_token_data:
         logger.warning(f"User {user_id} ms_token_data is not a dictionary: {type(current_ms_token_data)}. Skipping refresh check.")

    # Return the Pydantic User model (potentially updated with refreshed token)
    return user 

# --- API Key Header for Bearer token --- 
# Use the same scheme as used elsewhere for consistency
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# --- Copied Token Validation Dependency --- 

async def get_validated_token(
    authorization: Optional[str] = Security(api_key_header_scheme),
    db: Session = Depends(get_db)
) -> TokenDB:
    """
    Dependency to validate an API token (prefix_secret format) provided in the
    Authorization header (as a Bearer token) and return the corresponding TokenDB object.

    Raises HTTPException 401/403 if validation fails.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate API token credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    forbidden_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="API token is inactive, expired, or invalid format", # Updated detail
    )

    logger.debug(f"get_validated_token: Raw Authorization header: {authorization}")

    if authorization is None or not authorization.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization Bearer header for token validation.")
        raise credentials_exception

    full_token_value = authorization.split("Bearer ")[1].strip()
    if not full_token_value:
        logger.warning("Bearer token value is empty after stripping.")
        raise credentials_exception

    # --- NEW: Split token into prefix and secret part --- 
    try:
        prefix, secret_part = full_token_value.split('_', 1) # Split only on the first underscore
        if not prefix or not secret_part:
            raise ValueError("Token format incorrect, missing prefix or secret part after split.")
        # Optional: Add more prefix format validation if needed (e.g., length, starting chars)
        if not prefix.startswith("kb_") or len(prefix) != 11: # Example validation: kb_ + 8 hex chars
             logger.warning(f"Invalid token prefix format: '{prefix}'")
             raise ValueError("Invalid token prefix format.")
             
    except ValueError as e:
        logger.error(f"Failed to parse token format: {e}. Input: {full_token_value}")
        raise forbidden_exception # Use 403 for invalid format
    # --- END Split --- 

    token_preview = f"{prefix}_...{secret_part[-5:]}" if len(secret_part) > 5 else f"{prefix}_..."
    logger.info(f"Attempting to validate token with prefix: {prefix}, preview: {token_preview}")

    # --- NEW: Lookup token by prefix --- 
    # TODO: Implement get_token_by_prefix in token_crud.py
    token_db = token_crud.get_token_by_prefix(db, token_prefix=prefix)
    # --- END Lookup ---

    if not token_db:
        logger.warning(f"No token found matching prefix: {prefix}.")
        raise credentials_exception # Use 401 if prefix doesn't exist

    # --- REVISED: Validate hash using secret_part --- 
    if not hasattr(token_db, 'hashed_token') or not token_db.hashed_token:
         logger.error(f"Token {token_db.id} (Prefix: {prefix}) found but missing hashed_token field. Configuration error.")
         raise forbidden_exception

    try:
        secret_part_bytes = secret_part.encode('utf-8')
        # Ensure stored hash is bytes (handle potential DB storage inconsistencies)
        stored_hash_str = token_db.hashed_token
        if isinstance(stored_hash_str, str):
             hashed_token_bytes = stored_hash_str.encode('utf-8')
        elif isinstance(stored_hash_str, bytes):
             hashed_token_bytes = stored_hash_str
        else:
             logger.error(f"Token {token_db.id} (Prefix: {prefix}) has unexpected type for hashed_token: {type(stored_hash_str)}.")
             raise forbidden_exception

        is_valid_hash = bcrypt.checkpw(secret_part_bytes, hashed_token_bytes)

        if not is_valid_hash:
            logger.warning(f"Token {token_db.id} (Prefix: {prefix}) hash verification failed.")
            raise credentials_exception # Use 401 for invalid credentials (wrong secret part)

        logger.debug(f"Token {token_db.id} (Prefix: {prefix}) hash verification successful.")

    except Exception as e:
        logger.error(f"Error during bcrypt hash check for token {token_db.id} (Prefix: {prefix}): {e}", exc_info=True)
        # Consider 500 Internal Server Error for unexpected bcrypt issues?
        raise forbidden_exception # Or 500?

    # --- END HASH VALIDATION --- 

    # Check if token is active
    if not token_db.is_active:
        logger.warning(f"Token {token_db.id} (Prefix: {prefix}, Owner: {token_db.owner_email}) is inactive.")
        raise forbidden_exception # Use 403 Forbidden for inactive/expired/format issues

    # Check expiry
    if token_db.expiry and token_db.expiry < datetime.now(timezone.utc):
        logger.warning(f"Token {token_db.id} (Prefix: {prefix}, Owner: {token_db.owner_email}) expired at {token_db.expiry}.")
        raise forbidden_exception # Use 403 Forbidden

    # TODO: Implement Audience Check (IP/Org Restrictions) if token_db.audience is set
    # Requires access to the request object to get client IP
    # Example: 
    # request: Request = Depends() # Add request dependency if needed here
    # request_ip = request.client.host
    # if token_db.audience and not check_audience(request_ip, token_db.audience):
    #    logger.warning(f"Token {token_db.id} used from disallowed source IP: {request_ip}. Audience: {token_db.audience}")
    #    raise forbidden_exception

    logger.info(f"Successfully validated token {token_db.id} (Prefix: {prefix}, Owner: {token_db.owner_email})")
    return token_db

# --- End Copied Dependency --- 