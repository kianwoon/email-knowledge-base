import os
import base64
import logging
from cryptography.fernet import Fernet
# from cryptography.exceptions import InvalidToken # Remove direct import
import cryptography.exceptions # Import the module itself

logger = logging.getLogger(__name__)

# --- CRITICAL: Load the encryption key from environment variables --- 
# Generate a key using: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Store the output in your .env file as JARVIS_TOKEN_ENCRYPTION_KEY=your_generated_key_here
_key_str = os.getenv("JARVIS_TOKEN_ENCRYPTION_KEY")

if not _key_str:
    logger.critical("JARVIS_TOKEN_ENCRYPTION_KEY environment variable not set! Encryption service cannot function.")
    # Option 1: Raise an error immediately to prevent the app from starting incorrectly
    raise ValueError("JARVIS_TOKEN_ENCRYPTION_KEY is not set in the environment.")
    # Option 2: Set _fernet to None and handle it in encrypt/decrypt (less safe)
    # _fernet = None
else:
    try:
        # The key must be URL-safe base64 encoded
        _key = base64.urlsafe_b64encode(_key_str.encode()) if len(base64.urlsafe_b64decode(_key_str.encode())) != 32 else _key_str.encode()
        # Ensure the key is the correct length for Fernet after potential encoding correction
        if len(base64.urlsafe_b64decode(_key)) != 32:
             raise ValueError("JARVIS_TOKEN_ENCRYPTION_KEY is not a valid Fernet key length after encoding check.")
        _fernet = Fernet(_key)
        logger.info("Encryption service initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize Fernet encryption with JARVIS_TOKEN_ENCRYPTION_KEY: {e}", exc_info=True)
        raise ValueError(f"Invalid JARVIS_TOKEN_ENCRYPTION_KEY: {e}")

def encrypt_token(raw_token: str) -> bytes:
    """Encrypts a raw token string using Fernet."""
    if not _fernet:
        logger.error("Encryption service not initialized. Cannot encrypt token.")
        raise RuntimeError("Encryption service is not available.")
    if not raw_token:
        raise ValueError("Cannot encrypt an empty token.")
    try:
        encrypted = _fernet.encrypt(raw_token.encode('utf-8'))
        return encrypted
    except Exception as e:
        logger.error(f"Error encrypting token: {e}", exc_info=True)
        raise

def decrypt_token(encrypted_token: bytes) -> str:
    """Decrypts an encrypted token (bytes) using Fernet."""
    if not _fernet:
        logger.error("Encryption service not initialized. Cannot decrypt token.")
        raise RuntimeError("Encryption service is not available.")
    if not encrypted_token:
        raise ValueError("Cannot decrypt an empty token.")
    try:
        decrypted_bytes = _fernet.decrypt(encrypted_token)
        return decrypted_bytes.decode('utf-8')
    except cryptography.exceptions.InvalidToken: # Use full path to exception
        logger.error("Failed to decrypt token: InvalidToken (likely wrong key or corrupted data)")
        raise ValueError("Invalid encrypted token or incorrect decryption key.")
    except Exception as e:
        logger.error(f"Error decrypting token: {e}", exc_info=True)
        raise 