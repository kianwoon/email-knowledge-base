# backend/app/crud/crud_catalog.py

import duckdb
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
import pandas as pd
from pyiceberg.catalog import load_catalog, Catalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError
# Expressions not needed for this approach
from app.models.token import Token
from app.config import settings
import logging
import traceback
from fastapi import HTTPException
import asyncio
import threading # Import threading for lock

logger = logging.getLogger(__name__)

# --- Default settings (Keep for column selection logic) ---
DEFAULT_COLUMNS = ["id", "subject", "sender_name", "created_at", "content_preview"] 
DEFAULT_SEARCH_COLUMNS = ["subject", "content_preview", "sender_name", "body_text"] # Columns for SQL LIKE
ATTACHMENT_COLUMNS = ["attachment_filenames", "attachment_count", "attachment_details"]
# Default table name for audit logging purposes
DEFAULT_CATALOG_TABLE = "email_facts"
# --- End Defaults ---

# --- Catalog Getter (Simplified Synchronous Version) ---
_iceberg_catalog_instance: Optional[Catalog] = None
_catalog_lock = threading.Lock() # Use a standard threading lock

def get_iceberg_catalog() -> Catalog:
    """Initializes and returns a cached Iceberg catalog instance (synchronous)."""
    global _iceberg_catalog_instance
    # Quick check without lock for performance
    if _iceberg_catalog_instance is not None:
        return _iceberg_catalog_instance

    # Acquire lock only if instance is None
    with _catalog_lock:
        # Double-check after acquiring lock
        if _iceberg_catalog_instance is None:
            logger.info("Initializing Iceberg REST Catalog (synchronous)...")
            try:
                catalog_props = {
                    "name": settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_crud",
                    "uri": settings.R2_CATALOG_URI,
                    "token": settings.R2_CATALOG_TOKEN,
                    "warehouse": settings.R2_CATALOG_WAREHOUSE,
                    "endpoint": settings.R2_ENDPOINT_URL,
                }
                catalog_props = {k: v for k, v in catalog_props.items() if v is not None}
                if not catalog_props.get("token"):
                     logger.warning("R2_CATALOG_TOKEN not set, attempting connection without token.")
                     
                _iceberg_catalog_instance = load_catalog(**catalog_props)
                logger.info("Iceberg Catalog initialized successfully (synchronous).")
            except Exception as e:
                logger.error(f"Failed to initialize Iceberg Catalog: {e}", exc_info=True)
                _iceberg_catalog_instance = None # Ensure it's None on failure
                raise ConnectionError(f"Could not initialize Iceberg Catalog: {e}") from e
                
    # If instance is still None after lock release (should not happen normally)
    if _iceberg_catalog_instance is None:
         raise ConnectionError("Failed to obtain Iceberg catalog instance.")

    return _iceberg_catalog_instance


# --- Rewritten search_catalog_items using DuckDB view pattern --- 
def search_catalog_items(
    query: str,
    token: Token,
    effective_limit: int,
    filters: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Searches the Iceberg email_facts table using PyIceberg's native scan API
    and executes filtering directly on the Iceberg table, respecting token permissions.
    This approach doesn't use DuckDB SQL and instead follows the REST catalog API pattern.
    """
    try:
        # 1. Get Iceberg Catalog
        catalog = get_iceberg_catalog()

        # 2. Define Target Table
        namespace = settings.ICEBERG_DEFAULT_NAMESPACE
        table_name = settings.ICEBERG_EMAIL_FACTS_TABLE
        full_table_name = f"{namespace}.{table_name}"
        
        # 3. Load Iceberg Table
        logger.info(f"Attempting to load Iceberg table: {full_table_name}")
        try:
            iceberg_table = catalog.load_table(full_table_name)
            logger.info(f"Successfully loaded Iceberg table: {full_table_name}")
        except (NoSuchTableError, NoSuchNamespaceError) as table_not_found:
            logger.error(f"Iceberg table or namespace not found: {full_table_name}. Error: {table_not_found}")
            raise HTTPException(status_code=404, detail=f"Data table '{full_table_name}' not found.") from table_not_found

        # 4. Determine columns to select based on token
        table_schema = iceberg_table.schema()
        all_column_names = [field.name for field in table_schema.fields]
        
        # Start with selecting all columns
        select_columns = all_column_names[:]
        
        # Apply token column restrictions if specified
        if token.allow_columns and '*' not in token.allow_columns:
            allowed_columns = token.allow_columns
            # Filter by what's actually in the table schema
            select_columns = [col for col in allowed_columns if col in all_column_names]
            if not select_columns:
                logger.warning(f"Token {token.id} requested only non-existent columns. Defaulting to all columns.")
                select_columns = all_column_names[:]
        
        logger.debug(f"Selected columns for query: {select_columns}")
        
        # 5. Build scan with filters
        scan = iceberg_table.scan()
        
        # Add column projection
        if select_columns and select_columns != all_column_names:
            scan = scan.select(*select_columns)
        
        # --- ADDED: Filter by token owner --- 
        if "owner_email" in all_column_names:
            if token.owner_email:
                # Escape single quotes in the owner_email for the filter expression
                escaped_owner_email = token.owner_email.replace("'", "''")
                logger.info(f"Applying filter for owner_email: {escaped_owner_email}")
                scan = scan.filter(f"owner_email = '{escaped_owner_email}'")
            else:
                logger.warning("Token has no owner_email, cannot filter by owner. This might be a security risk!")
        else:
            logger.warning("'owner_email' column not found in table schema, cannot filter by owner.")
        # --- END ADDED ---
        
        # Apply text search filter
        if query:
            query_lower = query.lower()
            # PyIceberg only supports LIKE with % at the end, not beginning or both
            # So we'll do post-filtering in Python instead
            logger.debug(f"Will perform text search filter for '{query_lower}' after retrieving results")
            # Note: Not adding filter to scan - will filter after scan.to_arrow()
        
        # Apply specific field filters
        if filters.get("sender"):
            sender = filters["sender"]
            # Escape single quotes in the sender value for use in filter expression
            escaped_sender = sender.replace("'", "''")
            
            # Build filter expressions
            sender_filters = []
            if "sender_name" in all_column_names:
                sender_filters.append(f"sender_name = '{escaped_sender}'")
            if "sender" in all_column_names:
                sender_filters.append(f"sender = '{escaped_sender}'")
            
            if sender_filters:
                logger.debug(f"Applying sender filters: {' OR '.join(sender_filters)}")
                scan = scan.filter(" OR ".join(sender_filters))
        
        # Date range filters
        if filters.get("date_from") and "created_at" in all_column_names:
            date_from = filters["date_from"]
            scan = scan.filter(f"created_at >= '{date_from}'")
        
        if filters.get("date_to") and "created_at" in all_column_names:
            date_to = filters["date_to"]
            scan = scan.filter(f"created_at <= '{date_to}'")

        # 6. Execute scan and get results
        # Convert to Arrow table and then to Python list
        arrow_table = scan.to_arrow()
        
        # Convert to pandas first for easier manipulation if needed
        import pandas as pd
        df = arrow_table.to_pandas()
        
        # Apply text search as post-filter in pandas (case-insensitive)
        if query and len(query.strip()) > 0:
            query_lower = query.lower()
            # Create a combined filter across all text columns
            mask = pd.Series(False, index=df.index)
            search_columns = ["subject", "body_text", "sender", "sender_name", "content_preview"]
            
            for col in search_columns:
                if col in df.columns:
                    # Convert column to string and handle NaN/None values
                    string_col = df[col].astype(str).str.lower()
                    mask = mask | string_col.str.contains(query_lower, na=False)
            
            # Apply the filter mask
            before_count = len(df)
            df = df[mask]
            after_count = len(df)
            logger.debug(f"Text search filter reduced results from {before_count} to {after_count}")
        
        # Apply sorting (if needed) and limit
        if "created_at" in df.columns:
            df = df.sort_values("created_at", ascending=False)
        
        # Apply limit
        if effective_limit > 0:
            df = df.head(effective_limit)
        
        # Convert to dict records
        results = df.to_dict('records')
        logger.info(f"Iceberg scan found {len(results)} results (limit: {effective_limit}).")
        
        return results

    except ConnectionError as conn_err:
        logger.error(f"Failed to connect to Iceberg catalog: {conn_err}", exc_info=True)
        raise HTTPException(status_code=503, detail="Could not connect to data catalog.") from conn_err
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error executing catalog search using PyIceberg scan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error during catalog search: {e}") from e 