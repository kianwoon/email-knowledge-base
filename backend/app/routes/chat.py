from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import logging
import asyncio
import httpx
import json
import uuid
import os

# Import the RAG function
from app.services.llm import generate_openai_rag_response, get_rate_card_response_advanced
# Import authentication dependency and User model
from app.dependencies.auth import get_current_active_user_or_token_owner
from app.models.user import User
from app.db.session import get_db

# --- ADDED IMPORTS ---
from app.crud import crud_jarvis_token
from app.services.encryption_service import decrypt_token
from app.models.jarvis_token import JarvisExternalToken
from app.config import settings
from app.crud import mcp_tool_crud  # Import the MCP tool CRUD operations
from app.services.tool_executor import execute_tool  # Import the tool executor
# --- END ADDED IMPORTS ---

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter()

# --- BEGIN NEW/MODIFIED PYDANTIC MODELS ---

# For tool_results in the request
class ToolResult(BaseModel):
    call_id: str
    name: str # ADDED: Name of the function that was called
    result: Any # Can be complex JSON from the tool

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict[str, str]]] = None
    model_id: Optional[str] = None
    # New field for Phase 3
    tool_results: Optional[List[ToolResult]] = None

# For tool_calls in the Phase 1 response
class ToolCall(BaseModel):
    call_id: str
    name: str
    arguments: Dict[str, Any]

class ChatPhase1ResponsePayload(BaseModel):
    type: str # 'text' or 'tool_call'
    reply: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None

# Phase 3 response is always text
class ChatPhase3ResponsePayload(BaseModel):
    type: str = Field(default='text') # Should always be 'text'
    reply: str

# --- END NEW/MODIFIED PYDANTIC MODELS ---

# --- MANIFEST LOADING (Placeholder) ---
TOOL_MANIFEST: Optional[Dict[str, Any]] = None

import os
# __file__ is backend/app/routes/chat.py
# manifest.json is in backend/manifest.json
# So we need to go up three levels from chat.py directory (routes -> app -> backend)
APP_DIR = os.path.dirname(os.path.abspath(__file__)) # .../backend/app/routes
BACKEND_APP_DIR = os.path.dirname(APP_DIR) # .../backend/app
BACKEND_DIR_ROOT = os.path.dirname(BACKEND_APP_DIR) # .../backend
MANIFEST_PATH = os.path.join(BACKEND_DIR_ROOT, "manifest.json")

def load_tool_manifest(user_email: Optional[str] = None, db_session: Optional[Session] = None):
    """Load tool manifest from manifest.json and merge with user-defined MCP tools if user_email and db_session are provided."""
    global TOOL_MANIFEST
    static_tools = []
    
    # Load static tools from manifest.json
    try:
        with open(MANIFEST_PATH, 'r') as f:
            manifest_data = json.load(f)
            static_tools = manifest_data.get("tools", [])
        logger.info(f"Successfully loaded {len(static_tools)} static tools from {MANIFEST_PATH}")
    except Exception as e:
        logger.error(f"Failed to load tool manifest from {MANIFEST_PATH}: {e}", exc_info=True)
        static_tools = []  # Default to empty tools if load fails
    
    # If user_email and db_session are provided, merge with user-defined tools
    user_tools = []
    if user_email and db_session:
        try:
            # Get all enabled MCP tools for the user
            db_tools = mcp_tool_crud.get_mcp_tools(db_session, user_email)
            user_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "entrypoint": tool.entrypoint,  # Save the entrypoint for execution
                    "version": tool.version,
                    "is_custom": True  # Flag to identify user-defined tools
                }
                for tool in db_tools if tool.enabled  # Only include enabled tools
            ]
            logger.info(f"Successfully loaded {len(user_tools)} user-defined MCP tools for user {user_email}")
        except Exception as e:
            logger.error(f"Failed to load user-defined MCP tools for user {user_email}: {e}", exc_info=True)
    
    # Combine static and user tools
    all_tools = static_tools + user_tools
    
    # Update the global manifest
    TOOL_MANIFEST = {"tools": all_tools}
    logger.info(f"Total tools available: {len(all_tools)} (Static: {len(static_tools)}, User-defined: {len(user_tools)})")
    
    return TOOL_MANIFEST

# Call it once on startup (FastAPI specific way would be in startup event)
# For now, this will load it on first access or ensure it's loaded.
# A more robust solution would use FastAPI's @app.on_event("startup")
# load_tool_manifest() # We'll call this at the start of the endpoint for now.

# --- END MANIFEST LOADING ---

# --- ADDED HELPER FUNCTION for External Search ---
async def search_external_knowledge(token_record: JarvisExternalToken, query: str, request: Request) -> List[Dict]:
    """Performs a search using a single external token."""
    try:
        decrypted_token = decrypt_token(token_record.encrypted_token_value)
    except Exception as e:
        logger.error(f"Failed to decrypt external token ID {token_record.id} for user {token_record.user_id}: {e}")
        # TODO: Consider marking token as invalid in DB after several failures
        return [] # Return empty list on decryption failure

    search_endpoint = request.url_for('search_shared_knowledge') # Use FastAPI's reverse routing
    # Fallback if reverse routing fails (e.g., testing)
    if not search_endpoint:
         search_endpoint = f"/api/v1/shared-knowledge/search" # Adjust if your base path differs
         logger.warning(f"Could not reverse route 'search_shared_knowledge', using hardcoded path: {search_endpoint}")
    
    # Construct absolute URL for the internal request
    base_url = str(request.base_url) # e.g., http://localhost:8000/
    target_url = f"{base_url.rstrip('/')}{search_endpoint}"
    
    headers = {
        "Authorization": f"Bearer {decrypted_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"query": query, "limit": 5} # Limit external results for performance
    
    logger.debug(f"External search: User={token_record.user_id}, TokenID={token_record.id}, Nickname='{token_record.token_nickname}', URL={target_url}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client: # Use httpx for async requests
            response = await client.post(target_url, headers=headers, json=payload)
        
        response.raise_for_status() # Raise exception for 4xx/5xx errors
        results = response.json()
        logger.info(f"External search success: User={token_record.user_id}, TokenID={token_record.id}, ResultsCount={len(results)}")
        # Add source info to results
        for result in results:
             result['_source_nickname'] = token_record.token_nickname
        return results
    except httpx.HTTPStatusError as e:
        logger.error(f"External search failed (HTTP {e.response.status_code}): TokenID={token_record.id}, Nickname='{token_record.token_nickname}', URL={target_url}, Response: {e.response.text}")
        # TODO: Handle specific errors (401/403 might mean token is invalid)
        if e.response.status_code in [401, 403]:
            # Mark token as invalid? Needs DB access - complex here, maybe handle later.
            pass
        return []
    except Exception as e:
        logger.error(f"External search failed (General Error): TokenID={token_record.id}, Nickname='{token_record.token_nickname}', URL={target_url}, Error: {e}", exc_info=True)
        return []
# --- END HELPER FUNCTION ---

@router.post("/", response_model=None) # response_model will be dynamic. FastAPI will infer from return type annotation.
async def chat_endpoint(
    chat_message: ChatRequest,
    request: Request, 
    # response: Response, # FastAPI can infer status codes for different return types too.
    current_user: User = Depends(get_current_active_user_or_token_owner),
    db: Session = Depends(get_db)
) -> ChatPhase1ResponsePayload | ChatPhase3ResponsePayload: # Union for multiple response types
    """Chat endpoint for processing user messages, handling tool calls, and generating responses."""
    logger.info(f"Received chat request from user: {current_user.email}. Message: \"{chat_message.message}\". Tool results provided: {chat_message.tool_results is not None}")

    # Load tools (manifest) with user-defined tools
    tools_config = load_tool_manifest(current_user.email, db)
    # Ensure tools_config has a 'tools' key, even if empty from load_tool_manifest error handling
    available_tools = tools_config.get("tools", [])
    logger.info(f"Loaded {len(available_tools)} available tools for user {current_user.email}")

    # --- Phase 3: Final Response Generation (if tool_results are provided) ---
    if chat_message.tool_results:
        logger.info(f"[Phase 3] Processing tool results for user: {current_user.email}")
        try:
            # Placeholder: This function would take the original message, history, and tool_results
            # and call the LLM to synthesize a final natural language response.
            # It needs to be adapted or created in app.services.llm
            final_reply_content = await generate_openai_rag_response(
                message=chat_message.message, # Original message
                chat_history=chat_message.chat_history or [],
                user=current_user,
                db=db,
                model_id=chat_message.model_id,
                # NEW: Pass tool_results for synthesis
                tool_results=chat_message.tool_results 
            )

            if final_reply_content is None:
                logger.error(f"[Phase 3] LLM synthesis returned None for user {current_user.email}")
                final_reply_content = "I encountered an issue synthesizing the information from the tools. Please try again."
            
            return ChatPhase3ResponsePayload(reply=final_reply_content)
        
        except Exception as e:
            logger.error(f"[Phase 3] Error during final response synthesis for user {current_user.email}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error occurred while generating the final response.")

    # --- Phase 1: Tool Call Decision (if no tool_results) ---
    logger.info(f"[Phase 1] Deciding on tool call for user: {current_user.email}")
    
    # --- Existing External Knowledge Fetch (pre-LLM context gathering) --- 
    all_external_results_text_context = ""
    # This part remains largely the same as before, gathering context for the LLM
    try:
        valid_external_tokens = crud_jarvis_token.get_valid_tokens_for_user(db=db, user_id=current_user.id)
        if valid_external_tokens:
            external_search_tasks = [search_external_knowledge(token, chat_message.message, request) for token in valid_external_tokens]
            if external_search_tasks:
                results_list = await asyncio.gather(*external_search_tasks)
                all_external_results = [item for sublist in results_list for item in sublist]
                if all_external_results:
                    combined_context_text = "\n\n---\\nAdditional Context from Shared Knowledge:\n"
                    for result in all_external_results[:3]: # Limit context
                        source = result.get('_source_nickname', 'Unknown Source')
                        content = result.get('metadata', {}).get('raw_text', '[No text content]')
                        combined_context_text += f"\nSource: {source}\nContent: {content}\n---\n"
                    all_external_results_text_context = combined_context_text
                    logger.info(f"[Phase 1] Prepared external knowledge context for user {current_user.email}.")
    except Exception as e:
        logger.error(f"[Phase 1] Error during external knowledge processing for user {current_user.email}: {e}", exc_info=True)
        # Non-critical, proceed without this context if it fails

    message_for_llm = chat_message.message
    if all_external_results_text_context:
        message_for_llm += all_external_results_text_context

    try:
        # Placeholder: This function (or a new one) needs to be adapted in app.services.llm
        # to accept the 'available_tools' and make a tool decision.
        # The LLM provider (e.g., OpenAI) will return a specific structure if it decides to use a tool.
        llm_response_data = await generate_openai_rag_response(
            message=message_for_llm, # Message potentially augmented with external context
            chat_history=chat_message.chat_history or [],
            user=current_user,
            db=db,
            model_id=chat_message.model_id,
            ms_token=current_user.ms_access_token, # Assuming this is still relevant
            # NEW: Pass available tools for the LLM to choose from
            available_tools=available_tools 
        )

        if llm_response_data is None:
            logger.error(f"[Phase 1] LLM tool decision returned None for user {current_user.email}")
            # Fallback to a simple text response if LLM fails to give structured output or text
            return ChatPhase1ResponsePayload(type="text", reply="I had trouble understanding that. Could you try rephrasing?")

        # --- PARSING LLM RESPONSE FOR TOOL CALLS OR TEXT REPLY --- 
        # This parsing logic is HIGHLY DEPENDENT on how your LLM service (e.g., OpenAI)
        # returns tool call requests vs. direct text replies. The example below is a common pattern.

        # Example: Check if llm_response_data contains tool_calls (OpenAI style)
        # Real implementation would parse `llm_response_data.choices[0].message.tool_calls` for OpenAI
        # or similar structure for other LLMs.
        # For this placeholder, we assume llm_response_data MIGHT be a dict with 'tool_calls' or 'text_reply'
        
        parsed_tool_calls_for_frontend = [] # Renamed to avoid confusion with llm.py's variable
        if isinstance(llm_response_data, dict) and llm_response_data.get('type') == 'tool_call' and llm_response_data.get('tool_calls'):
            # Extract tool calls from the LLM response
            tool_calls_from_llm = llm_response_data.get('tool_calls', [])
            
            # Find the tool metadata for each tool call
            for tc in tool_calls_from_llm:
                call_id = tc.get('call_id') or str(uuid.uuid4())  # Generate ID if none provided
                tool_name = tc.get('name')
                
                # Parse arguments if they're a string (JSON)
                tool_args = tc.get('arguments', {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tool arguments JSON: {e}")
                        tool_args = {}  # Default to empty dict if parsing fails
                
                # Find the tool metadata from available_tools
                tool_metadata = next((tool for tool in available_tools if tool['name'] == tool_name), None)
                
                # Add to the list for the frontend response
                parsed_tool_calls_for_frontend.append(
                    ToolCall(
                        call_id=call_id,
                        name=tool_name,
                        arguments=tool_args
                    )
                )
                
                # Log what tool we're executing
                if tool_metadata:
                    is_custom = tool_metadata.get('is_custom', False)
                    entrypoint = tool_metadata.get('entrypoint', 'unknown')
                    logger.info(f"[Phase 1] Tool call for {tool_name} (Custom: {is_custom}, Entrypoint: {entrypoint})")
                else:
                    logger.warning(f"[Phase 1] Tool call for unknown tool: {tool_name}")
                
            # Return the tool calls to the frontend
            return ChatPhase1ResponsePayload(
                type="tool_call",
                tool_calls=parsed_tool_calls_for_frontend
            )
        else:
            # Assume it's a direct text reply if no valid tool calls were parsed.
            # If llm_response_data was a string, use it. If dict, try to find a reply field.
            text_reply = ""
            if isinstance(llm_response_data, str):
                text_reply = llm_response_data
            elif isinstance(llm_response_data, dict):
                # Adjust this key based on actual LLM response structure for direct replies
                text_reply = llm_response_data.get('reply', llm_response_data.get('text', "I'm not sure how to respond to that.")) 
            else:
                text_reply = "I received an unexpected response format from the AI."
            
            logger.info(f"[Phase 1] LLM provided direct text reply for user {current_user.email}")
            return ChatPhase1ResponsePayload(type="text", reply=text_reply)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"[Phase 1] Error during tool decision/RAG for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your request.") 