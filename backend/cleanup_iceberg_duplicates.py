# backend/cleanup_iceberg_duplicates.py
import os
import sys
import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.io.pyarrow import schema_to_pyarrow
import logging
import traceback

# --- Configuration (Adapt from your settings) ---
# Add the project root to the Python path to import settings
# Since this script is in /backend, go up one level to the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    # Assuming your config module is accessible as backend.app.config
    from backend.app.config import settings
except ImportError:
    print("Error: Could not import settings from backend.app.config.")
    print(f"Attempted to add project root: {project_root} to sys.path")
    print(f"Current sys.path: {sys.path}")
    print("Ensure script is run from the workspace root or adjust path logic.")
    exit(1)
except Exception as import_err:
    print(f"An unexpected error occurred during settings import: {import_err}")
    traceback.print_exc()
    exit(1)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TABLE_NAMESPACE = settings.ICEBERG_DEFAULT_NAMESPACE
TABLE_NAME = settings.ICEBERG_EMAIL_FACTS_TABLE
FULL_TABLE_NAME = f"{TABLE_NAMESPACE}.{TABLE_NAME}"
UNIQUE_COLUMN = "message_id"
# Optional: Define a column to sort by to keep the 'latest' duplicate
# SORT_COLUMN = "received_datetime" # Example, adjust if you have a timestamp field name
# KEEP_RULE = "last" # Keep the 'last' after sorting, 'first' otherwise

# --- Catalog Initialization ---
try:
    logger.info("Initializing Iceberg REST Catalog...")
    catalog_props = {
        "name": "r2_catalog_cleanup", # Use a distinct name for the catalog instance
        "uri": settings.R2_CATALOG_URI,
        "warehouse": settings.R2_CATALOG_WAREHOUSE,
        "token": settings.R2_CATALOG_TOKEN,
        "pyiceberg.io.pyarrow.downcast-ns-timestamp-to-us-on-write": True
    }
    catalog = RestCatalog(**catalog_props)
    logger.info(f"Iceberg REST Catalog initialized successfully. URI: {settings.R2_CATALOG_URI}, Warehouse: {settings.R2_CATALOG_WAREHOUSE}")
except Exception as e:
    logger.error(f"Failed to initialize Iceberg Catalog: {e}", exc_info=True)
    exit(1)

# --- Main Cleanup Logic ---
try:
    logger.info(f"Attempting to load table: {FULL_TABLE_NAME}")
    try:
        table = catalog.load_table(FULL_TABLE_NAME)
        logger.info(f"Table '{FULL_TABLE_NAME}' loaded successfully.")
    except Exception as load_err:
         logger.error(f"Failed to load table '{FULL_TABLE_NAME}': {load_err}", exc_info=True)
         exit(1)

    # Ensure identifier fields are set for context, though not strictly needed for this script's logic
    schema = table.schema()
    logger.info(f"Table schema identifier fields: {schema.identifier_field_ids}")
    if not schema.identifier_field_ids:
        logger.warning(f"Table '{FULL_TABLE_NAME}' does not have identifier fields set in its schema. This cleanup script will proceed, but upserts might fail later if this isn't addressed.")

    arrow_schema = schema_to_pyarrow(schema) # Get target schema
    logger.info(f"Target Arrow schema: {arrow_schema}")

    logger.info("Scanning entire table into Pandas DataFrame (this may take time for large tables)...")
    # Scan all data. Be mindful of memory for very large tables.
    # Consider using .to_arrow_batch_reader() and processing in chunks
    # for larger-than-memory datasets.
    try:
        df = table.scan().to_pandas()
        logger.info(f"Loaded {len(df)} rows from the table.")
    except Exception as scan_err:
        logger.error(f"Failed to scan table data into Pandas: {scan_err}", exc_info=True)
        exit(1)


    if df.empty:
        logger.info("Table is empty, no cleanup needed.")
        exit(0)

    if UNIQUE_COLUMN not in df.columns:
        logger.error(f"Unique column '{UNIQUE_COLUMN}' not found in DataFrame columns: {df.columns.tolist()}. Please verify the column name.")
        exit(1)

    # --- Deduplication ---
    original_count = len(df)
    logger.info(f"Performing deduplication based on '{UNIQUE_COLUMN}'...")

    # Optional: Sort before dropping duplicates if you want to keep the latest/earliest
    # Example: Assuming 'created_at_ms' is a timestamp column
    # SORT_COLUMN = "created_at_ms"
    # if SORT_COLUMN in df.columns:
    #    logger.info(f"Sorting by '{SORT_COLUMN}' (descending) before deduplicating to keep the latest record.")
    #    # Ensure the sort column is numeric or datetime for correct sorting
    #    try:
    #        df[SORT_COLUMN] = pd.to_datetime(df[SORT_COLUMN], errors='coerce', unit='ms') # Example conversion
    #        df = df.sort_values(by=SORT_COLUMN, ascending=False, na_position='last')
    #        KEEP_RULE = "first" # Keep the first row after sorting descending (which is the latest)
    #    except Exception as sort_err:
    #        logger.warning(f"Could not sort by '{SORT_COLUMN}': {sort_err}. Proceeding without sorting.")
    #        KEEP_RULE = "first" # Default keep rule
    # else:
    #    logger.info(f"Sort column '{SORT_COLUMN}' not found. Proceeding without sorting.")
    KEEP_RULE = "first" # Default: keep the first encountered duplicate

    # Drop duplicates
    df_deduplicated = df.drop_duplicates(subset=[UNIQUE_COLUMN], keep=KEEP_RULE)
    deduplicated_count = len(df_deduplicated)
    removed_count = original_count - deduplicated_count
    logger.info(f"Deduplication complete. Original rows: {original_count}, Deduplicated rows: {deduplicated_count}, Removed: {removed_count}")

    if removed_count == 0:
        logger.info("No duplicate rows found based on the criteria. Overwrite not necessary.")
        exit(0)

    # --- Overwrite Table ---
    logger.info("Converting cleaned data back to Arrow Table...")
    # Ensure the DataFrame matches the target Arrow schema before converting
    try:
        # Convert with schema enforcement first
        arrow_table_cleaned = pa.Table.from_pandas(df_deduplicated, schema=arrow_schema, preserve_index=False)
    except (TypeError, pa.lib.ArrowInvalid) as conversion_error:
         logger.warning(f"Strict Arrow conversion failed ({conversion_error}). This might happen if Pandas changed types. Attempting conversion without strict schema first.")
         # Fallback to schema inference by Arrow, overwrite might still fail if incompatible
         try:
            arrow_table_cleaned = pa.Table.from_pandas(df_deduplicated, preserve_index=False)
            logger.info(f"Schema inferred by Arrow: {arrow_table_cleaned.schema}")
            # Optional: Add explicit casting here based on expected types if needed
         except Exception as fallback_conv_err:
             logger.error(f"Fallback Arrow conversion also failed: {fallback_conv_err}", exc_info=True)
             exit(1)


    logger.info(f"Attempting to overwrite Iceberg table '{FULL_TABLE_NAME}' with {deduplicated_count} cleaned rows...")
    # Overwrite the entire table with the deduplicated data
    try:
        table.overwrite(arrow_table_cleaned)
        logger.info("Table overwrite successful.")
    except Exception as overwrite_err:
        logger.error(f"Failed to overwrite table '{FULL_TABLE_NAME}': {overwrite_err}", exc_info=True)
        # Note: A failed overwrite might leave the table in an inconsistent state if not transactional.
        exit(1)

except Exception as e:
    logger.error(f"An unexpected error occurred during the cleanup process: {e}", exc_info=True)
    exit(1)

logger.info("Cleanup process finished.") 