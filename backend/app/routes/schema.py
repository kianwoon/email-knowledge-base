# backend/app/routes/schema.py
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import duckdb
from pyiceberg.exceptions import NoSuchTableError

# Import Iceberg catalog getter (adapt path if needed)
# We might need to adjust how the catalog is accessed if llm.py dependencies are complex
# For now, let's assume we can import and use it similarly
# If this causes issues, we'll refactor catalog access.
from app.services.llm import get_iceberg_catalog, get_duckdb_conn
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Schema"],
    responses={404: {"description": "Not found"}},
)

@router.get(
    "/email-facts/columns",
    response_model=List[str],
    summary="Get Email Facts Columns",
    description="Retrieves the list of available column names from the email_facts Iceberg table.",
)
async def get_email_facts_columns():
    """Returns the list of column names for the email_facts table."""
    logger.info("Request received for email_facts columns.")
    try:
        # Get Iceberg catalog
        # Note: get_iceberg_catalog uses an asyncio.Lock, which should be fine here.
        catalog = await get_iceberg_catalog() 
        if not catalog:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Iceberg Catalog is not available.")

        full_table_name = f"{settings.ICEBERG_DEFAULT_NAMESPACE}.{settings.ICEBERG_EMAIL_FACTS_TABLE}"
        
        # Check if table exists using the catalog
        try:
            catalog.load_table(full_table_name)
            logger.debug(f"Iceberg table '{full_table_name}' found.")
        except NoSuchTableError:
            logger.error(f"Iceberg table {full_table_name} not found in catalog.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Iceberg table '{full_table_name}' not found.")
        except Exception as load_err:
             logger.error(f"Error loading Iceberg table '{full_table_name}': {load_err}", exc_info=True)
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load Iceberg table information.")

        # Use global DuckDB connection
        con = get_duckdb_conn()
        
        # Load table into a DuckDB view (required for DESCRIBE)
        view_name = 'email_facts_view_schema_check' # Use a distinct view name
        # This scan might be slow if the table is huge, but necessary for DESCRIBE
        logger.debug(f"Loading Iceberg table '{full_table_name}' into DuckDB view '{view_name}' for schema description...")
        iceberg_table = catalog.load_table(full_table_name) # Load again, necessary for scan
        
        # Clean up the view first if it exists
        con.execute(f"DROP VIEW IF EXISTS {view_name}")
        
        # Use predicate and projection push-down to limit data scan
        scan = iceberg_table.scan().limit(1)  # We only need schema, so limit to 1 row
        scan.to_duckdb(table_name=view_name, connection=con)
        logger.debug("Table loaded into DuckDB view.")

        # Execute DESCRIBE to get schema info
        schema_info = con.execute(f"DESCRIBE {view_name};").fetchall()
        
        # Extract column names
        column_names = [row[0] for row in schema_info] # First element of each row is the column name
        
        # Clean up after use
        con.execute(f"DROP VIEW IF EXISTS {view_name}")
        
        logger.info(f"Successfully retrieved {len(column_names)} columns for email_facts.")
        return column_names

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions
        raise http_exc
    except Exception as e:
        logger.error(f"Failed to retrieve email_facts columns: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving table schema: {e}"
        ) 