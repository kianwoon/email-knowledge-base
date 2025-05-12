import os
import uuid
import json
import pathlib
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

import duckdb
from pyiceberg.catalog import load_catalog, Catalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.expressions import GreaterThanOrEqual, LessThanOrEqual, And, StartsWith, EqualTo

from app.config import settings
from openai import AsyncOpenAI

# Set up logger for this module
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

# --- START: Global DuckDB Connection Pool ---
DUCKDB_CONN: Optional[duckdb.DuckDBPyConnection] = None

def get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    """Returns a reusable DuckDB connection with httpfs and caching configured."""
    global DUCKDB_CONN
    if DUCKDB_CONN is None:
        DUCKDB_CONN = duckdb.connect(database=':memory:')
        
        # Create and configure cache directories with absolute paths
        import os
        import pathlib
        
        # Define paths for cache directories
        home_dir = os.path.expanduser("~/.duckdb_cache")
        httpfs_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "duckdb_httpfs_cache")
        
        # Create directories if they don't exist
        pathlib.Path(home_dir).mkdir(parents=True, exist_ok=True)
        pathlib.Path(httpfs_cache_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Using DuckDB home directory: {home_dir}")
        logger.info(f"Using HTTP/FS cache directory: {httpfs_cache_dir}")
        
        # Configure home directory first
        DUCKDB_CONN.execute(f"SET home_directory='{home_dir}';")
        
        # Install and load httpfs (required for S3/remote data access)
        DUCKDB_CONN.execute("INSTALL httpfs; LOAD httpfs;")
        
        # Try to enable object-store caching using the cache_httpfs extension
        try:
            # 1. Install & load the cache_httpfs community extension
            logger.info("Installing and loading cache_httpfs extension...")
            DUCKDB_CONN.execute("INSTALL cache_httpfs FROM community;")
            DUCKDB_CONN.execute("LOAD cache_httpfs;")
            
            # 2. Configure caching parameters
            logger.info("Configuring cache_httpfs settings...")
            DUCKDB_CONN.execute("SET cache_httpfs_type = 'on_disk';")
            DUCKDB_CONN.execute(f"SET cache_httpfs_cache_directory = '{httpfs_cache_dir}';")
            DUCKDB_CONN.execute("SET cache_httpfs_cache_block_size = 1048576;")  # 1 MiB blocks
            DUCKDB_CONN.execute("SET cache_httpfs_in_mem_cache_block_timeout_millisec = 600000;")  # 10 min
            
            logger.info("Successfully enabled object-store caching for DuckDB via cache_httpfs extension")
        except Exception as e:
            # If the caching extension isn't available or fails to install, log and continue without it
            logger.warning(f"DuckDB object-store caching could not be enabled: {e}")
            logger.info("Continuing without object-store caching")
    
    return DUCKDB_CONN
# --- END: Global DuckDB Connection Pool ---

# --- START: Global Catalog Variable (Initialize lazily) ---
# Use a global variable to hold the catalog instance to avoid reinitialization on every call.
# Ensure thread-safety if your application uses threads extensively for requests.
_iceberg_catalog: Optional[Catalog] = None
_catalog_lock = asyncio.Lock() # Use async lock for async context

async def get_iceberg_catalog() -> Catalog:
    """Initializes and returns the Iceberg catalog instance, ensuring it's done only once."""
    global _iceberg_catalog
    async with _catalog_lock:
        if _iceberg_catalog is None:
            logger.info("Initializing Iceberg REST Catalog for DuckDB integration...")
            try:
                catalog_props = {
                    # Use a distinct name
                    "name": settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_duckdb_llm",
                    "uri": settings.R2_CATALOG_URI,
                    "warehouse": settings.R2_CATALOG_WAREHOUSE,
                    "token": settings.R2_CATALOG_TOKEN,
                    # Add S3 specific creds if needed by PyArrowFileIO used under the hood
                    # These might come from settings or environment variables
                    "s3.endpoint": settings.R2_ENDPOINT_URL, 
                    "s3.access-key-id": settings.R2_ACCESS_KEY_ID,
                    "s3.secret-access-key": settings.R2_SECRET_ACCESS_KEY
                }
                # Remove None values from props before passing to load_catalog
                catalog_props = {k: v for k, v in catalog_props.items() if v is not None}
                _iceberg_catalog = load_catalog(**catalog_props)
                logger.info("Iceberg Catalog initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Iceberg Catalog: {e}", exc_info=True)
                # Raise or handle appropriately - maybe return None or raise specific exception
                raise RuntimeError(f"Could not initialize Iceberg Catalog: {e}") from e
    return _iceberg_catalog
# --- END: Global Catalog Variable ---

# --- START: DuckDB Query Helper ---
async def query_iceberg_emails_duckdb(
    user_email: str,
    sender_filter: Optional[str] = None,
    subject_filter: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    search_terms: Optional[List[str]] = None, # Renamed from keywords for general search
    limit: int = 5,
    user_client: AsyncOpenAI = None, # Client configured for the correct provider
    token: Optional[Any] = None, # ADDED: Optional Token parameter
    provider: str = "openai" # ADDED: Provider name ('openai', 'deepseek', etc.)
) -> List[Dict[str, Any]]:
    """Queries the email_facts Iceberg table using DuckDB based on structured filters, applying token scope (columns) if provided."""
    results = []
    
    if not sender_filter and not subject_filter and not start_date and not end_date and not search_terms:
        logger.warning("DuckDB Query: No specific filters (sender, subject, date, terms) provided. Returning empty results.")
        return results
    if not user_client:
        logger.error("DuckDB Query: User-specific OpenAI client (user_client) was not provided.")
        return results

    try:
        catalog = await get_iceberg_catalog()
        if not catalog:
            return results

        full_table_name = f"{settings.ICEBERG_DEFAULT_NAMESPACE}.{settings.ICEBERG_EMAIL_FACTS_TABLE}"
        try:
            iceberg_table = catalog.load_table(full_table_name)
        except NoSuchTableError:
            logger.error(f"Iceberg table {full_table_name} not found.")
            return results

        # Get reusable DuckDB connection
        con = get_duckdb_conn()
        view_name = f'email_facts_view_{uuid.uuid4().hex[:8]}'  # Use unique view name to avoid conflicts
        
        # Create PyIceberg expressions for predicate push-down
        
        # Build push-down expressions
        exprs = []
        # Add owner email filter
        exprs.append(EqualTo("owner_email", user_email))
        
        # Add date filters
        if start_date:
            exprs.append(GreaterThanOrEqual("received_datetime_utc", start_date))
            logger.info(f"Pushing down start_date filter: {start_date.isoformat()}")
        if end_date:
            exprs.append(LessThanOrEqual("received_datetime_utc", end_date))
            logger.info(f"Pushing down end_date filter: {end_date.isoformat()}")
            
        # Add sender filter if plausible
        is_plausible_sender_filter = False
        if sender_filter:
            # Simple check: contains @ or multiple words, or is a reasonable length name
            if '@' in sender_filter or len(sender_filter.split()) > 1 or (len(sender_filter) >= 2 and sender_filter.isalpha()): 
                is_plausible_sender_filter = True
                # Only push-down exact match filters, do LIKE filters in SQL
                if '@' in sender_filter:
                    exprs.append(StartsWith("sender", sender_filter))
                    logger.debug(f"Pushing down sender filter: {sender_filter}")
            else:
                logger.warning(f"Ignoring likely implausible sender filter: '{sender_filter}'")
        
        # Determine select columns based on token
        select_columns = None  # Default to selecting all columns
        if token and hasattr(token, 'allow_columns') and token.allow_columns:
            select_columns = token.allow_columns
            logger.info(f"Applying column projection based on token {token.id}")
            
        # Create scan with filters and projection
        scan = iceberg_table.scan()
        
        # Apply filter expressions if we have any
        if exprs:
            try:
                scan = scan.filter(And(*exprs))
                logger.debug(f"Applied {len(exprs)} predicate pushdown filters to Iceberg scan")
            except Exception as filter_err:
                logger.warning(f"Failed to apply some predicate filters: {filter_err}. Falling back to basic scan.")
                # Start with a fresh scan and just apply the owner email filter which is the most important
                scan = iceberg_table.scan()
                try:
                    scan = scan.filter(EqualTo("owner_email", user_email))
                    logger.debug("Applied fallback filter for owner_email only")
                except Exception as basic_filter_err:
                    logger.error(f"Even basic filtering failed: {basic_filter_err}")
            
        # Apply column projection if specified
        if select_columns:
            scan = scan.select(*select_columns)
            
        # Execute the scan to DuckDB
        scan.to_duckdb(table_name=view_name, connection=con)
        
        # Continue with SQL filtering for more complex conditions that can't be pushed down
        # --- REVISED: Build WHERE clause based on provided filters ---
        # We've already filtered owner_email, start_date, and end_date in the scan
        final_where_clauses = []
        final_query_params = []

        # Clauses for specific field attribute filters (sender, subject)
        attribute_filter_clauses = []
        attribute_filter_params = []
        
        # Only add SQL sender filter if we couldn't push it down completely
        if is_plausible_sender_filter and not ('@' in sender_filter):
            # MODIFIED: Search in both sender (email) and sender_name (display name)
            attribute_filter_clauses.append("(sender LIKE ? OR sender_name LIKE ?)")
            attribute_filter_params.append(f"%{sender_filter}%")
            attribute_filter_params.append(f"%{sender_filter}%") # Add param again for sender_name
            logger.debug(f"Applying attribute sender filter (on sender/sender_name): {sender_filter}")
        
        if subject_filter:
            attribute_filter_clauses.append("subject LIKE ?")
            attribute_filter_params.append(f"%{subject_filter}%")
            logger.debug(f"Applying attribute subject filter: {subject_filter}")
        
        attribute_filters_sql_part = ""
        if attribute_filter_clauses:
            attribute_filters_sql_part = " AND ".join(attribute_filter_clauses)
            # Wrap in parentheses if there are attribute filters
            attribute_filters_sql_part = f"({attribute_filters_sql_part})"
            final_where_clauses.append(attribute_filters_sql_part)
            final_query_params.extend(attribute_filter_params)

        # Clause for general keyword search terms
        keyword_search_sql_part = ""
        keyword_search_params = []
        if search_terms:
            keyword_filter_individual_parts = []
            for term in search_terms:
                safe_term = term.replace('%', '\%').replace('_', '\_')
                # Each term searches across multiple fields OR'd together
                term_specific_search = f"(subject LIKE ? OR body_text LIKE ? OR sender LIKE ? OR sender_name LIKE ? OR generated_tags LIKE ? OR quoted_raw_text LIKE ?)"
                keyword_filter_individual_parts.append(term_specific_search)
                keyword_search_params.extend([f'%{safe_term}%'] * 6)
            
            if keyword_filter_individual_parts:
                # If multiple search terms, they are typically OR'd (any term can match)
                keyword_search_sql_part = " OR ".join(keyword_filter_individual_parts)
                # Wrap keyword search in parentheses if it exists
                keyword_search_sql_part = f"({keyword_search_sql_part})"
                final_where_clauses.append(keyword_search_sql_part)
                final_query_params.extend(keyword_search_params)
                logger.debug(f"Applying keyword search terms: {search_terms}")

        # --- END REVISED: WHERE clause ---

        # Construct the full SQL query with dynamic WHERE clauses
        effective_limit = token.row_limit if token and hasattr(token, 'row_limit') and token.row_limit else limit

        # Only add WHERE if we have conditions
        where_sql_final = ""
        if final_where_clauses:
            where_sql_final = f"WHERE {' AND '.join(final_where_clauses)}"

        sql_query = f"""
        SELECT * 
        FROM {view_name}
        {where_sql_final}
        ORDER BY received_datetime_utc DESC
        LIMIT ?;
        """
        final_query_params.append(effective_limit)

        # ADDED LOGGING FOR THE SQL QUERY AND PARAMETERS
        logger.info(f"[DuckDB Query] Final SQL to execute: {sql_query}")
        logger.info(f"[DuckDB Query] Parameters: {final_query_params}")

        # Execute query and fetch results
        arrow_table = con.execute(sql_query, final_query_params).fetch_arrow_table()
        results = arrow_table.to_pylist()
        logger.info(f"DuckDB query returned {len(results)} email results.")
        
        # Drop the temporary view to avoid cluttering the connection
        con.execute(f"DROP VIEW IF EXISTS {view_name}")

    except Exception as e:
        logger.error(f"Error querying DuckDB for emails: {e}", exc_info=True)
        results = [] # Ensure empty list on error
    # Don't close the connection since we're reusing it

    return results
# --- END: DuckDB Query Helper --- 