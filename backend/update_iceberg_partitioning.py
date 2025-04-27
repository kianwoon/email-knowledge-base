# backend/update_iceberg_partitioning.py
import os
import sys
import logging
import traceback
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import StringType
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform
from pyiceberg.exceptions import NoSuchTableError

# --- Configuration (Adapt from your settings) ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
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
PARTITION_COLUMN = "owner_email"

# --- Catalog Initialization ---
try:
    logger.info("Initializing Iceberg REST Catalog...")
    catalog_props = {
        "name": "r2_catalog_partition_update",
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

# --- Main Update Logic ---
table = None
try:
    logger.info(f"Attempting to load table: {FULL_TABLE_NAME}")
    table = catalog.load_table(FULL_TABLE_NAME)
    logger.info(f"Table '{FULL_TABLE_NAME}' loaded successfully.")

    schema = table.schema()
    spec = table.spec()

    # 1. Check and Add Partition Column to Schema if necessary
    owner_email_field = None
    try:
        owner_email_field = schema.find_field(PARTITION_COLUMN, case_sensitive=False)
        logger.info(f"Column '{PARTITION_COLUMN}' already exists in the schema (ID: {owner_email_field.field_id}).")
    except ValueError:
        logger.info(f"Column '{PARTITION_COLUMN}' not found in schema. Attempting to add it.")
        try:
            with table.update_schema() as update:
                # Add the column. Ensure the type (StringType) is appropriate.
                update.add_column(PARTITION_COLUMN, StringType(), f"Partition key: Owner email address")
            logger.info(f"Successfully submitted schema update to add column '{PARTITION_COLUMN}'.")
            # Reload table metadata to reflect the change
            logger.info("Reloading table metadata after schema update...")
            table = catalog.load_table(FULL_TABLE_NAME)
            schema = table.schema()
            owner_email_field = schema.find_field(PARTITION_COLUMN, case_sensitive=False)
            logger.info(f"Column '{PARTITION_COLUMN}' added successfully (ID: {owner_email_field.field_id}).")
        except Exception as add_col_err:
            logger.error(f"Failed to add column '{PARTITION_COLUMN}' to schema: {add_col_err}", exc_info=True)
            exit(1)

    # Ensure we have the field info now
    if not owner_email_field:
        logger.error(f"Could not find or add column '{PARTITION_COLUMN}'. Cannot proceed with partitioning.")
        exit(1)

    # 2. Check and Update Partition Specification if necessary
    is_partitioned_correctly = False
    if spec.spec_id != 0: # Check if there's any partitioning
        for field in spec.fields:
            # Check if a field partitioning on the source column ID using IdentityTransform exists
            if field.source_id == owner_email_field.field_id and isinstance(field.transform, IdentityTransform):
                is_partitioned_correctly = True
                logger.info(f"Table is already partitioned by '{PARTITION_COLUMN}' (Field ID: {field.field_id}, Source ID: {field.source_id}).")
                break

    if not is_partitioned_correctly:
        logger.info(f"Table is not partitioned by '{PARTITION_COLUMN}' with IdentityTransform. Attempting to update partition spec.")
        # IMPORTANT: Changing the partition spec on a table with data can be a complex operation.
        # Iceberg might handle adding an identity partition field gracefully, but significant changes
        # often require data migration/rewriting for optimal performance.
        # Review Iceberg documentation on partition evolution.
        try:
            with table.update_spec() as update_spec:
                # Add identity partition field based on the source column name
                update_spec.add_identity(PARTITION_COLUMN)
            logger.info(f"Successfully submitted partition spec update to partition by '{PARTITION_COLUMN}'.")
            # Optionally reload table spec
            # table = catalog.load_table(FULL_TABLE_NAME)
            # logger.info(f"New partition spec: {table.spec()}")
        except Exception as spec_update_err:
            logger.error(f"Failed to update partition spec for '{PARTITION_COLUMN}': {spec_update_err}", exc_info=True)
            exit(1)
    else:
        logger.info("Partition specification already includes partitioning by owner_email.")

except NoSuchTableError:
    logger.error(f"Table '{FULL_TABLE_NAME}' does not exist. Cannot update schema or partitioning.")
    exit(1)
except Exception as e:
    logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    exit(1)

logger.info(f"Script finished. Table '{FULL_TABLE_NAME}' schema and partitioning checked/updated for '{PARTITION_COLUMN}'.") 