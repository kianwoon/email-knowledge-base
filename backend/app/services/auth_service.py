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
            refresh_result = None
            MAX_REFRESH_ATTEMPTS = 2
            REFRESH_RETRY_DELAY = 2  # seconds

            for attempt in range(1, MAX_REFRESH_ATTEMPTS + 1):
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
                    # If successful, break the loop
                    break 
                except asyncio.TimeoutError:
                    logger.error(f"MSAL refresh for user {email} timed out on attempt {attempt}/{MAX_REFRESH_ATTEMPTS} after {REFRESH_TIMEOUT} seconds.")
                    if attempt < MAX_REFRESH_ATTEMPTS:
                        logger.info(f"Retrying MSAL refresh for user {email} in {REFRESH_RETRY_DELAY} seconds...")
                        await asyncio.sleep(REFRESH_RETRY_DELAY)
                    else:
                        logger.error(f"All {MAX_REFRESH_ATTEMPTS} MSAL refresh attempts failed for user {email} due to timeout.")
                        return None # All retries failed
            
            if refresh_result is None: # Should only happen if all retries fail due to timeout and return None was hit
                # This case is technically covered by the return None in the loop, 
                # but as a safeguard if logic changes.
                logger.error(f"MSAL refresh for user {email} failed after all retries (refresh_result is None).")
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
    def create_user_jwt(user_id: str, email: str, 
                      scopes: List[str] = None, 
                      expires_delta: Optional[timedelta] = None) -> Tuple[str, datetime]:
        """
        Creates a JWT token for a user.
        NOTE: Does NOT embed the MS token anymore.
        
        Args:
            user_id: The user's internal UUID
            email: The user's email
            scopes: Optional list of scopes
            expires_delta: Optional timedelta for token expiration
            
        Returns:
            Tuple containing the JWT token and its expiry datetime
        """
        # Create JWT payload WITHOUT the MS access token
        jwt_payload = {
            "sub": user_id,
            "email": email,
            # "ms_token": ms_token # DO NOT embed the MS token in the JWT
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
            logger.debug(f"Attempting final JWT decode and validation for token: {token[:20]}...")
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"leeway": 60}  # Increase leeway for clock skew to 60 seconds
            )
            logger.debug(f"JWT decode successful for token: {token[:20]}. Payload email: {payload.get('email')}")
            return payload
        except jwt.ExpiredSignatureError as ese:
            logger.error(f"JWT EXPIRED (within extract_token_data) for token {token[:20]}...: {ese}")
            raise
        except JWTError as e:
            # General JWTError (signature, format, etc.)
            logger.error(f"JWT VALIDATION ERROR (within extract_token_data) for token {token[:20]}...: {e}. Type: {type(e)}")
            logger.error(f"JWT validation error (re-raising): {str(e)}")
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
            payload = AuthService.extract_token_data(token) # This can throw JWTError (including ExpiredSignatureError)
            email = payload.get("email")
            user_id = payload.get("sub") # This is the internal DB User ID (UUID)
            
            if not email or not user_id:
                logger.error("JWT missing required fields (email or sub/user_id)")
                # It's possible extract_token_data itself threw an error handled by outer JWTError block
                return None # Should be caught by JWTError if token was malformed
                
            # Fetch user from DB 
            user_db = get_user_full_instance(db, email=email) # Assuming this fetches the full user object
            if not user_db:
                logger.error(f"User {email} (ID: {user_id}) not found in DB based on JWT claims.")
                return None # User in JWT doesn't exist in DB
            
            # At this point, the local JWT was valid (not expired, good signature etc.)
            # Now, check the MS token associated with the user
            ms_token = user_db.ms_access_token
            
            is_ms_token_valid = False
            if ms_token:
                is_ms_token_valid, _ = await AuthService.validate_ms_token(ms_token)
            
            if is_ms_token_valid:
                validated_ms_token = ms_token
                logger.info(f"Existing MS token for user {email} is valid.")
            else:
                logger.info(f"MS token for user {email} is invalid or missing. Attempting MS token refresh flow.")
                # The user_id from the local JWT (which is db_user.id) is passed here
                validated_ms_token = await AuthService.handle_token_refresh_flow(
                    db, email, user_id, response # response object is passed to set new local JWT cookie
                )
                
                if not validated_ms_token:
                    logger.warning(f"MS Token refresh failed for user {email}. Session ending.")
                    # handle_token_refresh_flow should have deleted the cookie.
                    return None
            
            user = User.model_validate(user_db)
            user.ms_access_token = validated_ms_token 
            logger.info(f"Successfully authenticated user {email} with valid local JWT and MS token (potentially refreshed).")
            return user
            
        except jwt.ExpiredSignatureError as e:
            logger.warning(f"LOCAL JWT EXPIRED (Caught in authenticate_and_validate_token) for user: {e}. Attempting full session refresh via MS token.")
            try:
                # Try to get email/user_id from the expired token to initiate refresh
                unsafe_payload = AuthService.decode_jwt_unsafe(token) # Use unsafe decode for expired token
                email_from_expired_token = unsafe_payload.get("email")
                user_id_from_expired_token = unsafe_payload.get("sub") # This is db_user.id

                if not email_from_expired_token or not user_id_from_expired_token:
                    logger.error("Could not extract email/user_id from expired local JWT for refresh.")
                    response.delete_cookie(key=settings.JWT_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=settings.COOKIE_SECURE, httponly=True)
                    return None

                logger.info(f"Attempting to refresh MS token and reissue local JWT for user {email_from_expired_token} due to expired local JWT.")
                
                # This will attempt MS refresh, and if successful, create_user_jwt and set_cookie via response
                refreshed_ms_token_after_local_jwt_expiry = await AuthService.handle_token_refresh_flow(
                    db, email_from_expired_token, user_id_from_expired_token, response 
                )

                if not refreshed_ms_token_after_local_jwt_expiry:
                    logger.warning(f"Full session refresh failed for user {email_from_expired_token} after local JWT expired. Cookie should have been deleted by handle_token_refresh_flow.")
                    return None # handle_token_refresh_flow deletes cookie on failure
                
                # If refresh was successful, a new local JWT cookie is set. Now fetch user and return.
                user_db_after_refresh = get_user_full_instance(db, email=email_from_expired_token)
                if not user_db_after_refresh:
                    logger.error(f"User {email_from_expired_token} not found in DB after successful session refresh. This should not happen.")
                    # This case implies a serious inconsistency.
                    response.delete_cookie(key=settings.JWT_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=settings.COOKIE_SECURE, httponly=True)
                    return None 
                
                user_model_after_refresh = User.model_validate(user_db_after_refresh)
                # The refreshed_ms_token_after_local_jwt_expiry is the new MS access token
                user_model_after_refresh.ms_access_token = refreshed_ms_token_after_local_jwt_expiry 
                logger.info(f"Successfully re-authenticated user {email_from_expired_token} after local JWT expiry and MS refresh. New local JWT cookie set.")
                return user_model_after_refresh

            except Exception as refresh_exc: # Catch any error during this specific refresh flow
                logger.error(f"Exception during local JWT expiry refresh flow: {refresh_exc}", exc_info=True)
                response.delete_cookie(key=settings.JWT_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=settings.COOKIE_SECURE, httponly=True)
                return None

        except JWTError as e: # Catch other JWTError (invalid signature, malformed, etc.)
            logger.error(f"OTHER JWT ERROR (Caught in authenticate_and_validate_token). Type: {type(e)}, Error: {e}. Deleting cookie.")
            response.delete_cookie(key=settings.JWT_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=settings.COOKIE_SECURE, httponly=True)
            return None
        except Exception as e:
            logger.error(f"UNEXPECTED AUTHENTICATION ERROR (Caught in authenticate_and_validate_token): {e}", exc_info=True)
            # It's safer to ensure cookie is cleared on any unexpected auth error
            response.delete_cookie(key=settings.JWT_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN, samesite="Lax", secure=settings.COOKIE_SECURE, httponly=True)
            return None 