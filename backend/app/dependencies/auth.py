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
from app.services.auth_service import AuthService  # Import the new centralized AuthService

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
    # +++ Added Log +++
    logger.debug(f"get_current_user: Checking Authorization header. Value: '{auth_header}'")
    # --- End Added Log ---
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ")[1]
        token_source = "Header"
        logger.debug(f"Token extracted from Authorization header: {token[:10]}...{token[-10:] if len(token) > 20 else ''}")
        
        # Check if it looks like our internal JWT or a potential API key
        try:
            # Attempt to decode as JWT first
            payload = AuthService.decode_jwt_unsafe(token)
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
        cookie_value = request.cookies.get(settings.JWT_COOKIE_NAME)
        logger.debug(f"Cookie value for {settings.JWT_COOKIE_NAME}: {cookie_value[:10] + '...' if cookie_value else 'None'}")
        
        if cookie_value:
            token = cookie_value
            token_source = "Cookie"
            logger.debug(f"Using token from cookie: {token[:10]}...{token[-10:] if len(token) > 20 else ''}")

    # 3. Check X-API-Key Header if still no token (explicit API key header)
    if not token:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            logger.debug("Found X-API-Key header.")
            # No *user* found via JWT/Cookie, let get_current_active_user_or_token_owner handle API key validation.
            return None 
        else:
            logger.warning("No token found in Bearer Header (JWT), Cookie, or X-API-Key header.")
            logger.debug(f"All cookies: {request.cookies}")
            logger.debug(f"All headers: {dict(request.headers)}")
            return None # No authentication provided at all

    # --- If we have a token (JWT from header or cookie), authenticate using AuthService --- 
    logger.debug(f"Attempting to validate JWT found in: {token_source}. Token: {token[:10]}...{token[-10:] if len(token)>20 else ''}")
    
    # Use the new centralized auth service to authenticate user
    user = await AuthService.authenticate_and_validate_token(db, token, response)
    
    if user:
        logger.info(f"User {user.email} authenticated successfully")
        return user
    else:
        logger.warning(f"User authentication failed for token from {token_source}")
        return None

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
    token = request.cookies.get(settings.JWT_COOKIE_NAME)
    
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
    db: Session = Depends(get_db),
    request: Request = None
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
        
    # Debug log the received token
    logger.info(f"Received token value for validation. Length: {len(full_token_value)}, Raw value: '{full_token_value}'")

    # --- Extract prefix from token value ---
    try:
        # Try to split by '.' to get prefix and secret part
        if '.' in full_token_value:
            prefix, secret_part = full_token_value.split('.', 1)
            if not prefix or not secret_part:
                raise ValueError("Token format incorrect, missing prefix or secret part after split by '.'")
        else:
            # No period - might be just the prefix
            prefix = full_token_value
            secret_part = None
            logger.info(f"No period separator found in token. Treating as prefix only: {prefix}")
    except ValueError as e:
        logger.error(f"Failed to parse token format (expected 'prefix.secret'): {e}. Input: {full_token_value}")
        raise forbidden_exception
        
    # Create the token preview for logging
    if secret_part:
        token_preview = f"{prefix}.{secret_part[:3]}...{secret_part[-3:]}" if len(secret_part) > 6 else f"{prefix}.{secret_part[:3]}..."
    else:
        token_preview = f"{prefix} (prefix only)"
    logger.info(f"Attempting to validate token with prefix: {prefix}, preview: {token_preview}")

    # Get the token from DB
    token_db = token_crud.get_token_by_prefix(db, token_prefix=prefix)
    if not token_db:
        logger.warning(f"No token found matching prefix: {prefix}.")
        raise credentials_exception

    # Check if token is active
    if not token_db.is_active:
        logger.warning(f"Token {token_db.id} (Prefix: {prefix}, Owner: {token_db.owner_email}) is inactive.")
        raise forbidden_exception
        
    # Check expiry
    if token_db.expiry and token_db.expiry < datetime.now(timezone.utc):
        logger.warning(f"Token {token_db.id} (Prefix: {prefix}, Owner: {token_db.owner_email}) expired at {token_db.expiry}.")
        raise forbidden_exception

    # If no secret part provided, check if the Authorization header contains a valid JWT token
    # This would indicate the user is authenticated and might be the token owner
    if not secret_part:
        # Extract the JWT token directly from the Authorization header
        jwt_token = None
        owner_email = None
        
        # First, get the JWT token from the cookie if request is available
        cookie_token = None
        if request:
            cookie_token = request.cookies.get("access_token")
            
            # Also check for the X-User-Session header that might contain the JWT token
            user_session = request.headers.get("X-User-Session")
            if user_session and not cookie_token:
                cookie_token = user_session
                logger.info("Found session token in X-User-Session header")
        
        if cookie_token:
            try:
                # Decode the JWT to get user info
                payload = jwt.decode(
                    cookie_token, 
                    settings.JWT_SECRET, 
                    algorithms=[settings.JWT_ALGORITHM]
                )
                owner_email = payload.get("email")
                logger.info(f"Found authenticated user from cookie: {owner_email}")
                
                # If authenticated user matches token owner, allow access
                if owner_email and owner_email == token_db.owner_email:
                    logger.info(f"Allowing owner access to token {token_db.id} via prefix only. Owner: {owner_email}")
                    return token_db
            except Exception as jwt_err:
                logger.error(f"Error decoding JWT from cookie: {jwt_err}")
        
        # If we reach here, we also need to check if there's a valid JWT token in the Authorization header itself
        # The Authorization would be in the format "Bearer <JWT_TOKEN>"
        # This is needed because in API requests, the cookie might not be sent
        try:
            # Simple check to see if it looks like a JWT (contains two periods)
            if full_token_value.count('.') == 2:
                # Try to decode it as a JWT
                try:
                    payload = jwt.decode(
                        full_token_value,
                        settings.JWT_SECRET,
                        algorithms=[settings.JWT_ALGORITHM]
                    )
                    owner_email = payload.get("email")
                    
                    # If authenticated user matches token owner, allow access
                    if owner_email and owner_email == token_db.owner_email:
                        logger.info(f"Allowing owner access to token {token_db.id} via JWT in Authorization. Owner: {owner_email}")
                        return token_db
                except Exception as jwt_err:
                    logger.debug(f"Authorization token is not a valid JWT: {jwt_err}")
        except Exception as auth_err:
            logger.error(f"Error checking JWT in Authorization header: {auth_err}")
            
        # If we got here, either no auth or auth user does not match token owner
        logger.warning(f"Token prefix provided without secret part, and no matching owner authentication found")
        raise credentials_exception

    # Validate the secret part against the stored hash
    try:
        secret_part_bytes = secret_part.encode('utf-8')
        if not token_db.hashed_secret or not bcrypt.checkpw(secret_part_bytes, token_db.hashed_secret.encode('utf-8')):
            logger.warning(f"Token validation failed: Invalid secret provided for prefix '{prefix}' (Token ID: {token_db.id}).")
            raise credentials_exception
    except Exception as e:
        logger.error(f"Error during token secret validation: {e}", exc_info=True)
        raise credentials_exception

    logger.info(f"Successfully validated token {token_db.id} (Prefix: {prefix}, Owner: {token_db.owner_email})")
    return token_db

# --- End Copied Dependency --- 

# Function to create a dependency that passes the request to get_validated_token
def get_token_with_request():
    """
    Creates a dependency that passes the request object to get_validated_token.
    This ensures the token validation can access cookies for owner authentication.
    """
    async def _get_token_with_request(
        request: Request,
        authorization: Optional[str] = Security(api_key_header_scheme),
        db: Session = Depends(get_db)
    ) -> TokenDB:
        return await get_validated_token(authorization=authorization, db=db, request=request)
    
    return _get_token_with_request