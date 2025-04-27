print("--- Script starting ---") # ADDED FOR DEBUGGING
import os
import sys # Keep sys import
import logging
import pandas as pd
import duckdb  # Import DuckDB
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog, Catalog # Changed import for load_catalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError
from pyiceberg.expressions import Contains # ADD THIS LINE

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_iceberg_table(full_table_name: str, target_sender: str, limit: int):
    """Connects to the Iceberg REST catalog, loads a specified table via DuckDB, 
       and prints the last N records with all columns."""
    # Use passed arguments
    logger.info(f"Target Table: {full_table_name}")
    logger.info(f"Target Sender: {target_sender}")
    logger.info(f"Limit: {limit}")

    # Catalog initialization depends on settings, needs access to settings
    # Easiest is to assume settings object is available globally if imported in main
    # Or pass necessary settings fields as arguments too
    catalog_uri = settings.R2_CATALOG_URI
    catalog_warehouse = settings.R2_CATALOG_WAREHOUSE
    catalog_token = settings.R2_CATALOG_TOKEN
    catalog_name = settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_inspector_main"

    # --- Initialize Catalog ---
    _catalog: Catalog | None = None # Use local variable for catalog
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

    # --- Load Table and Read Data via PyIceberg Scan with Filter ---
    try:
        logger.info(f"Loading table '{full_table_name}' via PyIceberg Catalog...")
        iceberg_table = _catalog.load_table(full_table_name)
        logger.info(f"Table '{full_table_name}' loaded successfully via PyIceberg.")

        # Define the row filter using PyIceberg expressions
        # Using 'contains' for a LIKE '%...%' behavior
        # Note: Ensure the 'sender' column exists in your schema
        try:
            sender_filter = Contains("sender", target_sender)
            logger.info(f"Applying PyIceberg row_filter: contains(sender, '{target_sender}')")
        except ValueError as e:
            print(f"Error creating filter expression (Does 'sender' column exist?): {e}")
            return
        
        logger.info("Scanning filtered table data into Pandas via PyIceberg...")
        # Scan with the row filter and convert the result to Pandas
        filtered_df = iceberg_table.scan(row_filter=sender_filter).to_pandas()
        logger.info(f"Successfully read {len(filtered_df)} rows matching the sender filter into Pandas.")

        if filtered_df.empty:
            print(f"\n--- No records found matching sender filter: contains(sender, '{target_sender}') ---")
            return

        # Sort and limit using Pandas
        logger.info("Sorting results by received_datetime_utc...")
        if 'received_datetime_utc' not in filtered_df.columns:
            print("Error: 'received_datetime_utc' column not found for sorting.")
            results_df = filtered_df.head(limit) # Limit unsorted results
        else:
            try:
                # Convert to datetime just in case
                filtered_df['received_datetime_utc'] = pd.to_datetime(filtered_df['received_datetime_utc'], errors='coerce')
                results_df = filtered_df.sort_values(by='received_datetime_utc', ascending=False, na_position='last').head(limit)
            except Exception as sort_err:
                print(f"Warning: Could not properly sort by received_datetime_utc: {sort_err}. Limiting unsorted results.")
                results_df = filtered_df.head(limit)
        
        print(f"\n--- Last {limit} Records matching sender contains '{target_sender}' (Sorted by Date) --- ")
        # Set display options
        pd.set_option('display.max_rows', 40) 
        pd.set_option('display.max_columns', None) 
        pd.set_option('display.width', 2000) 
        pd.set_option('display.max_colwidth', 100)
        print(results_df)
        print("---------------------------------------------------------------------")

    except (NoSuchTableError, NoSuchNamespaceError):
        logger.error(f"Error: Table or Namespace not found: {full_table_name}")
        print(f"Error: Iceberg table '{full_table_name}' or its namespace not found. Please ensure it exists.")
    except RuntimeError as e:
        # Catch potential catalog init errors if get_iceberg_catalog raises it
        logger.error(f"Catalog initialization or loading failed: {e}")
        print(f"Error: Could not initialize/load Iceberg catalog/table. Check connection details and REST service status.")
    except KeyError as e:
        logger.error(f"DataFrame column error: {e}", exc_info=True)
        print(f"Error: A required column ({e}) was not found in the DataFrame.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
    finally:
        # No DuckDB connection to close here anymore
        logger.info("Script execution finished within check_iceberg_table.")


if __name__ == "__main__":
    # Import settings here to ensure .env is loaded first
    try:
        # Add sys.path modification right before import
        project_root_main = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if project_root_main not in sys.path:
            sys.path.insert(0, project_root_main)
            print(f"Added project root to sys.path: {project_root_main}")
        else:
            print(f"Project root already in sys.path: {project_root_main}")
        print(f"Current sys.path: {sys.path}") # Log sys.path for debugging
        
        # Add a print statement before the import
        print("Attempting to import settings...") 
        from backend.app.config import settings
        print("Settings imported successfully.") # Add confirmation
        
        # Now load dotenv using the correct path based on where the script *is*
        dotenv_path_main = os.path.join(project_root_main, '.env')
        if os.path.exists(dotenv_path_main):
            load_dotenv(dotenv_path=dotenv_path_main)
            logger.info(f"Loaded .env file from: {dotenv_path_main}")
        else:
            logger.warning(f".env file not found at: {dotenv_path_main}")

        # Resetup logging potentially based on new settings
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)

        # Configuration that depends on settings
        TARGET_SENDER = "derick.ooick@beyondsoft.com" # The sender email to search for
        TABLE_NAMESPACE = settings.ICEBERG_DEFAULT_NAMESPACE
        TABLE_NAME = settings.ICEBERG_EMAIL_FACTS_TABLE
        FULL_TABLE_NAME = f"{TABLE_NAMESPACE}.{TABLE_NAME}"
        LIMIT = 20 # Number of records to display

        # Now initialize catalog and run check
        _iceberg_catalog = None # Reset global catalog in case it was partially init before
        
        print("Running Iceberg Table Check...")
        check_iceberg_table(FULL_TABLE_NAME, TARGET_SENDER, LIMIT) # Pass config as args
        print("Check complete.") 
    except ImportError as e: # Catch the specific ImportError
        # Print the actual import error
        print(f"ERROR: Failed to import settings: {e}") 
        # Optionally print traceback for more details
        import traceback
        traceback.print_exc()
    except Exception as main_err:
        print(f"An error occurred in main execution: {main_err}")
        import traceback
        traceback.print_exc() # Print traceback for any other error in main 