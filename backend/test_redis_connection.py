#!/usr/bin/env python
"""
Test script to verify Redis connection and locking mechanism.
Run this before deployment to ensure Redis is properly configured.
"""

import redis
import os
import time
import uuid
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get Redis URL from environment
redis_url = os.getenv("CELERY_BROKER_URL")
if not redis_url:
    raise ValueError("CELERY_BROKER_URL environment variable not set")

def test_redis_connection():
    """Test basic Redis connection and operations"""
    logger.info(f"Testing Redis connection to {redis_url}")
    try:
        # Connect to Redis
        r = redis.from_url(redis_url)
        
        # Test SET operation
        test_key = f"test:connection:{uuid.uuid4()}"
        test_value = "Connection test successful"
        r.set(test_key, test_value, ex=60)  # Expire in 60 seconds
        
        # Test GET operation
        result = r.get(test_key)
        if result and result.decode() == test_value:
            logger.info("✅ Redis connection and basic operations successful")
            return True
        else:
            logger.error(f"❌ Redis GET operation failed, got: {result}")
            return False
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {str(e)}")
        return False

def test_locking_mechanism():
    """Test Redis locking mechanism"""
    logger.info("Testing Redis locking mechanism")
    try:
        # Connect to Redis
        r = redis.from_url(redis_url)
        
        # Test lock key
        lock_key = f"lock:test:{uuid.uuid4()}"
        token = str(uuid.uuid4())
        
        # Try to acquire lock
        logger.info(f"Acquiring lock '{lock_key}' with token '{token}'")
        acquired = r.set(lock_key, token, nx=True, ex=10)
        
        if not acquired:
            logger.error("❌ Failed to acquire lock when it should be available")
            return False
            
        logger.info("✅ Successfully acquired lock")
        
        # Try to acquire same lock again (should fail)
        second_token = str(uuid.uuid4())
        second_acquired = r.set(lock_key, second_token, nx=True, ex=10)
        
        if second_acquired:
            logger.error("❌ Acquired lock when it should have been locked")
            return False
            
        logger.info("✅ Failed to acquire locked resource as expected")
        
        # Release the lock with Lua script
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        
        # Execute script
        released = r.eval(script, 1, lock_key, token)
        
        if not released:
            logger.error("❌ Failed to release lock")
            return False
            
        logger.info("✅ Successfully released lock")
        
        # Check if lock is gone
        exists = r.exists(lock_key)
        
        if exists:
            logger.error("❌ Lock still exists after release")
            return False
            
        logger.info("✅ Lock no longer exists after release")
        
        # Test lock expiration
        logger.info("Testing lock expiration (waiting 3 seconds)...")
        short_lock_key = f"lock:test_expiration:{uuid.uuid4()}"
        r.set(short_lock_key, token, nx=True, ex=2)  # Expire in 2 seconds
        
        time.sleep(3)  # Wait longer than expiration
        
        # Check if lock expired
        expired = not r.exists(short_lock_key)
        
        if not expired:
            logger.error("❌ Lock did not expire as expected")
            return False
            
        logger.info("✅ Lock expiration works correctly")
        
        return True
    except Exception as e:
        logger.error(f"❌ Lock test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Run tests
    connection_ok = test_redis_connection()
    if connection_ok:
        locking_ok = test_locking_mechanism()
    else:
        locking_ok = False
    
    # Print summary
    print("\n--- Redis Test Summary ---")
    print(f"Connection Test: {'✅ PASSED' if connection_ok else '❌ FAILED'}")
    print(f"Locking Test: {'✅ PASSED' if locking_ok else '❌ FAILED'}")
    print(f"Overall Status: {'✅ PASSED' if connection_ok and locking_ok else '❌ FAILED'}")
    
    # Exit with appropriate code
    import sys
    sys.exit(0 if connection_ok and locking_ok else 1) 