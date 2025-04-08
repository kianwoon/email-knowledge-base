import sqlite3
import logging
import os
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)

# Database file path (adjust as needed, e.g., use settings)
# Place it in the backend root for simplicity or configure via settings
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "job_mapping.db")
TABLE_NAME = "job_mappings"
LOCK_TIMEOUT_SECONDS = 15 # How long to wait for a lock

@contextmanager
def get_db_connection():
    """Provides a database connection context manager."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH, timeout=LOCK_TIMEOUT_SECONDS, check_same_thread=False)
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        logger.debug(f"SQLite connection opened to {DATABASE_PATH}")
        yield conn
    except sqlite3.Error as e:
        logger.error(f"SQLite connection error to {DATABASE_PATH}: {e}", exc_info=True)
        raise # Re-raise the exception
    finally:
        if conn:
            conn.close()
            logger.debug(f"SQLite connection closed for {DATABASE_PATH}")

def initialize_db():
    """Initializes the database and creates the mapping table if it doesn't exist."""
    logger.info(f"Initializing SQLite job mapping database at: {DATABASE_PATH}")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    external_job_id TEXT PRIMARY KEY,
                    internal_job_id TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Optional: Create an index for faster lookups if needed later
            # cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_internal_job_id ON {TABLE_NAME} (internal_job_id);")
            conn.commit()
        logger.info(f"SQLite table '{TABLE_NAME}' ensured in {DATABASE_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize SQLite database or table '{TABLE_NAME}': {e}", exc_info=True)
        # Depending on requirements, you might want to exit or raise a critical error here

def insert_mapping(external_job_id: str, internal_job_id: str, owner: str):
    """Inserts or replaces a job ID mapping."""
    logger.debug(f"Attempting to insert mapping: External={external_job_id}, Internal={internal_job_id}, Owner={owner}")
    sql = f"""
        INSERT OR REPLACE INTO {TABLE_NAME} (external_job_id, internal_job_id, owner)
        VALUES (?, ?, ?);
    """
    retries = 3
    delay = 0.1
    for attempt in range(retries):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (external_job_id, internal_job_id, owner))
                conn.commit()
            logger.info(f"Successfully inserted/replaced mapping for External Job ID: {external_job_id}")
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                logger.warning(f"Database locked on attempt {attempt + 1}. Retrying insert for {external_job_id} in {delay:.2f}s...")
                time.sleep(delay)
                delay *= 2 # Exponential backoff
            else:
                logger.error(f"SQLite error inserting mapping for external_job_id {external_job_id}: {e}", exc_info=True)
                return False
        except sqlite3.Error as e:
            logger.error(f"Unexpected SQLite error inserting mapping for external_job_id {external_job_id}: {e}", exc_info=True)
            return False
    return False # Failed after retries

def get_mapping(external_job_id: str) -> tuple[str | None, str | None]:
    """Retrieves the internal job ID and owner for a given external job ID."""
    logger.debug(f"Attempting to retrieve mapping for External Job ID: {external_job_id}")
    sql = f"SELECT internal_job_id, owner FROM {TABLE_NAME} WHERE external_job_id = ?;"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (external_job_id,))
            result = cursor.fetchone()
            if result:
                logger.info(f"Found mapping for External Job ID {external_job_id}: Internal={result[0]}, Owner={result[1]}")
                return result[0], result[1] # (internal_job_id, owner)
            else:
                logger.warning(f"No mapping found for External Job ID: {external_job_id}")
                return None, None
    except sqlite3.Error as e:
        logger.error(f"SQLite error retrieving mapping for external_job_id {external_job_id}: {e}", exc_info=True)
        return None, None

# Optional: Add a function to clean up old mappings if needed
# def cleanup_old_mappings(days_old: int): ... 