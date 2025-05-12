import logging
from typing import Dict, List, Optional, Any
from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manager for WebSocket connections.
    Maintains active connections and provides methods to communicate with clients.
    """
    
    def __init__(self):
        # Dict of user_id -> Dict of conversation_id -> WebSocket connection
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, conversation_id: str):
        """
        Connect a new WebSocket client
        """
        await websocket.accept()
        
        # Initialize user dict if not exists
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        
        # Store the connection
        self.active_connections[user_id][conversation_id] = websocket
        logger.info(f"New WebSocket connection: user={user_id}, conversation={conversation_id}")
    
    def disconnect(self, user_id: str, conversation_id: str):
        """
        Remove a WebSocket connection
        """
        if user_id in self.active_connections and conversation_id in self.active_connections[user_id]:
            del self.active_connections[user_id][conversation_id]
            
            # Clean up empty user dict
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
            logger.info(f"WebSocket disconnected: user={user_id}, conversation={conversation_id}")
    
    async def send_message(self, user_id: str, conversation_id: str, message: Dict[str, Any]):
        """
        Send a message to a specific client
        """
        if user_id in self.active_connections and conversation_id in self.active_connections[user_id]:
            websocket = self.active_connections[user_id][conversation_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json(message)
                    return True
                except Exception as e:
                    logger.error(f"Error sending WebSocket message: {str(e)}", exc_info=True)
                    return False
        return False
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """
        Broadcast a message to all connections for a user
        """
        if user_id in self.active_connections:
            for conversation_id, websocket in self.active_connections[user_id].items():
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to user {user_id}: {str(e)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients
        """
        for user_id in self.active_connections:
            await self.broadcast_to_user(user_id, message) 