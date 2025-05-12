import logging
import asyncio
from typing import Dict, Any, Optional, List
from uuid import UUID

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

class AutoGenMessageHook:
    """
    Hooks into the AutoGen message system to broadcast messages to WebSocket clients.
    """
    
    def __init__(self, app: FastAPI):
        """
        Initialize the message hook with the FastAPI app
        
        Args:
            app: FastAPI application instance with ws_manager in its state
        """
        self.app = app
    
    async def on_message(self, 
        user_id: str, 
        conversation_id: str, 
        message: Dict[str, Any]
    ) -> None:
        """
        Callback for when a new message is received from an agent
        
        Args:
            user_id: User ID associated with the conversation
            conversation_id: ID of the conversation
            message: The message to send
        """
        try:
            if hasattr(self.app.state, 'ws_manager'):
                ws_manager = self.app.state.ws_manager
                
                # Prepare the message
                ws_message = {
                    "type": "agent_message",
                    "data": {
                        "message": message,
                        "conversation_id": conversation_id,
                    }
                }
                
                # Send the message to the user's connection for this conversation
                await ws_manager.send_message(user_id, conversation_id, ws_message)
                logger.debug(f"Sent agent message to user {user_id} for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Error in message hook: {str(e)}", exc_info=True)
    
    async def on_thinking(self,
        user_id: str,
        conversation_id: str,
        agent_name: str
    ) -> None:
        """
        Signal that an agent is thinking
        
        Args:
            user_id: User ID associated with the conversation
            conversation_id: ID of the conversation
            agent_name: Name of the agent that's thinking
        """
        try:
            if hasattr(self.app.state, 'ws_manager'):
                ws_manager = self.app.state.ws_manager
                
                # Prepare the thinking message
                ws_message = {
                    "type": "agent_thinking",
                    "data": {
                        "agent_name": agent_name,
                        "conversation_id": conversation_id,
                    }
                }
                
                # Send the message to the user's connection for this conversation
                await ws_manager.send_message(user_id, conversation_id, ws_message)
                logger.debug(f"Sent thinking status for agent {agent_name} to user {user_id}")
        except Exception as e:
            logger.error(f"Error in thinking hook: {str(e)}", exc_info=True) 