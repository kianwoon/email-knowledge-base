import logging
from cryptography.fernet import Fernet, InvalidToken
import base64 # Import base64
from app.config import settings

logger = logging.getLogger(__name__)

# It's generally safer to initialize Fernet once if the key doesn't change
# Or fetch the key each time if it might be rotated (less likely for this use case)
try:
    _key = settings.ENCRYPTION_KEY
    if not _key:
        logger.critical("ENCRYPTION_KEY is not set in settings. Cannot perform encryption/decryption.")
        # Depending on your app's needs, you might raise an error here to prevent startup
        # raise ValueError("ENCRYPTION_KEY not configured.")
        _fernet = None
    else:
        _fernet = Fernet(_key.encode())
except Exception as e:
    logger.critical(f"Failed to initialize Fernet for encryption/decryption: {e}", exc_info=True)
    _fernet = None

def encrypt_token(token: str) -> str | None:
    """Encrypts a string token and returns a base64 encoded string."""
    if not _fernet:
        logger.error("Encryption service not available. Cannot encrypt token.")
        return None
    if not token:
        logger.warning("Attempted to encrypt an empty token.")
        return None
    try:
        encrypted_bytes = _fernet.encrypt(token.encode('utf-8'))
        # Encode the encrypted bytes as base64 string for DB storage
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
    except Exception as e:
        logger.error(f"Error during token encryption: {e}", exc_info=True)
        return None

def decrypt_token(encrypted_base64_token: str) -> str | None:
    """Accepts a base64 encoded string, decodes it, and decrypts it."""
    if not _fernet:
        logger.error("Encryption service not available. Cannot decrypt token.")
        return None
    if not encrypted_base64_token:
        logger.warning("Attempted to decrypt empty base64 string.")
        return None
    try:
        # Decode the base64 string back into bytes
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_base64_token.encode('utf-8'))
        
        decrypted_bytes = _fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')
    except (InvalidToken, base64.binascii.Error, ValueError) as e: # Catch potential base64/decryption errors
        logger.error(f"Invalid token or base64 data provided for decryption: {e}")
        return None
    except Exception as e:
        logger.error(f"Error during token decryption: {e}", exc_info=True)
        return None 