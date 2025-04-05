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
    logger.info(f"+++ WebSocket connection attempt RECEIVED from {client_host}:{client_port} for path /api/analysis +++") # Updated log path
    
    await manager.connect(websocket)
    logger.info(f"+++ WebSocket client {client_host}:{client_port} CONNECTED successfully +++") # Log success *after* connect
    try:
        while True:
            # Keep the connection alive, optionally handle messages from client
            data = await websocket.receive_text()
            logger.info(f"Received message from WebSocket client {websocket.client}: {data}")
            # Example: Echo back or handle client messages if needed
            # await manager.send_personal_message(f"You wrote: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket client {websocket.client} disconnected gracefully.")
    except Exception as e:
        # Log other exceptions that might occur
        logger.error(f"WebSocket error for client {websocket.client}: {e}", exc_info=True)
        manager.disconnect(websocket) # Ensure disconnect on error 