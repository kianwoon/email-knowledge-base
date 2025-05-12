import logging
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI, RateLimitError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User
from app.crud import api_key_crud
from app.utils.security import decrypt_token
from app.services.milvus import get_milvus_context, count_tokens, truncate_text_by_tokens
from app.rag.email_rag import extract_email_search_parameters_for_iceberg, get_email_context
from app.rag.ratecard_rag import get_rate_card_response_advanced

# Set up logger for this module
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

def _build_system_prompt() -> str:
    """Builds the default system prompt for RAG responses."""
    return "You are a helpful AI assistant. Your user is asking a question.\n" \
           "You have been provided with some context information (RAG Context) that might be relevant to the user's query.\n" \
           "Please use this context to answer the user's question accurately and comprehensively, including relevant details from the context.\n" \
           "When referencing dates from emails or documents, always maintain the EXACT years as they appear in the source material.\n" \
           "Do NOT change years or assume current year. For example, if an email from 2023 is referenced, use '2023' not the current year.\n" \
           "For relative time expressions like 'last week', use the actual date range with correct years from the retrieved information.\n" \
           "If the context mentions multiple entities, projects, or clients (e.g., UOB, OCBC), be meticulous in attributing specific details only to the entity they are explicitly linked with in the source text. Avoid generalizing details from one entity to another unless the text explicitly supports it.\\n" \
           "If the context doesn't provide enough information, state that you couldn't find the answer in the provided documents or emails.\\n" \
           "Do not make up information.\n\n" \
           "<RAG_CONTEXT_PLACEHOLDER>"

def _format_chat_history(
    chat_history: List[Dict[str, str]], 
    model: str = "gpt-4", # Default model for token counting
    max_tokens: Optional[int] = None
) -> str:
    """Formats chat history into a string, optionally truncating by tokens."""
    if not chat_history:
        return ""

    formatted_history_parts = []
    for entry in chat_history:
        role = entry.get("role", "user") # Default to user if role is missing
        content = entry.get("content", "")
        formatted_history_parts.append(f"{role.capitalize()}: {content}")
    
    full_history_str = "\n".join(formatted_history_parts)

    if max_tokens is not None:
        current_tokens = count_tokens(full_history_str, model)
        if current_tokens > max_tokens:
            logger.warning(f"Chat history ({current_tokens} tokens) exceeds max_tokens ({max_tokens}). Truncating.")
            # For simplicity, this example truncates from the beginning of the history.
            # More sophisticated truncation (e.g., keeping recent messages) might be needed.
            truncated_history = truncate_text_by_tokens(full_history_str, model, max_tokens)
            return truncated_history
            
    return full_history_str

async def call_jarvis_router(message: str, client: AsyncOpenAI, model: str, available_tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Calls an LLM to classify the user message into a target category (mcp, iceberg, milvus)."""
    
    # Build MCP tools details if provided
    mcp_tools_details = ""
    if available_tools and len(available_tools) > 0:
        mcp_tools_details = "Available MCP tools:\n"
        for tool in available_tools:
            tool_name = tool.get("name", "")
            tool_desc = tool.get("description", "No description")
            mcp_tools_details += f"  - {tool_name}: {tool_desc}\n"
    
    system_prompt = (
        "You are Jarvis-Router. Classify the user message into one of the following categories:\n"
        "  1) mcp – user wants to interact with external systems or APIs (e.g., list/get/create/update Jira issues, schedule events & calendar, send emails, etc.).\n"
        "  2) iceberg – user wants operational data like emails, or information about jobs, tables, metrics, or day-to-day activities.\n"
        "  3) milvus – user is asking a knowledge question, seeking information from documents, or wants a rate card.\n"
        f"{mcp_tools_details}\n"
        "Analyze the user's message and respond with a single JSON object. "
        "The JSON object must have two keys: 'target' (string, one of ['mcp', 'iceberg', 'milvus', 'multi']) "
        "and 'confidence' (float, 0.0 to 1.0). Example JSON response: { \"target\": \"milvus\", \"confidence\": 0.85 }"
    )
    
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    router_output_str = ""
    try:
        logger.info(f"[call_jarvis_router] Calling LLM for routing. Message: '{message[:100]}...'")
        response = await client.chat.completions.create(
            model=model,
            messages=prompt_messages,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        router_output_str = response.choices[0].message.content
        logger.info(f"[call_jarvis_router] Raw LLM output: {router_output_str}")
        router_decision = json.loads(router_output_str)
        
        if not isinstance(router_decision, dict) or not all(k in router_decision for k in ['target', 'confidence']):
            logger.error(f"[call_jarvis_router] Invalid JSON structure from router LLM: {router_decision}. Missing keys or not a dict.")
            return {"target": "milvus", "confidence": 0.5, "error": "Invalid router response structure"}
        
        target = router_decision.get('target')
        if target not in ['mcp', 'iceberg', 'milvus', 'multi']:
            logger.warning(f"[call_jarvis_router] Router LLM returned unknown target: {target}. Defaulting to milvus.")
            router_decision['target'] = 'milvus' # Correct the target in the decision object
        
        # Ensure confidence is a float
        try:
            router_decision['confidence'] = float(router_decision.get('confidence', 0.5))
        except (ValueError, TypeError):
            logger.warning(f"[call_jarvis_router] Router LLM returned invalid confidence: {router_decision.get('confidence')}. Defaulting to 0.5.")
            router_decision['confidence'] = 0.5
            
        return router_decision
    except json.JSONDecodeError as e:
        logger.error(f"[call_jarvis_router] Failed to parse JSON from router LLM: {e}. Raw: {router_output_str}")
        return {"target": "milvus", "confidence": 0.5, "error": "JSON decode error from router"}
    except Exception as e:
        logger.error(f"[call_jarvis_router] Error: {e}", exc_info=True)
        return {"target": "milvus", "confidence": 0.5, "error": str(e)}

async def synthesize_answer_from_context(
    original_query: str, 
    retrieved_items: List[Dict[str, Any]], 
    context_description: str, 
    client: AsyncOpenAI, 
    model: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """Generates a natural language answer based on retrieved items and original query."""
    if not retrieved_items:
        return f"I couldn't find any specific information about '{original_query}' in the {context_description}."

    # Get current date in Singapore timezone for context
    singapore_tz = ZoneInfo("Asia/Singapore")
    now_sg = datetime.now(singapore_tz)
    today_sg_date = now_sg.strftime('%Y-%m-%d')
    today_sg_weekday = now_sg.strftime('%A')
    
    # Log the date we're using
    logger.info(f"[synthesize_answer_from_context] Using today's date (Singapore): {today_sg_date} ({today_sg_weekday})")

    context_str = ""
    # MODIFIED: Process more items (e.g., up to 6 or all if count is low)
    items_to_process = retrieved_items[:max(6, len(retrieved_items))] 

    logger.info(f"[synthesize_answer_from_context] Processing {len(items_to_process)} items for synthesis.")

    # HTML stripping function
    def strip_html_tags(text: str) -> str:
        """Strips HTML tags from text content."""
        if not text:
            return ""
        
        # Handle common HTML entity characters
        entity_replacements = {
            "&lt;": "<", "&gt;": ">", "&amp;": "&", 
            "&quot;": '"', "&apos;": "'", "&nbsp;": " "
        }
        for entity, replacement in entity_replacements.items():
            text = text.replace(entity, replacement)
        
        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    for i, item in enumerate(items_to_process):
        content_to_display = "[No clear textual content extracted for this item]" # Default message
        text_parts = []

        # Prioritize schema fields for plain text
        # Based on schema: body_text for full_message, quoted_raw_text for quoted_message
        granularity = item.get('granularity')
        
        primary_text = None
        if granularity == 'full_message' and isinstance(item.get('body_text'), str):
            primary_text = item['body_text']
            logger.debug(f"Item {i+1} (full_message) using body_text. Length: {len(primary_text) if primary_text else 0}")
        elif granularity == 'quoted_message' and isinstance(item.get('quoted_raw_text'), str):
            primary_text = item['quoted_raw_text']
            logger.debug(f"Item {i+1} (quoted_message) using quoted_raw_text. Length: {len(primary_text) if primary_text else 0}")
        elif isinstance(item.get('body_text'), str): # Fallback if granularity is missing but body_text exists
            primary_text = item['body_text']
            logger.debug(f"Item {i+1} (no/unclear granularity) using fallback body_text. Length: {len(primary_text) if primary_text else 0}")
        elif isinstance(item.get('content'), str): # Generic content field
            primary_text = item['content']
            logger.debug(f"Item {i+1} using generic 'content' field. Length: {len(primary_text) if primary_text else 0}")
        elif isinstance(item.get('summary'), str):
            primary_text = item['summary']
            logger.debug(f"Item {i+1} using 'summary' field. Length: {len(primary_text) if primary_text else 0}")

        if primary_text:
            # Check for HTML content and strip it if detected
            if "<html" in primary_text.lower() or "<body" in primary_text.lower() or "<div" in primary_text.lower() or \
               "&lt;div" in primary_text.lower() or "<!--" in primary_text or "@font-face" in primary_text:
                original_length = len(primary_text)
                primary_text = strip_html_tags(primary_text)
                logger.info(f"Item {i+1} contained HTML that was stripped. Original size: {original_length}, New size: {len(primary_text)}")
            text_parts.append(primary_text)
        
        # Add subject if not already in primary text and seems relevant
        subject = item.get('subject')
        if isinstance(subject, str) and subject:
            if not primary_text or subject.lower() not in primary_text.lower():
                text_parts.insert(0, f"Subject: {subject}") # Prepend subject
        
        if text_parts:
            content_to_display = "\n".join(text_parts)
        else:
            # Fallback if no primary text fields were found or were not strings
            simple_parts = []
            if isinstance(item, dict):
                for k, v in item.items():
                    if k not in ['body_text', 'quoted_raw_text', 'content', 'summary'] and isinstance(v, (str, int, float, bool)):
                        simple_parts.append(f"{k}: {v}")
            if simple_parts:
                content_to_display = "; ".join(simple_parts)
                logger.debug(f"Item {i+1} using fallback simple parts string: {content_to_display[:200]}")
            else:
                logger.debug(f"Item {i+1} truly has no displayable textual content based on checks.")

        item_content_for_llm = str(content_to_display)[:1500] # Increased truncation limit slightly
        context_str += f"--- Email {i+1} ---\nFrom: {item.get('sender_name') or item.get('sender', 'Unknown Sender')}\nDate: {item.get('received_datetime_utc', 'Unknown Date')}\n{item_content_for_llm}\n---\n"
    
    system_prompt = (
        f"You are an AI assistant. The user asked the following query: '{original_query}'.\n"
        f"IMPORTANT: Today's date is {today_sg_date} ({today_sg_weekday}) in Singapore timezone.\n"
        f"Based SOLELY on the following extracted context from '{context_description}', provide a comprehensive answer to the user's query. "
        f"If the context directly answers the query, provide that answer. "
        f"If the context is relevant but doesn't fully answer, explain what you found and what might be missing. "
        f"If the context doesn't seem to contain relevant information, clearly state that. Do not make up information or answer outside the provided context.\n"
        f"When referring to dates in your response, please be accurate and specific. Today means {today_sg_date}, yesterday means the day before, and so on. "
        f"Do NOT confuse today's date when answering queries about meetings or events."
    )
    
    messages_for_synthesis = [
        {"role": "system", "content": system_prompt}
    ]
    # Add chat history if available, before the current query and context
    if chat_history:
        for entry in chat_history:
            messages_for_synthesis.append({"role": entry["role"], "content": entry["content"]})
    
    # The user's current query that led to this synthesis, plus the context found.
    # Framing it as user providing the context they found regarding their query.
    messages_for_synthesis.append({"role": "user", "content": f"""Regarding my query ('{original_query}'), I found this information:

{context_str}
Please provide an answer based on this. Remember that today is {today_sg_date} ({today_sg_weekday})."""})
    
    try:
        logger.info(f"[synthesize_answer_from_context] Synthesizing for query: '{original_query[:50]}...' from {context_description}")
        response = await client.chat.completions.create(
            model=model,
            messages=messages_for_synthesis,
            temperature=0.1, # Lower temperature for factual synthesis
            max_tokens=1024  # Allow a reasonable length for the synthesized answer
        )
        synthesized_reply = response.choices[0].message.content.strip()
        return synthesized_reply
    except Exception as e:
        logger.error(f"[synthesize_answer_from_context] Error during synthesis: {e}", exc_info=True)
        return f"I found some information from {context_description} regarding '{original_query}', but encountered an issue while trying to formulate a final answer."

async def generate_openai_rag_response(
    message: str,
    chat_history: List[Dict[str, str]],
    user: User,
    db: Session,
    model_id: Optional[str] = None,
    ms_token: Optional[str] = None, 
    available_tools: Optional[List[Dict[str, Any]]] = None, 
    tool_results: Optional[List[Dict[str, Any]]] = None    
) -> str | Dict[str, Any]: 
    """Generates a chat response using RAG, potentially with tool calling.
    Handles Phase 1 (tool decision), Phase 3 (synthesis), or standard RAG.
    """
    logger.debug(f"RAG/ToolCall Entry: user={user.email}, msg='{message[:50]}...', tools_provided={available_tools is not None}, results_provided={tool_results is not None}")
    fallback_response = "I apologize, but I encountered an unexpected error. Please try again later."
    
    # Client setup (common for all phases)
    try:
        chat_model = model_id or settings.OPENAI_MODEL_NAME
        provider = "deepseek" if chat_model.lower().startswith("deepseek") else "openai"
        db_api_key = api_key_crud.get_api_key(db, user.email, provider)
        if not db_api_key:
            logger.warning(f"User {user.email} missing active {provider} key for RAG/ToolCall.")
            if available_tools and not tool_results: # Phase 1 expecting dict
                 return {"type": "error", "message": f"{provider.capitalize()} API key required."} # Consistent error dict
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider.capitalize()} API key required.")
        
        user_api_key = decrypt_token(db_api_key.encrypted_key)
        if not user_api_key:
            logger.error(f"Failed to decrypt {provider} API key for {user.email}.")
            if available_tools and not tool_results: # Phase 1 expecting dict
                return {"type": "error", "message": "Could not decrypt API key."} # Consistent error dict
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not decrypt API key.")

        provider_timeout = 30.0
        if hasattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS") and getattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS"):
            try:
                provider_timeout = float(getattr(settings, f"{provider.upper()}_TIMEOUT_SECONDS"))
            except (ValueError, TypeError):
                logger.warning(f"Invalid timeout for {provider.upper()}_TIMEOUT_SECONDS. Using default: 30.0s")
        
        client_kwargs = {"api_key": user_api_key, "timeout": provider_timeout}
        if db_api_key.model_base_url:
            client_kwargs["base_url"] = db_api_key.model_base_url
        user_client = AsyncOpenAI(**client_kwargs)

    except HTTPException as http_setup_exc:
        logger.error(f"RAG/ToolCall: HTTPException during setup: {http_setup_exc.detail}")
        if available_tools and not tool_results:
            return {"type": "error", "message": f"Setup error: {http_setup_exc.detail}"}
        raise http_setup_exc
    except Exception as setup_err:
        logger.error(f"RAG/ToolCall: Error during setup: {setup_err}", exc_info=True)
        if available_tools and not tool_results:
            return {"type": "error", "message": "Internal setup error for LLM interaction."}
        return fallback_response

    # --- Phase 3: Final Response Synthesis --- 
    if tool_results: # tool_results is List[ToolResult], where ToolResult has call_id, name, result
        logger.info(f"[Phase 3 LLM] Synthesizing response from {len(tool_results)} tool result(s) for user {user.email}")
        try:
            system_prompt_phase3 = (
                "You are an AI assistant. You previously decided to call tools to answer the user's query. "
                "Now you have the results from those tools. Synthesize these results into a final, user-friendly, natural language response. "
                "Address the user's original query based *only* on the information provided in the tool results. "
                "Do not refer to the fact that you used tools unless it's natural to the conversation. "
                "If a tool returned an error or no useful information, acknowledge that if necessary and respond as best as you can with other information."
            )
            messages_for_synthesis = [{"role": "system", "content": system_prompt_phase3}]
            
            if chat_history: # Original history before tool calls
                for entry in chat_history:
                    messages_for_synthesis.append({"role": entry["role"], "content": entry["content"]})
            messages_for_synthesis.append({"role": "user", "content": message}) # Original user message that triggered tools

            # Construct the assistant message that *would have made* these tool calls
            assistant_tool_call_objects = []
            if tool_results: # Ensure tool_results is not None and is iterable
                for res in tool_results: # res is a ToolResult model instance
                    assistant_tool_call_objects.append({
                        "id": res.call_id, 
                        "type": "function",
                        "function": {
                            "name": res.name, 
                            "arguments": "{}" # Placeholder: Original arguments not critical for linking if id/name match.
                        }
                    })
            
            if assistant_tool_call_objects:
                messages_for_synthesis.append({
                    "role": "assistant",
                    "content": None, 
                    "tool_calls": assistant_tool_call_objects
                })
                logger.info(f"[Phase 3 LLM] Added reconstructed assistant message with {len(assistant_tool_call_objects)} tool_calls.")

            # Now add the actual tool results (role: tool)
            if tool_results: # Ensure tool_results is not None and is iterable
                for res in tool_results: 
                    current_tool_result_data = res.result 
                    current_tool_call_id = res.call_id
                    current_tool_name = res.name

                    tool_output_content = ""
                    if isinstance(current_tool_result_data, dict) and current_tool_result_data.get('error'):
                        tool_output_content = json.dumps({"error": current_tool_result_data['error'], "message": "Tool execution failed."})
                    else:
                        tool_output_content = str(current_tool_result_data)

                    messages_for_synthesis.append({
                        "tool_call_id": current_tool_call_id,
                        "role": "tool",
                        "name": current_tool_name, 
                        "content": tool_output_content,
                    })
            
            logger.debug(f"[Phase 3 LLM] Final messages for synthesis count: {len(messages_for_synthesis)}. Content (first 2): {json.dumps(messages_for_synthesis[:2], indent=2)}")
            if len(messages_for_synthesis) > 2 : logger.debug(f"[Phase 3 LLM] Assistant tool_calls reconstruction (if any): {json.dumps(messages_for_synthesis[2], indent=2) if messages_for_synthesis[2]['role']=='assistant' else 'No assistant reconstruction'}")
            if len(messages_for_synthesis) > 3 : logger.debug(f"[Phase 3 LLM] First tool result message (if any): {json.dumps(messages_for_synthesis[3], indent=2) if messages_for_synthesis[3]['role']=='tool' else 'No tool message'}")

            response = await user_client.chat.completions.create(
                model=chat_model, messages=messages_for_synthesis, temperature=0.1
            )
            final_text_reply = response.choices[0].message.content.strip()
            logger.info(f"[Phase 3 LLM] Synthesis successful. Reply: {final_text_reply[:100]}...")
            return final_text_reply
        except Exception as e_synth:
            logger.error(f"[Phase 3 LLM] Error during synthesis: {e_synth}", exc_info=True)
            return "I tried to process the information from the tools, but encountered an issue."

    # --- Phase 1: Tool Call Decision or Routed Internal Query --- 
    elif available_tools: # available_tools are the MCP tools from manifest.json
        logger.info(f"[Phase 1 Router] Attempting to route message for user {user.email}. MCP tools available: {[t.get('name') for t in available_tools]}")
        
        # 1. Call Jarvis-Router to classify the query
        router_decision = await call_jarvis_router(message, user_client, chat_model, available_tools)
        target = router_decision.get('target')
        confidence = router_decision.get('confidence', 0.0)
        logger.info(f"[Phase 1 Router] Jarvis-Router decision: Target='{target}', Confidence={confidence:.2f}")

        # Low confidence threshold - adjust as needed
        LOW_CONFIDENCE_THRESHOLD = 0.88 

        if router_decision.get("error"):
            logger.error(f"[Phase 1 Router] Jarvis-Router returned an error: {router_decision.get('error')}. Defaulting to direct LLM reply attempt.")
            target = "direct_llm_fallback" # Special target to signify direct reply without tools/internal RAG

        # Decision logic based on router target
        if target == 'mcp' and confidence >= LOW_CONFIDENCE_THRESHOLD:
            logger.info(f"[Phase 1 Router] Target is 'mcp'. Proceeding with MCP tool decision.")
            try:
                # Build a more structured and detailed description of available tools
                tool_descriptions = ""
                if available_tools:
                    for tool in available_tools:
                        tool_name = tool.get("name", "unknown_tool")
                        tool_desc = tool.get("description", "No description available")
                        user_defined = "User-defined" if tool.get("user_defined", False) else "System"
                        tool_descriptions += f"\n- {tool_name}: {tool_desc} ({user_defined})"
                
                # This is the existing logic for when LLM decides on an MCP tool or direct answer
                system_prompt_mcp = (
                    "You are an AI assistant. Based on the user's query, "
                    "decide if calling one of the available external tools (MCP tools) would be beneficial. "
                    f"The following tools are available:{tool_descriptions}\n\n"
                    "If calling a tool would help answer the query, choose the appropriate tool(s) and provide arguments. "
                    "Otherwise, answer directly without using these tools. "
                    "Be specific when deciding to use a tool - only use tools when they directly apply to the user's request."
                )
                messages_for_mcp_decision = [{"role": "system", "content": system_prompt_mcp}]
                if chat_history:
                    for entry in chat_history: messages_for_mcp_decision.append({"role": entry["role"], "content": entry["content"]})
                messages_for_mcp_decision.append({"role": "user", "content": message})

                # available_tools are already formatted for OpenAI in routes/chat.py, but llm.py receives the raw manifest list
                formatted_mcp_tools_for_llm = [{"type": "function", "function": tool_def} for tool_def in available_tools]

                response = await user_client.chat.completions.create(
                    model=chat_model, messages=messages_for_mcp_decision,
                    tools=formatted_mcp_tools_for_llm, tool_choice="auto", temperature=0.1
                )
                response_message = response.choices[0].message

                if response_message.tool_calls:
                    logger.info(f"[Phase 1 MCP] LLM decided to call MCP tools: {response_message.tool_calls}")
                    parsed_mcp_tool_calls = [
                        {"call_id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                        for tc in response_message.tool_calls
                    ]
                    return {"type": "tool_call", "tool_calls": parsed_mcp_tool_calls}
                else:
                    direct_reply = response_message.content.strip() if response_message.content else "I'm not sure how to help with that specific request using my current tools."
                    logger.info(f"[Phase 1 MCP] LLM decided to reply directly (no MCP tool): {direct_reply[:100]}...")
                    return {"type": "text", "reply": direct_reply }
            except Exception as e_mcp:
                logger.error(f"[Phase 1 MCP] Error during MCP tool decision: {e_mcp}", exc_info=True)
                return {"type": "text", "reply": "I had trouble processing your request for external tools."}

        elif target == 'iceberg' and confidence >= LOW_CONFIDENCE_THRESHOLD:
            logger.info(f"[Phase 1 Router] Target is 'iceberg'. Querying Iceberg (emails/operational data).")
            try:
                # Use the email_rag module's parameter extraction
                logger.info(f"[Phase 1 Iceberg] Calling LLM to extract structured parameters for query: '{message}'")
                extracted_iceberg_params = await extract_email_search_parameters_for_iceberg(message, user_client, chat_model)
                
                if not extracted_iceberg_params: # Check if extraction failed and returned empty dict
                    logger.warning("[Phase 1 Iceberg] Parameter extraction failed or returned empty. Using broad search terms as fallback.")
                    extracted_iceberg_params = {"search_terms": [message]} # Fallback to raw message
                else:
                    logger.info(f"[Phase 1 Iceberg] Extracted parameters for Iceberg query: {extracted_iceberg_params}")

                iceberg_results = await get_email_context(
                    max_items=getattr(settings, "MAX_EMAIL_CONTEXT_ITEMS_BROAD", 10),
                    max_chunk_chars=8000,
                    user_client=user_client,
                    search_params=extracted_iceberg_params,
                    user_email=user.email
                )
                
                # ADDED: Log details of retrieved Iceberg results
                if iceberg_results:
                    logger.info(f"[Phase 1 Iceberg] Retrieved {len(iceberg_results)} emails from Iceberg. Details (up to 10):")
                    for i, email_res in enumerate(iceberg_results[:10]):
                        logger.info(f"  Email {i+1}: ID={email_res.get('message_id')}, From=\"{email_res.get('sender_name')}\" <{email_res.get('sender')}>, Subject='{email_res.get('subject')}', Date={email_res.get('received_datetime_utc')}")
                else:
                    logger.info("[Phase 1 Iceberg] No emails retrieved from Iceberg.")

                synthesized_reply = await synthesize_answer_from_context(message, iceberg_results, "operational data and emails", user_client, chat_model, chat_history)
                return {"type": "text", "reply": synthesized_reply}
            except Exception as e_iceberg:
                logger.error(f"[Phase 1 Iceberg] Error querying/synthesizing Iceberg data: {e_iceberg}", exc_info=True)
                return {"type": "text", "reply": "I encountered an issue while trying to retrieve operational data."}

        elif target == 'milvus' or target == 'multi' or confidence < LOW_CONFIDENCE_THRESHOLD:
            if target != 'milvus':
                 logger.info(f"[Phase 1 Router] Target is '{target}' or confidence {confidence:.2f} < {LOW_CONFIDENCE_THRESHOLD}. Defaulting to Milvus (knowledge base). ")
            else:
                 logger.info(f"[Phase 1 Router] Target is 'milvus'. Querying Milvus (knowledge base).")
            try:
                # For Milvus, the message itself can often be the query_text
                # The get_milvus_context includes deduplication and reranking.
                # Note: get_rate_card_response_advanced has more specific logic for rate cards.
                # If router identifies a rate card, we might want to invoke that more specific path.
                # For now, general Milvus search for knowledge questions.
                is_rate_card_query = "rate card" in message.lower() # Simple check for now
                if is_rate_card_query and target == 'milvus': # And router also thought it was knowledge question
                    logger.info("[Phase 1 Milvus] Identified as rate card query. Attempting to use get_rate_card_response_advanced logic.")
                    # This function already does retrieval and synthesis and returns a string.
                    # It needs to be adapted if its internal LLM calls are to use the main user_client.
                    # For now, we call it directly and assume it handles its own LLM client setup if needed.
                    # It expects `db` and `user` which are available in this scope.
                    # It doesn't fit the `synthesize_answer_from_context` pattern directly.
                    
                    # Import the rate card specific function
                    from app.rag.ratecard_rag import get_rate_card_response_advanced
                    rate_card_reply = await get_rate_card_response_advanced(message, chat_history or [], user, db, model_id, ms_token)
                    return {"type": "text", "reply": rate_card_reply}
                else:
                    milvus_docs, _ = await get_milvus_context(
                        max_items=10, # Fetch more for better synthesis context
                        max_chunk_chars=8000, # From original RAG settings
                        query=message, 
                        user_email=user.email, 
                        model_name=chat_model
                    )
                    synthesized_reply = await synthesize_answer_from_context(message, milvus_docs, "knowledge base documents", user_client, chat_model, chat_history)
                    return {"type": "text", "reply": synthesized_reply}
            except Exception as e_milvus:
                logger.error(f"[Phase 1 Milvus] Error querying/synthesizing Milvus data: {e_milvus}", exc_info=True)
                return {"type": "text", "reply": "I encountered an issue while searching the knowledge base."}
        
        elif target == "direct_llm_fallback": # Special case if router itself errored
            logger.info("[Phase 1 Router] Router errored. Attempting direct LLM reply as fallback.")
            try:
                response = await user_client.chat.completions.create(
                    model=chat_model,
                    messages=([{"role":"system", "content":"You are a helpful assistant."}] +
                              [{"role":h["role"], "content":h["content"]} for h in chat_history or []] +
                              [{"role":"user", "content":message}]),
                    temperature=0.1
                )
                direct_reply = response.choices[0].message.content.strip() if response.choices[0].message.content else "I'm not sure how to help with that."
                return {"type": "text", "reply": direct_reply }
            except Exception as e_direct_fallback:
                logger.error(f"[Phase 1 Direct Fallback] Error: {e_direct_fallback}", exc_info=True)
                return {"type": "text", "reply": "I had trouble formulating a direct response."}

        else: # Should not be reached if router provides valid target or error leads to direct_llm_fallback
            logger.error(f"[Phase 1 Router] Unhandled router target: '{target}'. Fallback to simple reply.")
            return {"type": "text", "reply": "I'm not quite sure how to handle your request with the current routing logic."}

    # --- Fallback to simple direct response --- 
    else:
        logger.info(f"[Fallback Direct Response] No tool interaction. Proceeding with direct response for user {user.email}")
        try:
            # Minimal messages for a direct reply
            response = await user_client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": message}
                ],
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e_fallback_direct:
            logger.error(f"Error in minimal fallback direct call: {e_fallback_direct}", exc_info=True)
            return "I am having trouble processing your request. Please try again later."

    # Should not be reached if logic is correct
    logger.error("RAG/ToolCall function reached unexpected end. Returning fallback.")
    if available_tools and not tool_results:
        return {"type": "text", "reply": fallback_response }
    return fallback_response 