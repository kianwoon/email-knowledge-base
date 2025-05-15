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
    Receives a single JSON chat request, starts the hybrid orchestration workflow, and closes after completion.
    """
    import json
    from fastapi import status
    from app.autogen.workflows import run_hybrid_orchestration_workflow
    from fastapi.concurrency import run_in_threadpool
    from starlette.websockets import WebSocketDisconnect
    from fastapi import Request

    user_id = str(current_user.id)
    conv_id = str(conversation_id)

    # Accept and store the connection
    await ws_manager.connect(websocket, user_id, conv_id)

    try:
        # Wait for a single JSON message from the client
        data = await websocket.receive_text()
        try:
            payload = json.loads(data)
        except Exception as e:
            logger.error(f"WebSocket received invalid JSON: {e}")
            await websocket.send_json({"type": "error", "error": "Invalid JSON payload."})
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            ws_manager.disconnect(user_id, conv_id)
            return

        logger.info(f"WebSocket received chat payload: {payload}")

        # Extract required fields
        message = payload.get("message")
        agents = payload.get("agents")
        model_id = payload.get("model_id")
        temperature = payload.get("temperature", 0.7)
        max_rounds = payload.get("max_rounds", 10)
        orchestration_type = payload.get("orchestration_type")
        use_mcp_tools = payload.get("use_mcp_tools", True)
        history = payload.get("history", [])

        # Validate required fields
        if not message or not agents:
            await websocket.send_json({"type": "error", "error": "Missing required fields: 'message' and 'agents' are required."})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            ws_manager.disconnect(user_id, conv_id)
            return

        # Log the arguments passed to the workflow
        logger.info(f"Starting hybrid orchestration via WebSocket: message={message}, agents={agents}, model_id={model_id}, temperature={temperature}, max_rounds={max_rounds}, orchestration_type={orchestration_type}, use_mcp_tools={use_mcp_tools}, history={history}")

        # Get the FastAPI app instance
        app = websocket.app if hasattr(websocket, 'app') else None

        # Start the hybrid orchestration workflow (streaming enabled)
        await run_hybrid_orchestration_workflow(
            query=message,
            user=current_user,
            db=db,
            agents=agents,
            conversation_id=conv_id,
            app=app,
            history=history,
            model_id=model_id,
            temperature=temperature,
            max_rounds=max_rounds,
            orchestration_type=orchestration_type,
            use_mcp_tools=use_mcp_tools,
            stream=True
        )

        # After workflow completes, close the connection
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
        ws_manager.disconnect(user_id, conv_id)
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, conv_id)
        logger.info(f"WebSocket client disconnected: user={user_id}, conversation={conv_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except:
            pass
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        ws_manager.disconnect(user_id, conv_id) 