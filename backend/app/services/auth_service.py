import asyncio
import logging
import msal
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, List
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from fastapi import Response
from jose import jwt, JWTError

from app.config import settings
from app.models.user import User, UserDB
from app.utils.security import encrypt_token, decrypt_token
from app.utils.auth_utils import create_access_token
from app.crud.user_crud import get_user_with_refresh_token, update_user_refresh_token, update_user_ms_tokens, get_user_full_instance

# Configure logging
logger = logging.getLogger(__name__)

# Create a centralized MSAL app instance
_msal_app = msal.ConfidentialClientApplication(
    settings.MS_CLIENT_ID,
    authority=settings.MS_AUTHORITY,
    client_credential=settings.MS_CLIENT_SECRET
)

# Constants
REFRESH_TIMEOUT = 60  # seconds
MS_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
RESERVED_SCOPES = {'openid', 'profile', 'offline_access'}

class AuthService:
    """
    Centralized authentication service that handles token validation,
    refresh, and related operations.
    """
    
    @staticmethod
    def get_msal_app() -> msal.ConfidentialClientApplication:
        """Returns the centralized MSAL app instance."""
        return _msal_app
    
    @staticmethod
    async def validate_ms_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validates a Microsoft Graph API access token.
        
        Args:
            token: The Microsoft access token to validate
            
        Returns:
            Tuple containing:
                - Boolean indicating if token is valid
                - Response data from validation request if successful, None otherwise
        """
        if not token:
            logger.warning("Cannot validate empty or None MS token")
            return False, None
            
        graph_url = f"{MS_GRAPH_BASE_URL}/me?$select=id"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # Run blocking requests.get in threadpool
            sync_graph_call = lambda: requests.get(graph_url, headers=headers)
            graph_response = await run_in_threadpool(sync_graph_call)
            
            if graph_response.status_code == 200:
                logger.info("MS Graph API token validation successful")
                return True, graph_response.json()
            elif graph_response.status_code == 401:
                logger.warning("MS token is expired or invalid (401)")
                return False, None
            else:
                logger.error(f"Unexpected status from MS Graph API: {graph_response.status_code}, Body: {graph_response.text}")
                return False, None
        except Exception as e:
            logger.error(f"Error validating MS token: {e}", exc_info=True)
            return False, None
    
    @staticmethod
    async def refresh_ms_token(db: Session, email: str) -> Optional[Dict[str, Any]]:
        """
        Refreshes a Microsoft access token using the stored refresh token.
        Updates the database with the new tokens if successful.
        
        Args:
            db: Database session
            email: Email of the user whose token needs refreshing
            
        Returns:
            Dict containing the refresh result if successful, None otherwise
        """
        if not email:
            logger.error("Cannot refresh token: email is required")
            return None
            
        # Get user with refresh token from DB
        user_db = get_user_with_refresh_token(db, email=email)
        
        if not user_db or not user_db.ms_refresh_token:
            logger.error(f"Cannot refresh token: User {email} not found or no refresh token stored in DB.")
            return None
            
        # Decrypt the stored refresh token
        encrypted_refresh_token = user_db.ms_refresh_token
        decrypted_refresh_token = decrypt_token(encrypted_refresh_token)
        
        if not decrypted_refresh_token:
            logger.error(f"Failed to decrypt refresh token for user {email}.")
            return None
            
        try:
            # Filter out reserved OIDC scopes before requesting refresh
            all_scopes = settings.MS_SCOPE_STR.split()
            resource_scopes = [s for s in all_scopes if s not in RESERVED_SCOPES]
            logger.debug(f"Requesting refresh token with filtered resource scopes: {resource_scopes}")
            
            # Execute token refresh with timeout
            try:
                # Define the synchronous function call
                sync_msal_call = lambda: _msal_app.acquire_token_by_refresh_token(
                    decrypted_refresh_token,
                    scopes=resource_scopes
                )
                # Run the sync call in threadpool and await its completion with timeout
                refresh_result = await asyncio.wait_for(
                    run_in_threadpool(sync_msal_call),
                    timeout=REFRESH_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.error(f"MSAL refresh for user {email} timed out after {REFRESH_TIMEOUT} seconds.")
                return None
                
            if "access_token" not in refresh_result:
                error_details = refresh_result.get('error_description', 'Unknown MSAL error')
                logger.error(f"MSAL refresh token acquisition failed for user {email}: {error_details}")
                
                # Handle invalid_grant error by clearing the refresh token
                if refresh_result.get("error") == "invalid_grant":
                    logger.warning(f"Refresh token for {email} is invalid or revoked. Clearing token.")
                    try:
                        update_user_refresh_token(db, user_email=email, encrypted_refresh_token=None)
                    except Exception as clear_err:
                        logger.error(f"Failed to clear refresh token from DB: {clear_err}", exc_info=True)
                
                return None
                
            # Token refresh successful
            new_ms_access_token = refresh_result['access_token']
            logger.info(f"Successfully refreshed MS token for user {email}.")
            
            # Check if a new refresh token was issued
            if "refresh_token" in refresh_result:
                new_ms_refresh_token = refresh_result['refresh_token']
                logger.info(f"New MS refresh token received for user {email}. Updating database.")
                encrypted_new_refresh = encrypt_token(new_ms_refresh_token)
                
                if encrypted_new_refresh:
                    # Calculate expiry time
                    expires_in = refresh_result.get('expires_in', 3600)
                    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    
                    # Update all token information in DB
                    try:
                        update_success = update_user_ms_tokens(
                            db=db,
                            user_email=email,
                            access_token=new_ms_access_token,
                            expiry=expiry,
                            refresh_token=encrypted_new_refresh
                        )
                        
                        if update_success:
                            logger.info(f"Successfully updated tokens in DB for {email}.")
                        else:
                            logger.warning(f"Update tokens call returned False for user {email}.")
                    except Exception as db_update_err:
                        logger.error(f"Failed to update tokens in DB: {db_update_err}", exc_info=True)
                else:
                    logger.error(f"Failed to encrypt new refresh token for {email}.")
            else:
                # New access token but no new refresh token
                # Update just the access token and expiry
                try:
                    expires_in = refresh_result.get('expires_in', 3600)
                    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    update_user_ms_tokens(
                        db=db,
                        user_email=email,
                        access_token=new_ms_access_token,
                        expiry=expiry
                    )
                except Exception as update_err:
                    logger.error(f"Failed to update access token in DB: {update_err}", exc_info=True)
            
            return refresh_result
            
        except Exception as e:
            logger.error(f"Unexpected error during MSAL refresh for {email}: {e}", exc_info=True)
            return None
    
    @staticmethod
    def create_user_jwt(user_id: str, email: str, ms_token: str, 
                      scopes: List[str] = None, 
                      expires_delta: Optional[timedelta] = None) -> Tuple[str, datetime]:
        """
        Creates a JWT token for a user with the Microsoft access token embedded.
        
        Args:
            user_id: The user's ID
            email: The user's email
            ms_token: Microsoft access token
            scopes: Optional list of scopes
            expires_delta: Optional timedelta for token expiration
            
        Returns:
            Tuple containing the JWT token and its expiry datetime
        """
        # Create JWT payload with the MS access token
        jwt_payload = {
            "sub": user_id,
            "email": email,
            "ms_token": ms_token
        }
        
        # Add scopes if provided
        if scopes:
            jwt_payload["scopes"] = scopes
            
        # Create and return the token
        return create_access_token(
            data=jwt_payload,
            expires_delta=expires_delta or timedelta(seconds=settings.JWT_EXPIRATION)
        )
    
    @staticmethod
    def extract_token_data(token: str) -> Dict[str, Any]:
        """
        Extracts and validates the data from a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Dict with token data if valid, empty dict if invalid
            
        Raises:
            JWTError: If token validation fails
        """
        if not token:
            return {}
            
        # Debug: decode without verification to check expiry
        try:
            debug_payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_signature": False, "verify_exp": False}
            )
            # Always use UTC for timestamp operations
            exp_time = datetime.fromtimestamp(debug_payload.get("exp", 0), tz=timezone.utc)
            iat_time = datetime.fromtimestamp(debug_payload.get("iat", 0), tz=timezone.utc)
            now_time = datetime.now(timezone.utc)
            
            # Compare timestamps in a timezone-aware manner
            time_until_expiry = (exp_time - now_time).total_seconds()
            
            logger.info(f"DEBUG JWT: Token issued at: {iat_time}, expires: {exp_time}, current time: {now_time}")
            logger.info(f"DEBUG JWT: Token expires in {time_until_expiry} seconds")
            logger.info(f"DEBUG JWT: Token secret: {settings.JWT_SECRET[:5]}... Algorithm: {settings.JWT_ALGORITHM}")
            
            # Check if token is already expired to provide better logging
            if time_until_expiry < 0:
                logger.warning(f"DEBUG JWT: Token is expired by {abs(time_until_expiry)} seconds")
            
            # Add debug logging for raw timestamps
            logger.debug(f"DEBUG JWT RAW: exp={debug_payload.get('exp')}, iat={debug_payload.get('iat')}, now={datetime.now().timestamp()}")
        except Exception as e:
            logger.error(f"DEBUG JWT: Failed to decode token for debugging: {e}")
        
        # Decode and validate the token with explicit leeway for clock skew
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"leeway": 60}  # Increase leeway for clock skew to 60 seconds
            )
            return payload
        except JWTError as e:
            logger.error(f"JWT Error during token decode: {e}")
            logger.error(f"JWT validation error: {str(e)}")
            raise
    
    @staticmethod
    def decode_jwt_unsafe(token: str) -> Dict[str, Any]:
        """
        Decodes a JWT token without validating signature or expiration.
        Used for debugging or extracting data from potentially expired tokens.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload or empty dict if decoding fails
        """
        try:
            # Decode without full verification just to check structure
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_signature": False, "verify_exp": False, "leeway": 30}
            )
            return payload
        except JWTError:
            return {}
    
    @staticmethod
    async def handle_token_refresh_flow(
        db: Session, 
        email: str, 
        user_id: str, 
        response: Response
    ) -> Optional[str]:
        """
        Handles the complete token refresh flow including database updates and cookie settings.
        
        Args:
            db: Database session
            email: User email
            user_id: User ID string
            response: FastAPI Response object for setting cookies
            
        Returns:
            New access token if refresh successful, None otherwise
        """
        refresh_result = await AuthService.refresh_ms_token(db, email)
        
        if not refresh_result or "access_token" not in refresh_result:
            # Refresh failed, clear cookie
            logger.error(f"Failed to refresh token for user {email}")
            response.delete_cookie(
                key=settings.JWT_COOKIE_NAME, 
                path="/", 
                domain=settings.COOKIE_DOMAIN, 
                samesite="Lax", 
                secure=True, 
                httponly=True
            )
            return None
            
        # Refresh successful
        new_ms_access_token = refresh_result["access_token"]
        
        # Filter scopes for new token
        all_scopes = settings.MS_SCOPE_STR.split()
        resource_scopes = [s for s in all_scopes if s not in RESERVED_SCOPES]
        
        # Create new JWT with refreshed MS token
        new_internal_token, expires_at = AuthService.create_user_jwt(
            user_id=user_id,
            email=email,
            ms_token=new_ms_access_token,
            scopes=resource_scopes
        )
        
        # Set new cookie
        response.set_cookie(
            key=settings.JWT_COOKIE_NAME,
            value=new_internal_token,
            httponly=True,
            secure=True,
            samesite="Lax",
            path="/",
            expires=expires_at
        )
        logger.info(f"Set new JWT cookie for user {email} after token refresh")
        
        return new_ms_access_token
    
    @staticmethod
    async def authenticate_and_validate_token(
        db: Session, 
        token: str, 
        response: Response
    ) -> Optional[User]:
        """
        Authenticates a user by validating their JWT token and MS token,
        refreshing tokens if needed.
        
        Args:
            db: Database session
            token: JWT token string
            response: FastAPI Response object
            
        Returns:
            User object if authentication successful, None otherwise
        """
        if not token:
            logger.warning("Cannot authenticate with empty token")
            return None
            
        try:
            # Extract data from JWT
            payload = AuthService.extract_token_data(token)
            email = payload.get("email")
            user_id = payload.get("sub")
            ms_token = payload.get("ms_token")
            
            if not email or not user_id:
                logger.error("JWT missing required fields (email or sub)")
                return None
                
            # Validate MS token
            is_valid, _ = await AuthService.validate_ms_token(ms_token)
            
            if is_valid:
                # Token is valid, fetch user and return
                validated_ms_token = ms_token
            else:
                # Token invalid, attempt refresh
                validated_ms_token = await AuthService.handle_token_refresh_flow(
                    db, email, user_id, response
                )
                
                if not validated_ms_token:
                    # Refresh failed
                    return None
            
            # Fetch user from DB
            user_db = get_user_full_instance(db, email=email)
            if not user_db:
                logger.error(f"User {email} not found in DB after token validation")
                return None
                
            # Create and return user model
            user = User.model_validate(user_db)
            user.ms_access_token = validated_ms_token
            
            return user
            
        except JWTError as e:
            logger.error(f"JWT validation error: {e}")
            # Clear cookie on JWT error
            response.delete_cookie(
                key=settings.JWT_COOKIE_NAME,
                path="/",
                domain=settings.COOKIE_DOMAIN,
                samesite="Lax",
                secure=True,
                httponly=True
            )
            return None
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}", exc_info=True)
            return None 