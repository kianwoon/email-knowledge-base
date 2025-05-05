# Purpose: Evolve the schema of the Iceberg 'email_facts' table.
# Specifically, change the type of the 'quoted_details' field (ID 25) to StringType.
# Ensure you run this in the same environment where your app runs,
# so it can access the necessary settings/environment variables.

import logging
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.types import StringType  # Import StringType
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("pyiceberg").setLevel(logging.INFO)

# --- Catalog Configuration (from your settings) ---
catalog_props = {
    "name": "evolver_catalog", # Can be any name
    "uri": settings.R2_CATALOG_URI,
    "warehouse": settings.R2_CATALOG_WAREHOUSE,
    "token": settings.R2_CATALOG_TOKEN,
    # Add any other necessary properties
}

# --- Table Identifier (from your settings) ---
table_namespace = settings.ICEBERG_DEFAULT_NAMESPACE
table_name = settings.ICEBERG_EMAIL_FACTS_TABLE
full_table_name = f"{table_namespace}.{table_name}"

FIELD_ID_TO_UPDATE = 25
FIELD_NAME_TO_UPDATE = "quoted_details"
NEW_TYPE = StringType()

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

    # Check if the field exists and needs updating
    field_to_update = current_schema.find_field(FIELD_ID_TO_UPDATE)
    if field_to_update.field_type == NEW_TYPE:
        print(f"Field '{FIELD_NAME_TO_UPDATE}' (ID: {FIELD_ID_TO_UPDATE}) is already of type {NEW_TYPE}. No evolution needed.")
    else:
        print(f"\nAttempting to evolve schema: Change field '{FIELD_NAME_TO_UPDATE}' (ID: {FIELD_ID_TO_UPDATE}) to {NEW_TYPE}")
        # --- Perform Schema Evolution --- 
        update = table.update_schema()
        update.update_column(FIELD_NAME_TO_UPDATE, NEW_TYPE)
        update.commit()
        print("Schema evolution committed successfully!")

        # --- Verify New Schema --- 
        table.refresh() # Refresh table metadata
        new_schema = table.schema()
        print("\n--- New Table Schema (After Evolution) ---")
        print(new_schema)
        print("------------------------------------------")

except Exception as e:
    print(f"\nAn error occurred during schema evolution: {e}")
    logging.error("Failed to evolve Iceberg schema", exc_info=True) 