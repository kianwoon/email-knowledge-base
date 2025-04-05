from fastapi import APIRouter, Request, Body, HTTPException#, WebSocket, WebSocketDisconnect
import logging
import json # Import json for broadcasting

from app.models.analysis import WebhookPayload
from app.store import analysis_results_store
# Import the WebSocket manager
from app.websocket import manager 

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analysis", status_code=202) # Use 202 Accepted 
async def receive_subject_analysis(
    request: Request, # Added Request object parameter
    payload: WebhookPayload = Body(...)
):
    """Receives the analysis result from the external API via webhook."""
    
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

    # Store the entire payload (or just the result part) in the in-memory store
    analysis_results_store[payload.job_id] = payload.dict()
    
    logger.info(f"[WEBHOOK] Stored result for job_id: {payload.job_id}")
    
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