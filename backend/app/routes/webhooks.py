from fastapi import APIRouter, Request, Body, HTTPException, Depends
import logging
import json # Import json for broadcasting
import uuid
from typing import List, Dict, Any
from pydantic import BaseModel, Field

# Qdrant imports
# Import client and necessary models separately
from qdrant_client import QdrantClient
# Import models, removing ScrollResponse as it causes import errors 
from qdrant_client.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue, ScrollRequest # Common models

from app.models.analysis import WebhookPayload
from app.store import analysis_results_store
# Import the WebSocket manager
from app.websocket import manager
# Import Qdrant client dependency function
from ..db.qdrant_client import get_qdrant_client
from app.config import settings # Correct import
from ..websocket import manager # Correct import

# Add asyncio for sleep
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

# Define the expected structure of the incoming webhook data
class AnalysisResultItem(BaseModel):
    tag: str
    cluster: str
    subject: str

class WebhookPayload(BaseModel):
    results: List[AnalysisResultItem]
    job_id: str | int # Accept int or str, will convert to str
    status: str | None = None # Optional status field

@router.post("/analysis", status_code=202) # Use 202 Accepted 
async def handle_analysis_webhook(
    webhook_data: WebhookPayload,
    request: Request,
    qdrant: QdrantClient = Depends(get_qdrant_client) # <-- Add Qdrant dependency
):
    """
    Handles incoming webhook callbacks from the external analysis service.
    1. Receives analysis results and the external job ID.
    2. Looks up the internal job ID using the external job ID mapping in Qdrant.
    3. Retrieves the original owner and query criteria using the internal job ID.
    4. Stores the analysis chart data in Qdrant, associated with the internal job ID.
    5. Broadcasts the results via WebSocket to the relevant frontend client.
    """
    try:
        # Log raw body for debugging (optional, consider removing in production)
        # raw_body = await request.body()
        # logger.info(f"[WEBHOOK-DEBUG] Raw body received: {raw_body.decode()}")

        external_job_id = str(webhook_data.job_id) # Ensure it's a string
        logger.info(f"[WEBHOOK] Received analysis results for EXTERNAL job_id: {external_job_id}")
        logger.debug(f"[WEBHOOK] Status received: {webhook_data.status}")
        logger.debug(f"[WEBHOOK] Payload results count: {len(webhook_data.results)}")

        # --- Find Internal Job ID using In-Memory Dictionary --- 
        internal_job_id = None
        job_store = request.app.state.job_mapping_store

        try:
            external_job_id_str = external_job_id # Already ensured string above
            
            # Lookup in the dictionary
            internal_job_id = job_store.get(external_job_id_str)

            if internal_job_id:
                logger.info(f"[WEBHOOK] Found internal job ID (via memory store): {internal_job_id} for external ID: {external_job_id_str}")
                # Optionally remove the mapping now that it's used?
                # try:
                #     del job_store[external_job_id_str]
                #     logger.info(f"[WEBHOOK] Removed mapping for {external_job_id_str} from memory store. Size now: {len(job_store)}")
                # except KeyError:
                #     logger.warning(f"[WEBHOOK] Tried to remove mapping for {external_job_id_str}, but it was already gone.")
            else:
                logger.warning(f"[WEBHOOK] No mapping found in memory store for external job ID: {external_job_id_str}. Cannot correlate callback. Store size: {len(job_store)}")

        except Exception as e:
            logger.error(f"[WEBHOOK] Error looking up external job ID mapping ({external_job_id_str}) in memory store: {e}")
            internal_job_id = None # Ensure it's None if lookup fails

        # If internal_job_id could not be found, we cannot proceed meaningfully
        if not internal_job_id:
             logger.error(f"[WEBHOOK] Halting processing for external job {external_job_id} as internal job ID could not be determined.")
             return {"message": "Webhook received but could not correlate to an internal job."}

        # --- Proceed using internal_job_id --- 
        
        # We need the owner. Since it's not in the simple dict mapping, 
        # we MUST retrieve the original query criteria point from Qdrant using internal_job_id
        owner = "unknown_owner" # Default
        try:
            # Find the query_criteria point using the internal_job_id
            logger.info(f"[WEBHOOK] Retrieving original query criteria from Qdrant for internal job {internal_job_id}")
            criteria_filter = Filter(
                must=[
                    FieldCondition(key="payload.type", match=MatchValue(value="query_criteria")),
                    FieldCondition(key="payload.job_id", match=MatchValue(value=internal_job_id))
                ]
            )
            criteria_search = qdrant.search(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query_filter=criteria_filter,
                query_vector=[0.0] * settings.EMBEDDING_DIMENSION, # Dummy vector
                limit=1
            )

            if criteria_search and len(criteria_search) == 1:
                 original_criteria_payload = criteria_search[0].payload
                 owner = original_criteria_payload.get("owner", owner) # Update owner
                 logger.info(f"[WEBHOOK] Retrieved owner '{owner}' from original criteria for internal job {internal_job_id}")
            else:
                 logger.warning(f"[WEBHOOK] Could not find original query_criteria point in Qdrant for internal job {internal_job_id}. Using default owner.")
        except Exception as e:
             logger.error(f"[WEBHOOK] Error retrieving original query criteria from Qdrant for internal job {internal_job_id}: {e}")
             # Continue with default owner, but log the error


        # --- RESTORED: Store the analysis chart data --- 
        logger.info(f"Storing chart data for internal job {internal_job_id} with owner='{owner}'")
        chart_point_id = str(uuid.uuid4()) # Unique ID for the chart data point
        chart_payload = {
            "type": "analysis_chart",
            "job_id": internal_job_id, # Store the INTERNAL job ID
            "owner": owner,
            "results": [item.model_dump() for item in webhook_data.results],
            "status": webhook_data.status or "completed" # Use provided status or default
        }
        chart_point = PointStruct(
            id=chart_point_id,
            payload=chart_payload,
            vector=[0.0] * settings.EMBEDDING_DIMENSION # ADDED dummy vector
        )
        try:
            qdrant.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=[chart_point],
                wait=True
            )
            logger.info(f"Successfully stored analysis chart data for internal job {internal_job_id}")
        except Exception as e:
            logger.error(f"Failed to store analysis chart data in Qdrant for internal job {internal_job_id}: {e}")
            # Decide if this error should prevent broadcasting
            # For now, log and continue to broadcast attempt
        # --- END RESTORED --- 


        # Broadcast the full payload via WebSocket
        websocket_message = {
            "type": "analysis_complete",
            "job_id": internal_job_id, 
            "payload": chart_payload # Send the full chart data payload again
        }
        logger.info(f"Attempting WebSocket broadcast for internal job_id: {internal_job_id} with payload")
        await manager.broadcast(
            message=json.dumps(websocket_message) 
        )
        logger.info(f"[WEBHOOK] Broadcast attempt finished for internal job_id: {internal_job_id}")

        return {"message": "Webhook processed successfully"}

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions to return proper status codes if raised during processing
         logger.error(f"[WEBHOOK] HTTPException during processing: {http_exc.status_code} - {http_exc.detail}")
         raise http_exc
    except Exception as e:
        external_job_id_for_log = webhook_data.job_id if 'webhook_data' in locals() else 'unknown'
        logger.error(f"[WEBHOOK] Unexpected error processing webhook for external job ID '{external_job_id_for_log}': {str(e)}", exc_info=True)
        # Return 202 anyway? Or a 500?
        # Let's return 500 for unexpected errors
        raise HTTPException(status_code=500, detail="Internal server error processing webhook.")

# Simple endpoint to retrieve stored results (for debugging/polling fallback)
@router.get("/results/{job_id}")
async def get_analysis_result(job_id: str):
    logger.info(f"[RESULTS] Request received for job_id: {job_id}")
    result = analysis_results_store.get(job_id)
    if not result:
        logger.warning(f"[RESULTS] Job ID {job_id} not found in store.")
        raise HTTPException(status_code=404, detail="Analysis result not found or not ready.")
    logger.info(f"[RESULTS] Returning stored result for job_id: {job_id}")
    return result 

# WebSocket Endpoint REMOVED 