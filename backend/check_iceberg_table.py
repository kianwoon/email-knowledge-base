import os
import logging
import pandas as pd
from dotenv import load_dotenv
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_iceberg_table():
    """Connects to the Iceberg REST catalog, loads a specified table, and prints its content."""
    # Load environment variables from .env file located in the script's directory or parent
    # Assumes .env is in the same directory as this script or the CWD
    load_dotenv() 

    # --- Configuration ---
    catalog_uri = os.getenv("R2_CATALOG_URI")
    catalog_warehouse = os.getenv("R2_CATALOG_WAREHOUSE")
    catalog_token = os.getenv("R2_CATALOG_TOKEN")
    
    # Get namespace and table name from environment variables, with defaults
    table_namespace = os.getenv("ICEBERG_DEFAULT_NAMESPACE", "default") # Provide a fallback default
    table_name = os.getenv("ICEBERG_EMAIL_FACTS_TABLE", "email_facts") # Provide a fallback default
    
    full_table_name = f"{table_namespace}.{table_name}"

    if not all([catalog_uri, catalog_warehouse, catalog_token]):
        logger.error("Missing required environment variables: R2_CATALOG_URI, R2_CATALOG_WAREHOUSE, R2_CATALOG_TOKEN")
        print("Error: Missing required environment variables. Ensure your .env file is set up correctly.")
        return

    logger.info(f"Attempting to connect to Iceberg REST Catalog at URI: {catalog_uri}")
    logger.info(f"Target Table: {full_table_name}")

    # --- Initialize Catalog ---
    try:
        catalog_props = {
            "name": "check_table_catalog",
            "uri": catalog_uri,
            "warehouse": catalog_warehouse,
            "token": catalog_token,
            # Optional: Add downcast setting if needed for reading, though usually for writing
            # "pyiceberg.io.pyarrow.downcast-ns-timestamp-to-us-on-write": True 
        }
        catalog = RestCatalog(**catalog_props)
        logger.info("Iceberg REST Catalog initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Iceberg REST Catalog: {e}", exc_info=True)
        print(f"Error: Failed to initialize Iceberg Catalog: {e}")
        return

    # --- Load Table and Read Data ---
    try:
        logger.info(f"Loading table: {full_table_name}")
        table = catalog.load_table(full_table_name)
        logger.info(f"Table '{full_table_name}' loaded successfully.")

        logger.info("Scanning table data...")
        # Scan the table and convert to Pandas DataFrame
        df = table.scan().to_pandas()
        
        logger.info(f"Successfully read {len(df)} rows from the table.")

        if df.empty:
            print(f"The table '{full_table_name}' exists but is currently empty.")
        else:
            print(f"--- Contents of Iceberg Table: {full_table_name} ---")
            # Configure pandas display options for better readability
            pd.set_option('display.max_rows', None)       # Show all rows
            pd.set_option('display.max_columns', None)    # Show all columns
            pd.set_option('display.width', 1000)          # Adjust display width
            pd.set_option('display.max_colwidth', 100)     # Limit column width
            print(df)
            print("--------------------------------------------------")

    except NoSuchTableError:
        logger.error(f"Table '{full_table_name}' does not exist in the catalog.")
        print(f"Error: Table '{full_table_name}' not found.")
    except NoSuchNamespaceError:
         logger.error(f"Namespace '{table_namespace}' does not exist in the catalog.")
         print(f"Error: Namespace '{table_namespace}' not found.")
    except Exception as e:
        logger.error(f"An error occurred while loading or reading the table: {e}", exc_info=True)
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("Running Iceberg Table Check...")
    check_iceberg_table()
    print("Check complete.") 