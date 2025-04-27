import os
import sys
import logging
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog, Catalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError

# Add project root to sys.path to allow importing backend.app.config
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def drop_iceberg_table(full_table_name: str):
    """Connects to the Iceberg REST catalog and drops the specified table."""
    
    # Assume settings object is available globally if imported in main
    catalog_uri = settings.R2_CATALOG_URI
    catalog_warehouse = settings.R2_CATALOG_WAREHOUSE
    catalog_token = settings.R2_CATALOG_TOKEN
    catalog_name = settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_dropper"

    logger.info(f"Attempting to drop table: {full_table_name}")

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

    # --- Drop Table --- 
    try:
        logger.info(f"Checking if table '{full_table_name}' exists...")
        if _catalog.table_exists(full_table_name):
            logger.warning(f"Table '{full_table_name}' found. Proceeding with drop operation...")
            _catalog.drop_table(full_table_name)
            logger.info(f"Successfully dropped table: {full_table_name}")
            print(f"Successfully dropped table: {full_table_name}")
        else:
            logger.info(f"Table '{full_table_name}' does not exist. No action taken.")
            print(f"Table '{full_table_name}' does not exist.")

    except NoSuchNamespaceError:
        logger.error(f"Error: Namespace for table '{full_table_name}' does not exist.")
        print(f"Error: Namespace for table '{full_table_name}' not found.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during drop operation: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
    finally:
        logger.info("Script execution finished within drop_iceberg_table.")


if __name__ == "__main__":
    print("--- Script starting: Drop Iceberg Table ---")
    try:
        # Add sys.path modification right before import
        project_root_main = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if project_root_main not in sys.path:
            sys.path.insert(0, project_root_main)
            # print(f"Added project root to sys.path: {project_root_main}") # Optional debug
        # else:
            # print(f"Project root already in sys.path: {project_root_main}") # Optional debug
        
        print("Attempting to import settings...")
        from backend.app.config import settings
        print("Settings imported successfully.")

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
        TABLE_NAMESPACE = settings.ICEBERG_DEFAULT_NAMESPACE
        TABLE_NAME = settings.ICEBERG_EMAIL_FACTS_TABLE
        FULL_TABLE_NAME = f"{TABLE_NAMESPACE}.{TABLE_NAME}"
        
        # Confirmation step
        confirm = input(f"Are you sure you want to permanently drop the Iceberg table '{FULL_TABLE_NAME}'? (yes/no): ")
        if confirm.lower() == 'yes':
            print(f"Proceeding to drop table '{FULL_TABLE_NAME}'...")
            drop_iceberg_table(FULL_TABLE_NAME)
            print("Drop operation complete.")
        else:
            print("Operation cancelled by user.")
            
    except ImportError as e:
        print(f"ERROR: Failed to import settings: {e}")
        import traceback
        traceback.print_exc()
    except Exception as main_err:
        print(f"An error occurred in main execution: {main_err}")
        import traceback
        traceback.print_exc() 