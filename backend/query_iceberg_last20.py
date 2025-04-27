import os
import sys
import logging
import pandas as pd
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog, Catalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def print_table_summary(full_table_name: str, limit: int = 20):
    """Connects to the Iceberg REST catalog, loads the specified table,
       prints the total record count, and the last N records (sorted by ingestion time)."""
    
    catalog_uri = settings.R2_CATALOG_URI
    catalog_warehouse = settings.R2_CATALOG_WAREHOUSE
    catalog_token = settings.R2_CATALOG_TOKEN
    catalog_name = settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_summary"

    logger.info(f"Target Table: {full_table_name}")

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

    # --- Load Table and Read Data via PyIceberg Scan --- 
    try:
        logger.info(f"Loading table '{full_table_name}' via PyIceberg Catalog...")
        iceberg_table = _catalog.load_table(full_table_name)
        logger.info(f"Table '{full_table_name}' loaded successfully via PyIceberg.")

        logger.info("Scanning ALL table data into Pandas via PyIceberg (may take time)...")
        # Scan the entire table into Pandas
        all_data_df = iceberg_table.scan().to_pandas()
        total_count = len(all_data_df)
        logger.info(f"Successfully read {total_count} total rows into Pandas.")

        # --- Print Total Count --- 
        print(f"\n--- Total Records Found in '{full_table_name}': {total_count} ---")
        
        if total_count == 0:
            print("Table is empty, nothing more to display.")
            return

        # --- Sort and Print Last N Records --- 
        logger.info(f"Sorting results by ingested_at_utc to get last {limit} records...")
        if 'ingested_at_utc' not in all_data_df.columns:
            print(f"Error: 'ingested_at_utc' column not found for sorting. Displaying first {limit} unsorted records.")
            results_df = all_data_df.head(limit)
        else:
            try:
                all_data_df['ingested_at_utc'] = pd.to_datetime(all_data_df['ingested_at_utc'], errors='coerce')
                results_df = all_data_df.sort_values(by='ingested_at_utc', ascending=False, na_position='last').head(limit)
            except Exception as sort_err:
                print(f"Warning: Could not properly sort by ingested_at_utc: {sort_err}. Displaying first {limit} unsorted records.")
                results_df = all_data_df.head(limit)

        print(f"\n--- Last {limit} Records (Sorted by Ingestion Time) --- ")
        pd.set_option('display.max_rows', 40)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 2000)
        pd.set_option('display.max_colwidth', 100)
        print(results_df)
        print("--------------------------------------------------------")

    except (NoSuchTableError, NoSuchNamespaceError):
        logger.error(f"Error: Table or Namespace not found: {full_table_name}")
        print(f"Error: Iceberg table '{full_table_name}' or its namespace not found.")
    except RuntimeError as e:
        logger.error(f"Catalog initialization or loading failed: {e}")
        print(f"Error: Could not initialize/load Iceberg catalog/table.")
    except KeyError as e:
        logger.error(f"DataFrame column error: {e}", exc_info=True)
        print(f"Error: A required column ({e}) was not found in the DataFrame.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
    finally:
        logger.info("Script execution finished within print_table_summary.")


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
        from backend.app.config import settings
        print("Settings imported successfully.")

        dotenv_path_main = os.path.join(project_root_main, '.env')
        if os.path.exists(dotenv_path_main):
            load_dotenv(dotenv_path=dotenv_path_main)
            logger.info(f"Loaded .env file from: {dotenv_path_main}")
        else:
            logger.warning(f".env file not found at: {dotenv_path_main}")

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

        # Configuration that depends on settings
        TABLE_NAMESPACE = settings.ICEBERG_DEFAULT_NAMESPACE
        TABLE_NAME = settings.ICEBERG_EMAIL_FACTS_TABLE
        FULL_TABLE_NAME = f"{TABLE_NAMESPACE}.{TABLE_NAME}"
        LIMIT = 20

        print(f"Running Iceberg Table Summary for '{FULL_TABLE_NAME}'...")
        print_table_summary(FULL_TABLE_NAME, LIMIT)
        print("Check complete.")
    except ImportError as e:
        print(f"ERROR: Failed to import settings: {e}")
        import traceback
        traceback.print_exc()
    except Exception as main_err:
        print(f"An error occurred in main execution: {main_err}")
        import traceback
        traceback.print_exc() 