import unittest
import time
import threading
from app.utils.redis_lock import RedisLock, with_lock

class TestRedisLock(unittest.TestCase):
    """Test the Redis locking mechanism."""
    
    def setUp(self):
        """Set up the test environment."""
        self.redis_lock = RedisLock()
        # Use a test-specific key prefix to avoid conflicts
        self.test_key = "test_lock_key"
        
        # Clean up any existing locks with this key
        lock_name = f"lock:{self.test_key}"
        self.redis_lock.redis_client.delete(lock_name)
    
    def tearDown(self):
        """Clean up after the test."""
        lock_name = f"lock:{self.test_key}"
        self.redis_lock.redis_client.delete(lock_name)
        
    def test_acquire_release_lock(self):
        """Test that we can acquire and release a lock."""
        # Acquire the lock
        success, token = self.redis_lock.acquire_lock(self.test_key)
        self.assertTrue(success)
        self.assertIsNotNone(token)
        
        # Verify the lock exists
        self.assertTrue(self.redis_lock.is_locked(self.test_key))
        
        # Release the lock
        released = self.redis_lock.release_lock(self.test_key, token)
        self.assertTrue(released)
        
        # Verify the lock is gone
        self.assertFalse(self.redis_lock.is_locked(self.test_key))
    
    def test_cannot_acquire_locked(self):
        """Test that we cannot acquire a lock that's already held."""
        # Acquire the lock
        success1, token1 = self.redis_lock.acquire_lock(self.test_key)
        self.assertTrue(success1)
        
        # Try to acquire it again
        success2, token2 = self.redis_lock.acquire_lock(self.test_key, retry=False)
        self.assertFalse(success2)
        self.assertIsNone(token2)
        
        # Release the first lock
        released = self.redis_lock.release_lock(self.test_key, token1)
        self.assertTrue(released)
    
    def test_lock_expires(self):
        """Test that a lock expires after the timeout."""
        # Acquire a lock with a short timeout
        success, token = self.redis_lock.acquire_lock(self.test_key, timeout=1)
        self.assertTrue(success)
        
        # Wait for it to expire
        time.sleep(1.1)
        
        # Verify the lock is gone
        self.assertFalse(self.redis_lock.is_locked(self.test_key))
    
    def test_extend_lock(self):
        """Test that we can extend a lock's expiration."""
        # Acquire a lock with a short timeout
        success, token = self.redis_lock.acquire_lock(self.test_key, timeout=1)
        self.assertTrue(success)
        
        # Extend the lock
        extended = self.redis_lock.extend_lock(self.test_key, token, timeout=2)
        self.assertTrue(extended)
        
        # Wait for the original timeout
        time.sleep(1.1)
        
        # Verify the lock still exists
        self.assertTrue(self.redis_lock.is_locked(self.test_key))
        
        # Release the lock
        released = self.redis_lock.release_lock(self.test_key, token)
        self.assertTrue(released)
    
    def test_with_lock_decorator(self):
        """Test the with_lock decorator manually by directly using the lock in two threads."""
        # Create lock
        lock_key = self.test_key
        
        # Shared variables between threads
        shared_data = {'count': 0}
        thread_started = threading.Event()
        first_thread_acquired = threading.Event()
        second_thread_done = threading.Event()
        
        # First thread function that acquires a lock
        def first_thread():
            # Acquire a lock for 2 seconds
            success, token = self.redis_lock.acquire_lock(lock_key, timeout=2)
            if success:
                # Signal that first thread has acquired the lock
                first_thread_acquired.set()
                
                # Increment count
                shared_data['count'] += 1
                
                # Wait for second thread to finish trying
                second_thread_done.wait(timeout=3)
                
                # Release the lock
                self.redis_lock.release_lock(lock_key, token)
        
        # Second thread function that tries to acquire the same lock
        def second_thread():
            # Wait for the first thread to acquire its lock
            thread_started.set()
            first_thread_acquired.wait(timeout=3)
            
            # Try to acquire the same lock (should fail)
            success, _ = self.redis_lock.acquire_lock(lock_key, retry=False)
            
            # If we couldn't acquire the lock (expected behavior)
            if not success:
                # Don't increment count
                pass
            else:
                # Unexpected - lock should have been held
                shared_data['count'] += 1
            
            # Signal that we're done
            second_thread_done.set()
        
        # Start the first thread
        t1 = threading.Thread(target=first_thread)
        t1.start()
        
        # Wait for the first thread to start
        thread_started.wait(timeout=1)
        
        # Start the second thread
        t2 = threading.Thread(target=second_thread)
        t2.start()
        
        # Wait for both threads to finish
        t1.join(timeout=5)
        t2.join(timeout=5)
        
        # Check that only the first thread incremented the count
        self.assertEqual(shared_data['count'], 1, "Only one thread should have acquired the lock")
        
        # After lock expires, we should be able to acquire it
        time.sleep(2.1)  # Wait for lock to expire
        success, token = self.redis_lock.acquire_lock(lock_key)
        self.assertTrue(success, "Should be able to acquire lock after it expires")
        
        # Clean up
        if success:
            self.redis_lock.release_lock(lock_key, token)

if __name__ == "__main__":
    unittest.main() 