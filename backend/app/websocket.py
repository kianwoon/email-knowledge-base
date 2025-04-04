from typing import List
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {websocket.client}. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected: {websocket.client}. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message to {websocket.client}: {e}")
            self.disconnect(websocket) # Disconnect if sending fails

    async def broadcast(self, message: str):
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {connection.client}: {e}. Marking for disconnect.")
                disconnected_clients.append(connection)
        
        # Remove disconnected clients after broadcasting
        for client in disconnected_clients:
            self.disconnect(client)
        
        if disconnected_clients:
             logger.info(f"Finished broadcast. Disconnected {len(disconnected_clients)} clients.")

# Instantiate the manager globally
manager = ConnectionManager() 