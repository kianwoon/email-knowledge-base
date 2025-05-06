from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

# Import the WebSocket manager
from app.websocket import manager 

logger = logging.getLogger(__name__)
router = APIRouter()

# WebSocket Endpoint
@router.websocket("/analysis")
async def websocket_endpoint(websocket: WebSocket):
    client_host = websocket.client.host if websocket.client else "Unknown"
    client_port = websocket.client.port if websocket.client else "Unknown"
    logger.info(f"+++ WebSocket connection attempt RECEIVED from {client_host}:{client_port} for relative path /analysis +++")
    
    await manager.connect(websocket)
    logger.info(f"+++ WebSocket client {client_host}:{client_port} CONNECTED successfully +++") # Log success *after* connect
    try:
        logger.info(f"[WS-{client_port}] Entering main loop...")
        while True:
            logger.info(f"[WS-{client_port}] Waiting to receive text...")
            # Keep the connection alive, optionally handle messages from client
            data = await websocket.receive_text()
            logger.info(f"[WS-{client_port}] Received text: {data}")
            # Example: Echo back or handle client messages if needed
            # await manager.send_personal_message(f"You wrote: {data}", websocket)
    except WebSocketDisconnect as wsd:
        # Log specific disconnect reason if available
        logger.info(f"[WS-{client_port}] WebSocket client disconnected gracefully. Code: {wsd.code}, Reason: {wsd.reason}")
        manager.disconnect(websocket)
    except Exception as e:
        # Log other exceptions that might occur
        logger.error(f"[WS-{client_port}] WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket) # Ensure disconnect on error 