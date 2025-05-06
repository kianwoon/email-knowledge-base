import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from app.db.session import get_db
from app.celery_app import celery_app
from app.models.user import UserDB
from app.services.outlook import OutlookService 
from app.services.auth_service import AuthService
from app.tasks.email_tasks import process_user_emails
from app.config import settings
from app.utils.security import decrypt_token
from app.utils.redis_lock import with_lock, RedisLock

# Configure logging
logger = logging.getLogger(__name__)

# Constants for frequency mapping
FREQUENCY_INTERVALS = {
    "1min": timedelta(minutes=1),
    "15min": timedelta(minutes=15),
    "30min": timedelta(minutes=30),
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1)
}

# Default to one month ago if no start date is provided
DEFAULT_START_PERIOD = timedelta(days=30)


@celery_app.task(name="tasks.outlook_sync.dispatch_sync_tasks")
def dispatch_sync_tasks():
    """
    Main scheduler task that checks for users with sync enabled
    and dispatches individual sync tasks based on their configured frequencies.
    This task is meant to run every 15 minutes via Celery Beat.
    """
    # TEMP: Added log to check if task is being executed by worker
    logger.info("********* DEBUG: dispatch_sync_tasks task entered *********")
    
    logger.info("Starting Outlook sync task dispatcher")
    
    try:
        # Create a database session directly since we're not in an async context
        session_local = get_db()
        db = next(session_local)
        
        # Check if there are any users with outlook sync enabled at all
        # If no users have it enabled, exit early
        # Using a more robust method with PostgreSQL JSON functions instead of LIKE pattern matching
        query = """
            SELECT COUNT(*) 
            FROM users 
            WHERE outlook_sync_config IS NOT NULL 
            AND outlook_sync_config::jsonb ? 'enabled' 
            AND outlook_sync_config::jsonb ->> 'enabled' = 'true'
        """
        users_with_enabled_sync = db.execute(text(query)).scalar()
        
        if users_with_enabled_sync == 0:
            logger.info("No users have Outlook sync enabled, skipping dispatch")
            return
            
        # Get all users with outlook_sync_config that have sync enabled
        # Using a proper JSON query instead of pattern matching
        query = """
            SELECT * 
            FROM users 
            WHERE outlook_sync_config IS NOT NULL 
            AND outlook_sync_config::jsonb ? 'enabled' 
            AND outlook_sync_config::jsonb ->> 'enabled' = 'true'
        """
        users_with_config = db.execute(text(query)).all()
        
        logger.info(f"Found {len(users_with_config)} users with Outlook sync configurations")
        
        now = datetime.now(timezone.utc)
        
        for user in users_with_config:
            try:
                # Parse the sync configuration
                config = json.loads(user.outlook_sync_config)
                
                # Skip if sync is not enabled (double-check)
                if not config.get("enabled", False):
                    logger.debug(f"Sync disabled for user {user.email}, skipping")
                    continue
                
                # Get sync frequency and selected folders
                frequency = config.get("frequency", "daily")
                folders = config.get("folders", [])
                
                if not folders:
                    logger.debug(f"No folders configured for user {user.email}, skipping")
                    continue
                
                # Get last_sync time from the user record
                last_sync_time = user.last_outlook_sync
                
                # Determine if it's time to sync based on frequency
                should_sync = False
                
                if last_sync_time is None:
                    # First time sync
                    should_sync = True
                else:
                    # Convert frequency to timedelta
                    interval = FREQUENCY_INTERVALS.get(frequency, FREQUENCY_INTERVALS["daily"])
                    
                    # Check if enough time has passed since last sync
                    time_since_last_sync = now - last_sync_time
                    if time_since_last_sync >= interval:
                        should_sync = True
                
                # Before dispatching, check if there's an existing lock for this user
                lock_key = f"outlook_sync:{str(user.id)}"
                redis_lock = RedisLock()
                
                # Only check if lock exists - don't try to acquire it here
                if redis_lock.is_locked(lock_key):
                    logger.info(f"Skipping sync task for user {user.email} - previous sync still running")
                    continue
                
                if should_sync:
                    logger.info(f"Dispatching sync task for user {user.email} with frequency {frequency}")
                    process_user_outlook_sync.delay(
                        str(user.id),
                        folders,
                        config.get("startDate") 
                    )
                else:
                    logger.debug(
                        f"Skipping sync for user {user.email}: last sync at {last_sync_time}, "
                        f"frequency {frequency}"
                    )
            
            except Exception as e:
                logger.error(f"Error processing sync config for user {user.email}: {str(e)}")
                continue
    
    except Exception as e:
        logger.error(f"Error in Outlook sync task dispatcher: {str(e)}")
    finally:
        if 'db' in locals():
            db.close()


# Helper function to generate the lock key from task arguments
def get_outlook_sync_lock_key(user_id: str, *args, **kwargs) -> str:
    """Generate a unique lock key for Outlook sync tasks based on user ID"""
    return f"outlook_sync:{user_id}"


@celery_app.task(name="tasks.outlook_sync.process_user_outlook_sync")
@with_lock(key_function=get_outlook_sync_lock_key, timeout=7200)  # 2 hour lock timeout
def process_user_outlook_sync(user_id: str, folders: List[str], start_date: Optional[str] = None):
    """
    Process Outlook sync for a specific user.
    This function is decorated with @with_lock to prevent concurrent executions for the same user.
    """
    logger.info(f"Processing Outlook sync for user {user_id}, folders: {folders}")
    task_id = process_user_outlook_sync.request.id
    
    try:
        # Create a database session directly since we're not in an async context
        session_local = get_db()
        db = next(session_local)
        
        # Get user
        user = db.query(UserDB).filter(UserDB.id == UUID(user_id)).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return
        
        user_email = user.email
        
        # Initialize the update flag to track if we actually processed any emails
        emails_processed = False
        
        # Process each folder
        for folder_id in folders:
            try:
                # Only process emails from the last sync date if available, otherwise use the start_date
                from_date = None
                if user.last_outlook_sync:
                    from_date = user.last_outlook_sync
                elif start_date:
                    try:
                        from_date = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    except ValueError:
                        logger.error(f"Invalid start date format: {start_date}")
                
                if not from_date:
                    # Default to one month ago if no date is specified
                    from_date = datetime.now(timezone.utc) - timedelta(days=30)
                
                logger.info(f"Syncing emails for user {user_email}, folder {folder_id} from {from_date}")
                
                # Process emails for this folder by calling it as a synchronous subtask
                # This ensures it runs in a Celery context and self.request.id is available in process_user_emails
                processed_count_result = process_user_emails.s(
                    user_id=str(user.id),
                    user_email=user_email,
                    folder_id=folder_id,
                    from_date=from_date
                ).apply() # Apply synchronously
                
                # The result of apply() is an EagerResult, get the actual return value
                processed_count = processed_count_result.get() if processed_count_result.successful() else 0

                if processed_count > 0:
                    emails_processed = True
                    logger.info(f"Processed {processed_count} emails for user {user_email}, folder {folder_id}")
            except Exception as e:
                logger.error(f"Error processing folder {folder_id} for user {user_email}: {str(e)}")
                # Continue with the next folder even if this one fails
        
        # Update last sync time only if we actually processed emails
        if emails_processed:
            # Update the last sync time to the current time
            user.last_outlook_sync = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Updated last_outlook_sync for user {user_email} to {user.last_outlook_sync}")
        else:
            logger.info(f"No emails processed for user {user_email}, not updating last_outlook_sync")
    
    except Exception as e:
        logger.error(f"Error in Outlook sync task for user {user_id}: {str(e)}")
    finally:
        if 'db' in locals():
            db.close()


def cancel_user_sync_tasks(user_id: str) -> bool:
    """
    Cancel any pending sync tasks for a user and reset their sync configuration.
    Also release any Redis locks held by the user's sync tasks.
    
    Args:
        user_id: The UUID of the user as a string
        
    Returns:
        bool: True if the operation was successful
    """
    logger.info(f"Cancelling sync tasks for user {user_id}")
    
    try:
        # Create a database session
        session_local = get_db()
        db = next(session_local)
        
        # Get the user
        user = db.query(UserDB).filter(UserDB.id == UUID(user_id)).first()
        if not user:
            logger.error(f"User {user_id} not found for cancellation")
            return False
            
        # Reset the sync configuration
        if user.outlook_sync_config:
            # Parse existing config
            config = json.loads(user.outlook_sync_config)
            # Disable sync
            config["enabled"] = False
            # Save updated config
            user.outlook_sync_config = json.dumps(config)
            db.commit()
            
        # Try to release any Redis lock for this user
        try:
            lock_key = f"outlook_sync:{user_id}"
            redis_lock = RedisLock()
            
            # We can't release a lock without the token, so we'll just 
            # check if it exists and log it - the lock will expire automatically
            if redis_lock.is_locked(lock_key):
                logger.info(f"Found active lock for user {user_id} sync - will expire naturally")
        except Exception as e:
            logger.error(f"Error checking/releasing Redis lock for user {user_id}: {str(e)}")
            
        return True
    except Exception as e:
        logger.error(f"Error cancelling sync tasks for user {user_id}: {str(e)}")
        return False
    finally:
        if 'db' in locals():
            db.close() 