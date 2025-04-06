from fastapi import Depends, HTTPException, status, Request
from jose import jwt
from datetime import datetime, timedelta
import msal
import logging

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

# Get logger instance
logger = logging.getLogger(__name__)

async def get_current_user(request: Request) -> User:
    """Dependency to get current authenticated user"""
    logger.info("Attempting to get current user...")
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        logger.warning("Authorization header missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not auth_header.startswith("Bearer "):
        logger.warning(f"Invalid Authorization header format: {auth_header}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    logger.debug(f"Extracted token: {token[:10]}...{token[-5:]}")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Log current time just before decoding
        validation_time_utc = datetime.utcnow()
        logger.debug(f"Validating token at (UTC): {validation_time_utc}") 
        
        # Log parameters used for decoding
        logger.debug(f"Decoding token using algorithm: {settings.JWT_ALGORITHM}")
        logger.debug(f"Using JWT secret ending with: ...{settings.JWT_SECRET[-6:] if settings.JWT_SECRET else 'SECRET_NOT_SET'}")
        
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM],
            options={"leeway": 30}
        )
        user_id = payload.get("sub")
        email = payload.get("email")
        logger.info(f"Token decoded successfully. Payload sub: {user_id}, email: {email}")
        
        if user_id is None:
            logger.error("User ID ('sub') not found in token payload.")
            raise credentials_exception
            
    except jwt.ExpiredSignatureError:
        logger.warning("Token validation failed: ExpiredSignatureError")
        try:
            # Decode without verification JUST FOR DEBUGGING
            unverified_payload = jwt.decode(
                token, 
                settings.JWT_SECRET, 
                algorithms=[settings.JWT_ALGORITHM], 
                options={"verify_signature": False, "verify_exp": False}
            )
            exp_timestamp = unverified_payload.get('exp')
            exp_datetime = datetime.utcfromtimestamp(exp_timestamp) if exp_timestamp else 'N/A'
            logger.error(f"[DEBUG] ExpiredSignatureError caught! Validation time: {validation_time_utc}. Unverified payload 'exp' claim: {exp_timestamp} ({exp_datetime})")
        except Exception as e:
            logger.error(f"[DEBUG] Could not decode unverified payload after ExpiredSignatureError: {e}")
        raise credentials_exception # Re-raise the original exception
    except jwt.JWTClaimsError as e:
        logger.error(f"Token validation failed: JWTClaimsError - {e}")
        raise credentials_exception
    except jwt.JWTError as e:
        logger.error(f"Token validation failed: JWTError - {e}", exc_info=True)
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error during token decoding: {e}", exc_info=True)
        raise credentials_exception
        
    user = users_db.get(user_id)
    if user is None:
        logger.error(f"User with ID '{user_id}' not found in users_db.")
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
            print(f"Error refreshing token: {str(e)}")
            # Don't raise an exception here, let the request proceed with the expired token
            # The Microsoft Graph API will return 401 if the token is invalid
    
    return user 