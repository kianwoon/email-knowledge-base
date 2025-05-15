# backend/app/utils/auth_utils.py

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from jose import jwt

from app.config import settings

logger = logging.getLogger(__name__)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> Tuple[str, datetime]:
    """Creates a JWT access token.

    Args:
        data: Dictionary payload to include in the token.
        expires_delta: Optional timedelta for token expiration.
                     Defaults to JWT_EXPIRATION seconds from settings.

    Returns:
        A tuple containing the encoded JWT string and the expiry datetime.
    """
    to_encode = data.copy()
    # Explicitly use UTC timezone for JWT operations
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(seconds=settings.JWT_EXPIRATION)
    
    logger.info(f"DEBUG JWT CREATE: Current time (UTC): {now}, Expiry time (UTC): {expire}")
    logger.info(f"DEBUG JWT CREATE: JWT_EXPIRATION from settings: {settings.JWT_EXPIRATION} seconds")
    logger.info(f"DEBUG JWT CREATE: JWT_SECRET: {settings.JWT_SECRET[:5]}..., Algorithm: {settings.JWT_ALGORITHM}")
    
    # Convert to datetime.timestamp for consistent serialization
    to_encode.update({"exp": int(expire.timestamp()), "iat": int(now.timestamp())})
    
    # Ensure 'sub' (user ID) and 'email' are present for user tokens
    if "ms_token" in to_encode: # Heuristic check if it's a user session token
        if "sub" not in to_encode or "email" not in to_encode:
            logger.error("Missing 'sub' or 'email' in data for JWT creation containing 'ms_token'.")
            raise ValueError("Missing 'sub' or 'email' for user session token creation")
            
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    logger.debug(f"Created JWT with expiry: {expire}")
    
    # Debug: decode to verify contents
    try:
        decoded = jwt.decode(
            encoded_jwt,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False}  # Skip expiry check for debug
        )
        logger.info(f"DEBUG JWT CREATE: Decoded token exp: {decoded.get('exp')}, iat: {decoded.get('iat')}")
    except Exception as e:
        logger.error(f"DEBUG JWT CREATE: Error decoding token right after creation: {e}")
    
    return encoded_jwt, expire

# Placeholder for refresh_ms_token if we decide to extract it later
# async def refresh_ms_token(...): ... 