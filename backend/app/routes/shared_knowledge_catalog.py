from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime, timezone
import json
import time

from app.db.session import get_db
from app.models.token import Token
from app.models.external_audit_log import ExternalAuditLog
from app.schemas.shared_knowledge import CatalogSearchRequest, CatalogSearchResult
from app.dependencies.auth import get_validated_token
from app.crud import crud_catalog
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/search_catalog", response_model=List[CatalogSearchResult])
def search_shared_catalog(
    *, 
    db: Session = Depends(get_db),
    token: Token = Depends(get_validated_token),
    request_body: CatalogSearchRequest = Body(...)
) -> List[Dict[str, Any]]:
    """
    Search the shared knowledge catalog (structured data like Iceberg/DuckDB)
    using the provided token for authentication and filtering.
    
    Applies token restrictions:
    - `is_active`, `expiry` (handled by `get_validated_token`)
    - `row_limit` (limits the number of results)
    - `allow_columns` (restricts the fields returned in each result)
    - `allow_attachments` (influences default columns if `allow_columns` is null)
    
    Does NOT currently apply token restrictions:
    - `allow_rules`, `deny_rules`, `sensitivity` (row-level filtering based on these is deferred)
    """
    start_time = time.perf_counter()
    audit_log = None

    effective_limit = min(request_body.limit, token.row_limit)
    
    # Extract filters from request body
    filters = {
        "sender": request_body.sender,
        "date_from": request_body.date_from,
        "date_to": request_body.date_to
    }
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}

    try:
        # --- Implement Catalog Search Logic ---
        results = crud_catalog.search_catalog_items(
            query=request_body.query,
            token=token,
            effective_limit=effective_limit,
            filters=filters
        )
        # --- End Implementation ---
        
        end_time = time.perf_counter()
        execution_time_ms = int((end_time - start_time) * 1000)
        
        # --- Implement Audit Logging like in shared_knowledge.py ---
        try:
            # Serialize filters and response summary
            filter_json_data = json.dumps(filters, default=str) if filters else None
            response_details = {"result_count": len(results)}
            response_data_json = json.dumps(response_details)
            
            audit_log = ExternalAuditLog(
                token_id=token.id,
                action_type='SHARED_CATALOG_SEARCH',
                resource_id=crud_catalog.DEFAULT_CATALOG_TABLE,
                query_text=request_body.query, 
                filter_data=filter_json_data, 
                result_count=len(results),
                response_data=response_data_json, 
                execution_time_ms=execution_time_ms,
                created_at=datetime.now(timezone.utc)
            )
            db.add(audit_log)
            db.commit()
            logger.info(f"Successfully logged audit entry for catalog search (Token ID: {token.id})")
        except Exception as audit_exc:
            logger.error(f"Failed to save audit log for catalog search (Token ID: {token.id}): {audit_exc}", exc_info=True)
            db.rollback()
        # --- End Audit Logging ---
            
        return results

    except Exception as e:
        # --- Log Error (but cannot use factory anymore) ---
        logger.error(f"Error during catalog search (Token ID: {token.id}): {e}", exc_info=True)
        # Optionally try to log an error audit event here if possible, without factory
        # try:
        #     filter_json_data = json.dumps(filters, default=str) if filters else None
        #     error_audit = ExternalAuditLog(
        #         token_id=token.id,
        #         action_type='SHARED_CATALOG_SEARCH_ERROR',
        #         query_text=request_body.query,
        #         filter_data=filter_json_data,
        #         response_data=json.dumps({"error": str(e)}),
        #         created_at=datetime.now(timezone.utc)
        #     )
        #     db.add(error_audit)
        #     db.commit()
        # except Exception as audit_err_log_exc:
        #     logger.error(f"Failed to save ERROR audit log for catalog search: {audit_err_log_exc}")
        #     db.rollback()
        # --- End Error Audit Attempt ---
            
        # Re-raise a generic HTTP exception 
        print(f"Error during catalog search: {e}") # Log for server debugging
        raise HTTPException(status_code=500, detail="Internal server error during catalog search.") 