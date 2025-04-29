import os
import sys
import logging
import pandas as pd
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog, Catalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError
# No specific expressions needed for this task

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RENAMED function to get last N records regardless of owner
def get_last_emails(
    full_table_name: str,
    limit: int = 100 # Default limit is 100
):
    """Connects to the Iceberg REST catalog, loads the specified table,
       sorts all records by received time,
       and prints the top N (default 100) records."""

    catalog_uri = settings.R2_CATALOG_URI
    catalog_warehouse = settings.R2_CATALOG_WAREHOUSE
    catalog_token = settings.R2_CATALOG_TOKEN
    # Consistent catalog name
    catalog_name = settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_last_records"

    logger.info(f"Target Table: {full_table_name}")
    logger.info(f"Fetching last {limit} records (sorted by received time). No owner filter.")

    # --- Initialize Catalog ---
    _catalog: Catalog | None = None
    try:
        catalog_props = {
            "name": catalog_name,
            "uri": catalog_uri,
            "warehouse": catalog_warehouse,
            "token": catalog_token,
        }
        catalog_props = {k: v for k, v in catalog_props.items() if v is not None}
        _catalog = load_catalog(**catalog_props)
        logger.info("Iceberg REST Catalog object created successfully.")
    except Exception as e:
        logger.error(f"Failed to create Iceberg REST Catalog object: {e}", exc_info=True)
        print(f"Error: Failed to create Iceberg Catalog object: {e}")
        return

    # --- Load Table and Scan ---
    try:
        logger.info(f"Loading table '{full_table_name}' via PyIceberg Catalog...")
        iceberg_table = _catalog.load_table(full_table_name)
        logger.info(f"Table '{full_table_name}' loaded successfully via PyIceberg.")

        # REMOVED filter definition block

        logger.info("Scanning relevant table data into Pandas via PyIceberg...")
        # Scan without any row filter
        relevant_cols = ['owner_email', 'sender', 'subject', 'received_datetime_utc', 'body_text', 'message_id', 'ingested_at_utc'] 
        all_data_df = iceberg_table.scan(selected_fields=tuple(relevant_cols)).to_pandas()
        total_count = len(all_data_df)
        logger.info(f"Successfully read {total_count} total rows into Pandas.")

        if total_count == 0:
            print(f"\n--- Table '{full_table_name}' is empty. ---")
            return

        # --- Print Total Count --- 
        print(f"\n--- Total Records Found in '{full_table_name}': {total_count} ---")

        # --- Sort and Print Top N Records ---
        logger.info(f"Sorting results by received_datetime_utc to get latest {limit}...")
        sort_column = 'received_datetime_utc'
        if sort_column not in all_data_df.columns:
            print(f"Error: '{sort_column}' column not found for sorting. Displaying first {limit} unsorted records.")
            results_df = all_data_df.head(limit)
        else:
            try:
                all_data_df[sort_column] = pd.to_datetime(all_data_df[sort_column], errors='coerce')
                results_df = all_data_df.sort_values(by=sort_column, ascending=False, na_position='last').head(limit)
            except Exception as sort_err:
                print(f"Warning: Could not properly sort by {sort_column}: {sort_err}. Displaying first {limit} unsorted records.")
                results_df = all_data_df.head(limit)

        # Determine actual number of records displayed
        display_count = len(results_df)
        print(f"\n--- Displaying Latest {display_count} Records (Sorted by Received Time) --- ")
        pd.set_option('display.max_rows', limit + 10) # Adjust display rows based on limit
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 2000)
        pd.set_option('display.max_colwidth', 100) 
        # Display relevant columns, ensure they exist in results_df
        existing_display_cols = [col for col in relevant_cols if col in results_df.columns]
        print(results_df[existing_display_cols])
        print("--------------------------------------------------------")

    except (NoSuchTableError, NoSuchNamespaceError):
        logger.error(f"Error: Table or Namespace not found: {full_table_name}")
        print(f"Error: Iceberg table '{full_table_name}' or its namespace not found.")
    except RuntimeError as e:
        logger.error(f"Catalog initialization or loading failed: {e}")
        print(f"Error: Could not initialize/load Iceberg catalog/table.")
    except KeyError as e:
        logger.error(f"DataFrame column error: {e}", exc_info=True)
        print(f"Error: A required column ({e}) was not found or caused an error.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
    finally:
        logger.info("Script execution finished within get_last_emails.") # Updated function name


if __name__ == "__main__":
    print("--- Script starting ---")
    try:
        # Add sys.path modification right before import
        project_root_main = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if project_root_main not in sys.path:
            sys.path.insert(0, project_root_main)
            print(f"Added project root to sys.path: {project_root_main}")
        else:
            print(f"Project root already in sys.path: {project_root_main}")

        print("Attempting to import settings...")
        # Ensure settings are imported before use
        from backend.app.config import settings
        print("Settings imported successfully.")

        dotenv_path_main = os.path.join(project_root_main, '.env')
        if os.path.exists(dotenv_path_main):
            load_dotenv(dotenv_path=dotenv_path_main)
            logger.info(f"Loaded .env file from: {dotenv_path_main}")
        else:
            logger.warning(f".env file not found at: {dotenv_path_main}")

        # Configuration that depends on settings
        TABLE_NAMESPACE = settings.ICEBERG_DEFAULT_NAMESPACE
        TABLE_NAME = settings.ICEBERG_EMAIL_FACTS_TABLE
        FULL_TABLE_NAME = f"{TABLE_NAMESPACE}.{TABLE_NAME}"

        # --- Define Query Parameters ---
        # OWNER_EMAIL_TO_QUERY = "jiaqi.lin@int.beyondsoft.com" # Removed owner filter
        LIMIT = 100 # Set limit to 100

        print(f"\nRunning Iceberg Query for Last {LIMIT} Records in '{FULL_TABLE_NAME}'...")
        # Call the updated function
        get_last_emails(
            full_table_name=FULL_TABLE_NAME,
            limit=LIMIT
        )
        print("\nQuery execution complete.")
    except ImportError as e:
        print(f"ERROR: Failed to import settings: {e}")
        import traceback
        traceback.print_exc()
    except Exception as main_err:
        print(f"An error occurred in main execution: {main_err}")
        import traceback
        traceback.print_exc() 