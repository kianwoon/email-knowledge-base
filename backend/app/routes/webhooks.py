from fastapi import APIRouter, Request, Body, HTTPException, Depends
import logging
import json # Import json for broadcasting
import uuid

# Qdrant imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct

from app.models.analysis import WebhookPayload
from app.store import analysis_results_store
# Import the WebSocket manager
from app.websocket import manager 
# Import Qdrant client dependency
from app.routes.vector import get_db 
from app.config import settings # Need settings for collection name & embedding dim

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analysis", status_code=202) # Use 202 Accepted 
async def receive_subject_analysis(
    request: Request, # Added Request object parameter
    payload: WebhookPayload = Body(...),
    qdrant_client: QdrantClient = Depends(get_db) # Inject Qdrant client
):
    """Receives the analysis result, stores it in Qdrant, and broadcasts via WebSocket."""
    
    # --- Temporary Debugging: Log Raw Body --- 
    try:
        raw_body = await request.body()
        logger.info(f"[WEBHOOK-DEBUG] Raw body received: {raw_body.decode()}")
    except Exception as e:
        logger.error(f"[WEBHOOK-DEBUG] Error reading raw body: {e}")
    # --- End Temporary Debugging ---
    
    # The following code will likely still fail with 422 if job_id is missing,
    # but the raw body log above will help us see what *was* sent.
    
    logger.info(f"[WEBHOOK] Received subject analysis for job_id: {payload.job_id}")
    logger.info(f"[WEBHOOK] Status: {payload.status}")

    if payload.job_id in analysis_results_store:
        logger.warning(f"[WEBHOOK] Job ID {payload.job_id} already exists in store. Overwriting.")

    # --- Store Analysis Chart Data in Qdrant --- 
    try:
        job_id_from_payload = str(payload.job_id) # Ensure it's a string
        owner_email = "unknown_owner" # Hardcode owner as lookup is not reliable
        logger.info(f"Storing chart data for job {job_id_from_payload} with owner='{owner_email}'")
        
        # Use chart_{job_id} for the *chart* point ID 
        chart_point_id = f"chart_{job_id_from_payload}" 
        
        chart_payload = {
            "type": "analysis_chart",
            "job_id": job_id_from_payload,
            "owner": owner_email,
            "status": payload.status or "unknown",
            "chart_data": payload.results.dict() if payload.results else [] 
        }
        chart_point = PointStruct(id=chart_point_id, vector=[0.0] * settings.EMBEDDING_DIMENSION, payload=chart_payload)
        
        logger.info(f"Storing analysis chart data with point ID {chart_point_id} for job {job_id_from_payload}")
        qdrant_client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[chart_point],
            wait=True
        )
        logger.info(f"Successfully stored analysis chart data for job {job_id_from_payload}")

    except Exception as e:
        logger.error(f"Failed to store analysis chart data for job {job_id_from_payload} in Qdrant: {str(e)}", exc_info=True)
        # Log error but continue - broadcasting result is primary function here
    # --- End Store Analysis Chart Data ---

    # --- Broadcast via WebSocket --- 
    try:
        # Convert payload to JSON string for broadcasting
        message_to_broadcast = payload.json()
        await manager.broadcast(message_to_broadcast) 
        logger.info(f"[WEBHOOK] Broadcasted result for job_id: {payload.job_id} via WebSocket.")
    except Exception as ws_err:
        logger.error(f"[WEBHOOK] Failed to broadcast via WebSocket: {ws_err}")
    # --- End Broadcast ---

    return {"message": "Webhook received"}

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