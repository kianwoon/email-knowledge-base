import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.dependencies.auth import get_current_active_user_ws
from app.websockets.manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/chat/{conversation_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    conversation_id: UUID,
    current_user: User = Depends(get_current_active_user_ws),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for receiving real-time agent messages during a chat.
    
    Args:
        websocket: WebSocket connection
        conversation_id: UUID of the conversation to monitor
        current_user: Authenticated user from token validation
        db: Database session
    """
    user_id = str(current_user.id)
    conv_id = str(conversation_id)
    
    # Accept and store the connection
    await ws_manager.connect(websocket, user_id, conv_id)
    
    try:
        # Keep the connection alive, waiting for messages
        while True:
            # Wait for messages from client (mostly ping/keep-alive)
            data = await websocket.receive_text()
            
            # Echo back to confirm receipt (optional)
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        # Clean up connection when client disconnects
        ws_manager.disconnect(user_id, conv_id)
        logger.info(f"WebSocket client disconnected: user={user_id}, conversation={conv_id}")
    except Exception as e:
        # Handle other exceptions
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        ws_manager.disconnect(user_id, conv_id) 