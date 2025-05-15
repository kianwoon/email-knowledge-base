# backend/app/routes/schema.py
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pyiceberg.exceptions import NoSuchTableError

# Import Iceberg catalog getter (adapt path if needed)
# We might need to adjust how the catalog is accessed if llm.py dependencies are complex
# For now, let's assume we can import and use it similarly
# If this causes issues, we'll refactor catalog access.
from app.services.duckdb import get_iceberg_catalog # Removed get_duckdb_conn
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
        catalog = await get_iceberg_catalog() 
        if not catalog:
            logger.error("Iceberg Catalog is not available.")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Iceberg Catalog is not available.")

        full_table_name = f"{settings.ICEBERG_DEFAULT_NAMESPACE}.{settings.ICEBERG_EMAIL_FACTS_TABLE}"
        
        iceberg_table = None
        try:
            iceberg_table = catalog.load_table(full_table_name)
            logger.debug(f"Iceberg table '{full_table_name}' loaded successfully.")
        except NoSuchTableError:
            logger.error(f"Iceberg table '{full_table_name}' not found in catalog.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Iceberg table '{full_table_name}' not found.")
        except Exception as load_err:
            logger.error(f"Error loading Iceberg table '{full_table_name}': {load_err}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load Iceberg table information.")

        if not iceberg_table:
            # This case should ideally be covered by exceptions from load_table,
            # but as a safeguard:
            logger.error(f"Iceberg table object for '{full_table_name}' is None after load_table call.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to obtain valid Iceberg table object for '{full_table_name}'.")

        table_schema = iceberg_table.schema()
        if not table_schema:
            logger.error(f"Could not retrieve a valid schema object for Iceberg table '{full_table_name}'.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve schema for Iceberg table '{full_table_name}'.")
        
        # Ensure table_schema.fields is not None before iterating
        if table_schema.fields is None:
            logger.warning(f"Schema for table '{full_table_name}' has no fields (fields attribute is None). Returning empty list of columns.")
            column_names = []
        else:
            column_names = [field.name for field in table_schema.fields]
        
        logger.info(f"Successfully retrieved {len(column_names)} columns for '{full_table_name}' using direct schema access.")
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
