import logging
import time
import uuid
import redis
from redis.exceptions import LockError
from typing import Optional, Callable, Any
from functools import wraps

from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class RedisLock:
    """
    Redis-based distributed locking mechanism to prevent overlapping execution 
    of tasks with the same key (e.g., same user_id).
    """
    def __init__(
        self,
        redis_url: str = settings.CELERY_BROKER_URL,
        default_timeout: int = 3600,  # 1 hour default lock timeout
        retry_interval: float = 0.1,
        max_retries: int = 3,
    ):
        """
        Initialize the Redis lock client.
        
        Args:
            redis_url: Redis connection URL (defaults to CELERY_BROKER_URL)
            default_timeout: Default lock expiration time in seconds
            retry_interval: Time to wait between retries in seconds
            max_retries: Maximum number of times to retry acquiring the lock
        """
        # Extract Redis connection details from the URL
        try:
            self.redis_client = redis.from_url(redis_url)
            self.default_timeout = default_timeout
            self.retry_interval = retry_interval
            self.max_retries = max_retries
            logger.info(f"Redis lock initialized with connection to {redis_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis lock: {str(e)}")
            raise

    def acquire_lock(
        self, 
        lock_key: str, 
        timeout: Optional[int] = None, 
        retry: bool = True,
        owner: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Acquire a Redis lock with the given key.
        
        Args:
            lock_key: Unique identifier for the lock
            timeout: Lock expiration time in seconds (None uses default)
            retry: Whether to retry if lock acquisition fails
            owner: Optional owner identifier for the lock
            
        Returns:
            Tuple of (success, token) where success is a boolean indicating if 
            lock was acquired, and token is the lock identifier or None
        """
        # Prefix the lock key to avoid collisions with other Redis keys
        lock_name = f"lock:{lock_key}"
        # Generate a unique token for this lock acquisition
        token = owner or str(uuid.uuid4())
        timeout_sec = timeout or self.default_timeout
        
        retries = 0
        while True:
            # Try to set the lock key with NX (only if it doesn't exist)
            success = self.redis_client.set(
                lock_name, token, nx=True, ex=timeout_sec
            )
            
            if success:
                logger.info(f"Lock '{lock_name}' acquired with token '{token}'")
                return True, token
            
            if not retry or retries >= self.max_retries:
                logger.warning(f"Failed to acquire lock '{lock_name}' after {retries} retries")
                return False, None
            
            # Wait before retry
            time.sleep(self.retry_interval)
            retries += 1
    
    def release_lock(self, lock_key: str, token: str) -> bool:
        """
        Release a previously acquired lock.
        
        Args:
            lock_key: The lock key that was used to acquire the lock
            token: The token returned when acquiring the lock
            
        Returns:
            Boolean indicating if the lock was successfully released
        """
        lock_name = f"lock:{lock_key}"
        
        # Use a Lua script to ensure we only delete the key if it has our token
        # This prevents accidentally deleting a lock that was reacquired by another process
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        
        try:
            # Execute the release script
            result = self.redis_client.eval(script, 1, lock_name, token)
            if result:
                logger.info(f"Lock '{lock_name}' released with token '{token}'")
                return True
            else:
                logger.warning(f"Could not release lock '{lock_name}' with token '{token}' - lock not found or token doesn't match")
                return False
        except Exception as e:
            logger.error(f"Error releasing lock '{lock_name}': {str(e)}")
            return False
            
    def extend_lock(self, lock_key: str, token: str, timeout: Optional[int] = None) -> bool:
        """
        Extend the expiration time of an existing lock.
        
        Args:
            lock_key: The lock key that was used to acquire the lock
            token: The token returned when acquiring the lock
            timeout: New expiration time in seconds (None uses default)
            
        Returns:
            Boolean indicating if the lock was successfully extended
        """
        lock_name = f"lock:{lock_key}"
        timeout_sec = timeout or self.default_timeout
        
        # Use a Lua script to ensure we only extend the key if it has our token
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('expire', KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        
        try:
            # Execute the extension script
            result = self.redis_client.eval(script, 1, lock_name, token, timeout_sec)
            if result:
                logger.info(f"Lock '{lock_name}' extended with token '{token}' for {timeout_sec} seconds")
                return True
            else:
                logger.warning(f"Could not extend lock '{lock_name}' with token '{token}' - lock not found or token doesn't match")
                return False
        except Exception as e:
            logger.error(f"Error extending lock '{lock_name}': {str(e)}")
            return False
    
    def is_locked(self, lock_key: str) -> bool:
        """
        Check if a lock exists for the given key.
        
        Args:
            lock_key: The lock key to check
            
        Returns:
            Boolean indicating if the lock exists
        """
        lock_name = f"lock:{lock_key}"
        return self.redis_client.exists(lock_name) > 0


# Function decorator for tasks to ensure they don't run concurrently
def with_lock(key_function: Callable[[Any], str], timeout: Optional[int] = None, block: bool = False):
    """
    Decorator to ensure a function is executed with a Redis lock.
    
    Args:
        key_function: Function that takes the same args as the wrapped function and returns a lock key
        timeout: Lock timeout in seconds
        block: Whether to block waiting for the lock or return immediately
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create the Redis lock
            redis_lock = RedisLock()
            
            # Get the lock key from the function arguments
            lock_key = key_function(*args, **kwargs)
            
            # Try to acquire the lock
            success, token = redis_lock.acquire_lock(lock_key, timeout, retry=block)
            
            if not success:
                logger.warning(f"Function {func.__name__} skipped execution: lock for '{lock_key}' already held")
                return None  # Skip execution
            
            try:
                # Call the original function
                result = func(*args, **kwargs)
                return result
            finally:
                # Always release the lock when done
                redis_lock.release_lock(lock_key, token)
                
        return wrapper
    return decorator 