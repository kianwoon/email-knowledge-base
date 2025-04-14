import logging
from cryptography.fernet import Fernet, InvalidToken
import base64 # Import base64
from app.config import settings

logger = logging.getLogger(__name__)

# Remove the global Fernet instance initialization
# try:
#     _key = settings.ENCRYPTION_KEY
#     if not _key:
#         logger.critical("ENCRYPTION_KEY is not set in settings. Cannot perform encryption/decryption.")
#         _fernet = None
#     else:
#         _fernet = Fernet(_key.encode())
# except Exception as e:
#     logger.critical(f"Failed to initialize Fernet for encryption/decryption: {e}", exc_info=True)
#     _fernet = None

def get_fernet_instance() -> Fernet | None:
    """Helper function to get a Fernet instance based on current settings."""
    key = settings.ENCRYPTION_KEY
    # Log the key being used (or its absence)
    if not key:
        logger.critical("ENCRYPTION_KEY is not set in settings. Cannot get Fernet instance.")
        return None
    else:
        # Log a portion of the key for verification without exposing the whole key
        key_preview = key[:4] + "..." + key[-4:]
        logger.info(f"[Get Fernet] Using ENCRYPTION_KEY starting with '{key_preview}'.")
    try:
        # Ensure the key is bytes
        key_bytes = key.encode()
        # Validate key length if necessary (Fernet expects base64 encoded 32 bytes)
        # Example basic check (might need refinement based on how key is generated):
        # if len(base64.urlsafe_b64decode(key_bytes)) != 32:
        #    logger.critical("Invalid ENCRYPTION_KEY length after base64 decode.")
        #    return None
        return Fernet(key_bytes)
    except Exception as e:
        logger.critical(f"Failed to create Fernet instance from key: {e}", exc_info=True)
        return None

def encrypt_token(token: str) -> str | None:
    """Encrypts a string token and returns a base64 encoded string."""
    fernet = get_fernet_instance()
    if not fernet:
        logger.error("Encryption service not available (Fernet init failed). Cannot encrypt token.")
        return None
    if not token:
        logger.warning("Attempted to encrypt an empty token.")
        return None
    try:
        # Use the fetched Fernet instance
        encrypted_bytes = fernet.encrypt(token.encode('utf-8'))
        # Encode the encrypted bytes as base64 string for DB storage
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
    except Exception as e:
        logger.error(f"Error during token encryption: {e}", exc_info=True)
        return None

def decrypt_token(encrypted_base64_token: str) -> str | None:
    """Accepts a base64 encoded string, decodes it, and decrypts it."""
    fernet = get_fernet_instance()
    if not fernet:
        logger.error("Encryption service not available (Fernet init failed). Cannot decrypt token.")
        return None
    if not encrypted_base64_token:
        logger.warning("Attempted to decrypt empty base64 string.")
        return None
    try:
        # Decode the base64 string back into bytes
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_base64_token.encode('utf-8'))
        
        # Use the fetched Fernet instance
        decrypted_bytes = fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')
    except (InvalidToken, base64.binascii.Error, ValueError) as e: # Catch potential base64/decryption errors
        logger.error(f"Invalid token or base64 data provided for decryption: {e}")
        return None
    except Exception as e:
        logger.error(f"Error during token decryption: {e}", exc_info=True)
        return None 