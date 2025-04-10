from fastapi import Depends, HTTPException, status, Request
from jose import jwt, JWTError
from datetime import datetime, timedelta
import msal
import logging
from typing import Optional
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.config import settings
from app.models.user import User, UserDB, TokenData
from app.db.session import get_db
from app.crud import user_crud # Corrected import
from app.crud import token_crud # Import the module directly
from app.models.token_models import TokenDB # Import TokenDB for type hint
from app.utils.security import decrypt_token # Import decrypt_token function

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
        raise credentials_exception from e
    except ValidationError as e: 
        logger.error(f"Unexpected Pydantic validation error: {e}")
        raise credentials_exception from e

    # Ensure email was successfully extracted before proceeding
    if not email:
        logger.error("Email could not be extracted from JWT payload even after decode.")
        raise credentials_exception # Should not happen if JWTError didn't catch it

    # Fetch UserDB object from database using the email directly
    user_db = user_crud.get_user_full_instance(db, email=email)
    
    if user_db is None:
        logger.warning(f"User with email '{email}' (from JWT) not found in DB.")
        return None 

    # Convert UserDB to Pydantic User model and ADD the ms_token
    user = User.model_validate(user_db)
    user.ms_access_token = ms_token # Attach the extracted token

    # Check for API keys in the api_keys table, but don't set directly on user object
    # since it no longer has an openai_api_key field
    try:
        from ..crud import api_key_crud
        openai_key = api_key_crud.get_decrypted_api_key(db, user.email, "openai")
        if openai_key:
            logger.debug(f"[DEBUG-KEY] User {user.email} has an OpenAI API key in the api_keys table")
            # Log partial key for debugging
            if len(openai_key) > 10:
                masked_key = openai_key[:5] + '...' + openai_key[-5:]
                logger.debug(f"[DEBUG-KEY] Successfully retrieved API key for user: {user.email}, key: {masked_key}")
            else:
                logger.debug(f"[DEBUG-KEY] Successfully retrieved API key for user: {user.email}")
        else:
            logger.debug(f"[DEBUG-KEY] User {user.email} has no OpenAI API key in the database")
    except Exception as e:
        logger.error(f"[DEBUG-KEY] Error retrieving API key for user {user.email}: {e}", exc_info=True)

    # +++ Log value right before returning +++
    logger.debug(f"Final user object ms_access_token present: {'Yes' if user.ms_access_token else 'No'}")
    # --- End Log ---
    
    logger.debug(f"Successfully validated user: {user.email}")
    return user

# REVISED get_current_active_user_or_token_owner signature
async def get_current_active_user_or_token_owner(
    # Depend directly on the result of get_current_user for session check
    session_user: Optional[User] = Depends(get_current_user), 
    # Keep dependency for API key header
    api_key_header: Optional[str] = Depends(api_key_header_scheme),
    # Add explicit DB dependency for token lookup path
    db: Session = Depends(get_db) 
) -> User:
    
    # 1. Check session user resolved by Depends(get_current_user)
    if session_user:
        logger.debug(f"Authenticated via session: {session_user.email}")
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
    logger.warning("Authentication failed: No valid session or Bearer token found.")
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

async def get_current_user_from_cookie(request: Request) -> User:
    """Dependency to get current authenticated user from HttpOnly cookie."""
    logger.info("Attempting to get current user from cookie...")
    
    # --- Read token from HttpOnly cookie --- 
    token = request.cookies.get("access_token")
    
    if not token:
        logger.warning("Access token cookie missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: Access token cookie missing",
            # No WWW-Authenticate header needed for cookie auth typically
        )
        
    # --- Keep existing JWT validation logic --- 
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
        email = payload.get("email")
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
        
    # --- Keep existing user lookup and MS token refresh logic --- 
    user = users_db.get(user_id)
    if user is None:
        logger.error(f"User with ID '{user_id}' (from cookie token) not found in users_db.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"User '{user_id}' found in db. Checking MS token expiry.")
    # Check if Microsoft token is expired and needs refresh
    if user.ms_token_data and user.ms_token_data.expires_at <= datetime.utcnow():
        logger.info(f"MS token for user '{user_id}' expired or expires soon. Attempting refresh.")
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
            logger.error(f"Failed to refresh MS token for user '{user_id}': {str(e)}", exc_info=True)
            # Don't raise an exception here, let the request proceed with the expired token
            # The Microsoft Graph API will return 401 if the token is invalid
            # --- REVISED: Raise 401 on refresh failure --- 
            logger.error(f"Failed to refresh MS token for user '{user_id}': {str(e)}", exc_info=True)
            # Raise the credentials_exception (HTTP 401) to force re-login
            raise credentials_exception
            # --- END REVISION ---
    
    return user 