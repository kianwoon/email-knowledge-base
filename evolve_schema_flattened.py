# Purpose: Evolve the schema of the Iceberg 'email_facts' table for the flattened model.
# Specifically:
#   - Drop the 'quoted_details' column (ID 25).
#   - Add 'quoted_raw_text' column (StringType, optional).
#   - Add 'quoted_depth' column (IntegerType, optional).
# Ensure you run this in the same environment where your app runs,
# so it can access the necessary settings/environment variables.

import logging
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.types import StringType, IntegerType # Import required types
from app.config import settings
from pyiceberg.exceptions import NoSuchPropertyException

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("pyiceberg").setLevel(logging.INFO)

# --- Catalog Configuration (from your settings) ---
catalog_props = {
    "name": "evolver_catalog_flatten", # Can be any name
    "uri": settings.R2_CATALOG_URI,
    "warehouse": settings.R2_CATALOG_WAREHOUSE,
    "token": settings.R2_CATALOG_TOKEN,
    # Add any other necessary properties
}

# --- Table Identifier (from your settings) ---
table_namespace = settings.ICEBERG_DEFAULT_NAMESPACE
table_name = settings.ICEBERG_EMAIL_FACTS_TABLE
full_table_name = f"{table_namespace}.{table_name}"

# --- Columns to Modify ---
COLUMN_TO_DROP = "quoted_details"
COLUMN_TO_ADD_TEXT = "quoted_raw_text"
COLUMN_TO_ADD_DEPTH = "quoted_depth"

print(f"Attempting to connect to catalog at URI: {catalog_props['uri']}")
print(f"Attempting to load table: {full_table_name}")

try:
    # --- Load Catalog ---
    catalog = RestCatalog(**catalog_props)
    print("Catalog connected successfully.")

    # --- Load Table ---
    table = catalog.load_table(full_table_name)
    print(f"Table '{full_table_name}' loaded successfully.")

    # --- Get Current Schema --- 
    current_schema = table.schema()
    print("\n--- Current Table Schema (Before Evolution) ---")
    print(current_schema)
    print("---------------------------------------------")

    # --- Perform Schema Evolution --- 
    print(f"\nAttempting to evolve schema:")
    update = table.update_schema() # Start transaction
    commit_needed = False

    # 1. Drop 'quoted_details' if it exists
    try: 
        if current_schema.find_field(COLUMN_TO_DROP):
            print(f"  - Dropping column: {COLUMN_TO_DROP}")
            update.delete_column(COLUMN_TO_DROP)
            commit_needed = True
    except ValueError: # find_field raises ValueError if not found
        print(f"  - Column '{COLUMN_TO_DROP}' not found, skipping drop.")

    # 2. Add 'quoted_raw_text' if it doesn't exist
    try:
        current_schema.find_field(COLUMN_TO_ADD_TEXT)
        print(f"  - Column '{COLUMN_TO_ADD_TEXT}' already exists, skipping add.")
    except ValueError:
        print(f"  - Adding column: {COLUMN_TO_ADD_TEXT} (StringType, optional)")
        update.add_column(COLUMN_TO_ADD_TEXT, StringType())
        commit_needed = True
        
    # 3. Add 'quoted_depth' if it doesn't exist
    try:
        current_schema.find_field(COLUMN_TO_ADD_DEPTH)
        print(f"  - Column '{COLUMN_TO_ADD_DEPTH}' already exists, skipping add.")
    except ValueError:
        print(f"  - Adding column: {COLUMN_TO_ADD_DEPTH} (IntegerType, optional)")
        update.add_column(COLUMN_TO_ADD_DEPTH, IntegerType())
        commit_needed = True

    # Commit the transaction if changes were made
    if commit_needed:
        print("\nCommitting schema evolution...")
        update.commit()
        print("Schema evolution committed successfully!")

        # --- Verify New Schema --- 
        table.refresh() # Refresh table metadata
        new_schema = table.schema()
        print("\n--- New Table Schema (After Evolution) ---")
        print(new_schema)
        print("------------------------------------------")
    else:
        print("\nNo schema changes needed.")

except NoSuchPropertyException as e:
    print(f"\nConfiguration Error: Missing property in settings - {e}")
    logging.error("Failed to evolve Iceberg schema due to missing config", exc_info=True)
except Exception as e:
    print(f"\nAn error occurred during schema evolution: {e}")
    logging.error("Failed to evolve Iceberg schema", exc_info=True) 