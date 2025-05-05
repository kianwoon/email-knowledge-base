# Purpose: Inspect the current schema of the Iceberg 'email_facts' table.
# Ensure you run this in the same environment where your app runs,
# so it can access the necessary settings/environment variables.

import logging
from pyiceberg.catalog.rest import RestCatalog
from app.config import settings # Import your application's settings

# Configure logging for pyiceberg if needed
logging.basicConfig(level=logging.INFO)
logging.getLogger("pyiceberg").setLevel(logging.INFO)

# --- Catalog Configuration (from your settings) ---
catalog_props = {
    "name": "inspector_catalog", # Can be any name
    "uri": settings.R2_CATALOG_URI,
    "warehouse": settings.R2_CATALOG_WAREHOUSE,
    "token": settings.R2_CATALOG_TOKEN,
    # Add any other necessary properties your catalog requires
}

# --- Table Identifier (from your settings) ---
table_namespace = settings.ICEBERG_DEFAULT_NAMESPACE
table_name = settings.ICEBERG_EMAIL_FACTS_TABLE
full_table_name = f"{table_namespace}.{table_name}"

print(f"Attempting to connect to catalog at URI: {catalog_props['uri']}")
print(f"Attempting to load table: {full_table_name}")

try:
    # --- Load Catalog ---
    catalog = RestCatalog(**catalog_props)
    print("Catalog connected successfully.")

    # --- Load Table ---
    table = catalog.load_table(full_table_name)
    print(f"Table '{full_table_name}' loaded successfully.")

    # --- Get and Print Schema ---
    actual_schema = table.schema()
    print("\n--- Actual Iceberg Table Schema ---")
    print(actual_schema)
    print("---------------------------------")

except Exception as e:
    print(f"\nAn error occurred: {e}")
    logging.error("Failed to inspect Iceberg schema", exc_info=True) 