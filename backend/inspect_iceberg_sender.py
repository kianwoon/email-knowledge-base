import os
import sys
import logging
import pandas as pd
import duckdb
from pyiceberg.catalog import load_catalog, Catalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError
from dotenv import load_dotenv

# Add project root to sys.path to allow importing backend.app.config
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from backend.app.config import settings
except ImportError as e:
    print(f"Error: Could not import settings from backend.app.config: {e}")
    print(f"Attempted project root: {project_root}")
    print(f"Current sys.path: {sys.path}")
    print("Ensure this script is run from the 'backend' directory or adjust path logic.")
    exit(1)
except Exception as import_err:
    print(f"An unexpected error occurred during settings import: {import_err}")
    exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Load environment variables from .env file in the project root (one level up from backend)
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)
logger.info(f"Attempting to load .env file from: {dotenv_path}")

TARGET_SENDER = "derick.ooick@beyondsoft.com" # The sender email to search for
TABLE_NAMESPACE = settings.ICEBERG_DEFAULT_NAMESPACE
TABLE_NAME = settings.ICEBERG_EMAIL_FACTS_TABLE
FULL_TABLE_NAME = f"{TABLE_NAMESPACE}.{TABLE_NAME}"
LIMIT = 20 # Number of records to display

# --- Catalog Initialization ---
_iceberg_catalog: Catalog | None = None

def get_iceberg_catalog() -> Catalog:
    """Initializes and returns the Iceberg catalog instance."""
    global _iceberg_catalog
    if _iceberg_catalog is None:
        logger.info("Initializing Iceberg REST Catalog...")
        try:
            catalog_props = {
                "name": settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_inspector",
                "uri": settings.R2_CATALOG_URI,
                "warehouse": settings.R2_CATALOG_WAREHOUSE,
                "token": settings.R2_CATALOG_TOKEN,
            }
            catalog_props = {k: v for k, v in catalog_props.items() if v is not None}
            _iceberg_catalog = load_catalog(**catalog_props)
            logger.info("Iceberg Catalog initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Iceberg Catalog: {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize Iceberg Catalog: {e}") from e
    return _iceberg_catalog

def inspect_sender_data(sender_email: str):
    """Queries Iceberg for records from the specified sender and prints them."""
    logger.info(f"Starting inspection for sender: {sender_email}")
    
    try:
        catalog = get_iceberg_catalog()
        
        logger.info(f"Attempting to load table: {FULL_TABLE_NAME}")
        iceberg_table = catalog.load_table(FULL_TABLE_NAME)
        logger.info(f"Table '{FULL_TABLE_NAME}' loaded.")

        logger.info("Connecting to in-memory DuckDB...")
        con = duckdb.connect(database=':memory:', read_only=False)
        
        view_name = 'email_facts_view'
        logger.info(f"Registering Iceberg table '{FULL_TABLE_NAME}' as DuckDB view '{view_name}'...")
        iceberg_table.scan().to_duckdb(table_name=view_name, connection=con)
        logger.info("View registered successfully.")

        # Construct the query
        # Using LIKE to potentially match variations if the sender field includes display name
        query = f"""
        SELECT 
            sender, 
            subject, 
            received_datetime_utc, 
            message_id,
            owner_email -- Added owner_email for context
        FROM {view_name}
        WHERE sender LIKE ? 
        ORDER BY received_datetime_utc DESC
        LIMIT ?;
        """
        params = [f'%{sender_email}%', LIMIT]

        logger.info(f"Executing query for sender '{sender_email}' (Limit: {LIMIT})...")
        logger.debug(f"SQL: {query.strip()} PARAMS: {params}")
        
        results_df = con.execute(query, params).fetchdf()
        
        logger.info(f"Query returned {len(results_df)} records.")

        if not results_df.empty:
            print(f"\n--- Records found for sender LIKE '%{sender_email}%' (Last {LIMIT}) ---")
            # Set display options for better readability
            pd.set_option('display.max_rows', None)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1000)
            pd.set_option('display.max_colwidth', 100) # Adjust column width as needed
            print(results_df)
            print("------------------------------------------------------")
        else:
            print(f"\n--- No records found matching sender LIKE '%{sender_email}%' ---")

        con.close()
        logger.info("DuckDB connection closed.")

    except (NoSuchTableError, NoSuchNamespaceError):
        logger.error(f"Error: Table or Namespace not found: {FULL_TABLE_NAME}")
        print(f"Error: Iceberg table '{FULL_TABLE_NAME}' or its namespace not found. Please ensure it exists.")
    except RuntimeError as e:
        logger.error(f"Catalog initialization failed: {e}")
        print(f"Error: Could not initialize Iceberg catalog. Check connection details and REST service status.")
    except duckdb.Error as e:
         logger.error(f"DuckDB query execution failed: {e}", exc_info=True)
         print(f"Error executing DuckDB query: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
    finally:
        if 'con' in locals() and con:
            try:
                con.close()
            except Exception: pass # Ignore errors during cleanup close

if __name__ == "__main__":
    print(f"Inspecting Iceberg table '{FULL_TABLE_NAME}' for sender: {TARGET_SENDER}")
    inspect_sender_data(TARGET_SENDER)
    print("Inspection script finished.") 