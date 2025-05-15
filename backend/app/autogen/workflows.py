import logging
from typing import Dict, Any, List, Optional, Tuple
# Re-enable autogen imports
import autogen
from app.autogen.agent_factory import (
    create_assistant, 
    create_user_proxy, 
    create_group_chat, 
    create_group_chat_manager, 
    build_llm_config_for_user,
    Agent
)
from app.autogen.custom_agents import ResearchAgent, CodingAgent, CriticAgent
from app.services.client_factory import get_user_client
from app.models.user import User
from sqlalchemy.orm import Session
from fastapi import FastAPI
import json
import time # Import time for logging

logger = logging.getLogger(__name__)

async def run_research_workflow(
    query: str,
    user: User,
    db: Session,
    model_id: Optional[str] = None,
    max_rounds: int = 15,
    temperature: float = 0.5
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Run a research workflow with multiple agents collaborating to research a topic.
    
    Args:
        query: The research query/question to investigate
        user: Current user
        db: Database session
        model_id: Optional model ID to use (defaults to user's preference)
        max_rounds: Maximum conversation rounds
        temperature: Temperature for LLM
        
    Returns:
        Tuple of: List of messages exchanged, Summary dictionary with findings
    """
    logger.info(f"Starting research workflow for query: {query}")
    
    try:
        # Build LLM config based on user preferences
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id, 
            temperature=temperature
        )
        
        # Create the researcher agent
        researcher = create_assistant(
            name="Researcher",
            system_message=(
                "You are an expert researcher who provides accurate and detailed information. "
                "Focus on facts and cite sources when possible. Avoid speculation and clearly "
                "state when information is uncertain."
            ),
            llm_config=llm_config
        )
        
        # Create the critic agent
        critic = create_assistant(
            name="Critic",
            system_message=(
                "You are a critical thinker who evaluates information for accuracy, bias, and gaps. "
                "Your job is to identify weaknesses in the research and suggest improvements. "
                "Be constructive and specific in your criticism."
            ),
            llm_config=llm_config
        )
        
        # Create the synthesizer agent
        synthesizer = create_assistant(
            name="Synthesizer",
            system_message=(
                "You are a synthesis expert who consolidates information into coherent summaries. "
                "Identify key themes, create frameworks that organize the information, and present "
                "balanced conclusions. Focus on clarity and completeness."
            ),
            llm_config=llm_config
        )
        
        # Create a user proxy to oversee the conversation
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER",
            system_message=f"You are delegating the following research task to a team of agents: {query}"
        )
        user_proxy.max_consecutive_auto_reply = 0 # Prevent UserProxy auto-replies in this workflow
        
        # Create a group chat with all agents
        groupchat = create_group_chat(
            agents=[user_proxy, researcher, critic, synthesizer],
            max_round=max_rounds
        )
        
        # Create a manager to orchestrate the chat
        manager = create_group_chat_manager(
            groupchat=groupchat,
            llm_config=llm_config,
            system_message="You are managing a research discussion. Keep the conversation focused on the research query."
        )
        
        # Start the conversation with the research query
        user_proxy.initiate_chat(
            manager,
            message=f"Research query: {query}. Please investigate this topic thoroughly."
        )
        
        # Extract messages from the conversation
        messages = []
        for msg in groupchat.messages:
            if msg.get("role") != "system":  # Filter out system messages
                messages.append({
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "agent": msg.get("name", "unknown")
                })
        
        # Extract a summary from the synthesizer's last message
        summary = {
            "query": query,
            "summary": "No synthesis provided yet",
            "agent": "Synthesizer"
        }
        
        # Look for the synthesizer's last message
        for msg in reversed(groupchat.messages):
            if msg.get("name") == "Synthesizer":
                summary["summary"] = msg.get("content", "No synthesis provided")
                break
        
        logger.info("Research workflow completed successfully")
        return messages, summary
        
    except Exception as e:
        logger.error(f"Error in research workflow: {str(e)}", exc_info=True)
        
        # Fallback response in case of error
        messages = [{
            "role": "system",
            "content": f"Error in research workflow: {str(e)}"
        }, {
            "role": "assistant",
            "content": (
                "I encountered an issue while processing your research request. "
                "Please try again later or contact support if the problem persists."
            ),
            "agent": "System"
        }]
        
        summary = {
            "query": query,
            "summary": f"Error: {str(e)}",
            "agent": "System"
        }
        
        return messages, summary

async def run_code_generation_workflow(
    task_description: str,
    user: User,
    db: Session,
    model_id: Optional[str] = None,
    max_rounds: int = 10,
    temperature: float = 0.2,
    work_dir: str = "workspace"
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Run a code generation workflow with agents collaborating to generate code.
    
    Args:
        task_description: Description of the coding task
        user: Current user
        db: Database session
        model_id: Optional model ID to use
        max_rounds: Maximum conversation rounds
        temperature: Temperature for LLM
        work_dir: Working directory for code execution
        
    Returns:
        Tuple of: List of messages exchanged, Path to the generated code
    """
    logger.info(f"Starting code generation workflow for task: {task_description}")
    
    try:
        # Build LLM config based on user preferences
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id, 
            temperature=temperature
        )
        
        # Create the architect agent
        architect = create_assistant(
            name="Architect",
            system_message=(
                "You are a software architect who designs high-level solutions. "
                "Focus on system structure, component interactions, and best practices. "
                "Provide clear rationales for your design decisions."
            ),
            llm_config=llm_config
        )
        
        # Create the coder agent
        coder = create_assistant(
            name="Coder",
            system_message=(
                "You are an expert programmer who implements solutions based on requirements and designs. "
                "Write clean, efficient, and well-documented code. Follow best practices for the "
                "language and framework you're using."
            ),
            llm_config=llm_config
        )
        
        # Create the tester agent
        tester = create_assistant(
            name="Tester",
            system_message=(
                "You are a QA engineer who reviews and tests code. "
                "Look for bugs, edge cases, and improvements. Provide constructive feedback "
                "and suggest specific fixes for any issues you find."
            ),
            llm_config=llm_config
        )
        
        # Create a user proxy that will receive the code
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER",
            system_message=f"You are delegating the following coding task: {task_description}"
        )
        user_proxy.max_consecutive_auto_reply = 0 # Prevent UserProxy auto-replies in this workflow
        
        # Create a group chat with all agents
        groupchat = create_group_chat(
            agents=[user_proxy, architect, coder, tester],
            max_round=max_rounds
        )
        
        # Create a manager to orchestrate the chat
        manager = create_group_chat_manager(
            groupchat=groupchat,
            llm_config=llm_config,
            system_message="You are managing a code development discussion. Keep the conversation focused on implementing the requested code."
        )
        
        # Start the conversation with the coding task
        user_proxy.initiate_chat(
            manager,
            message=f"Coding task: {task_description}. Please design and implement a solution."
        )
        
        # Extract messages from the conversation
        messages = []
        for msg in groupchat.messages:
            if msg.get("role") != "system":  # Filter out system messages
                messages.append({
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "agent": msg.get("name", "unknown")
                })
        
        # The output path would normally be where code was saved
        # For now, we'll just return a placeholder
        output_path = f"{work_dir}/output.py"
        
        logger.info("Code generation workflow completed successfully")
        return messages, output_path
        
    except Exception as e:
        logger.error(f"Error in code generation workflow: {str(e)}", exc_info=True)
        
        # Fallback response in case of error
        messages = [{
            "role": "system",
            "content": f"Error in code generation workflow: {str(e)}"
        }, {
            "role": "assistant",
            "content": (
                "I encountered an issue while processing your code generation request. "
                "Please try again later or contact support if the problem persists."
            ),
            "agent": "System"
        }]
        
        return messages, work_dir + "/error.log"

async def run_qa_workflow(
    question: str,
    context: List[str],
    user: User,
    db: Session,
    model_id: Optional[str] = None,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """
    Run a QA workflow to answer a question based on the provided context.
    
    Args:
        question: The question to answer
        context: List of context strings to inform the answer
        user: Current user
        db: Database session
        model_id: Optional model ID to use
        temperature: Temperature for LLM
        
    Returns:
        Dict with answer and supporting information
    """
    logger.info(f"Starting QA workflow for question: {question}")
    
    try:
        # Build LLM config based on user preferences
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id, 
            temperature=temperature
        )
        
        # Create the QA agent
        qa_agent = create_assistant(
            name="QA",
            system_message=(
                "You are a question-answering assistant. Your task is to answer questions based only "
                "on the provided context. If the context doesn't contain the information needed, "
                "state that you cannot answer the question based on the available information."
            ),
            llm_config=llm_config
        )
        
        # Create a user proxy to interact with the QA agent
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER"
        )
        
        # Format the context for the assistant
        formatted_context = "\n\n".join([f"Context {i+1}:\n{ctx}" for i, ctx in enumerate(context)])
        message = f"Question: {question}\n\nHere is the context to use for answering:\n{formatted_context}"
        
        # Interact with the QA agent
        user_proxy.initiate_chat(
            qa_agent,
            message=message
        )
        
        # Get the answer from the QA agent's last message
        answer = "No answer provided"
        for msg in reversed(user_proxy.chat_messages[qa_agent]):
            if msg.get("role") == "assistant":
                answer = msg.get("content", "No answer provided")
                break
        
        # Determine confidence level based on heuristics
        confidence = "high" if len(answer) > 50 and "I cannot" not in answer and "don't have" not in answer else "low"
        
        # Return the QA result
        result = {
            "question": question,
            "answer": answer,
            "context_used": context,
            "confidence": confidence
        }
        
        logger.info("QA workflow completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error in QA workflow: {str(e)}", exc_info=True)
        
        # Fallback response in case of error
        return {
            "question": question,
            "answer": f"Error processing request: {str(e)}",
            "context_used": [],
            "confidence": "low"
        }

async def run_chat_workflow(
    message: str,
    user: User,
    db: Session,
    agents: List[Dict[str, Any]],
    conversation_id: str = None,
    app: FastAPI = None,
    history: Optional[List[Dict[str, Any]]] = None,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
    max_rounds: int = 10
) -> List[Dict[str, Any]]:
    """
    Run a flexible chat workflow with customizable agents.
    
    Args:
        message: The initial message
        user: Current user
        db: Database session
        agents: List of agent configurations
        conversation_id: Optional conversation ID for WebSocket notifications
        app: Optional FastAPI app instance for WebSocket notifications
        history: Optional conversation history
        model_id: Optional model ID to use
        temperature: Temperature for LLM
        max_rounds: Maximum conversation rounds
        
    Returns:
        List of messages in the conversation
    """
    logger.info(f"Starting chat workflow with message: {message}")
    
    # Initialize message hook if we have app and conversation_id
    message_hook = None
    if app and conversation_id and hasattr(app.state, 'ws_manager'):
        from app.autogen.message_hooks import AutoGenMessageHook
        message_hook = AutoGenMessageHook(app)
    
    try:
        # Build LLM config based on user preferences
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id, 
            temperature=temperature
        )
        
        # Create agents from the provided configurations
        created_agents = []
        for agent_config in agents:
            logger.debug(f"Full agent_config: {agent_config}")
            logger.info(f"Creating agent {getattr(agent_config, 'name', getattr(agent_config, 'agent', 'unknown'))} with system message: {getattr(agent_config, 'system_message', '')}")
            agent = create_assistant(
                name=agent_config.name,
                system_message=agent_config.system_message,
                llm_config=llm_config,
                max_consecutive_auto_reply=max_rounds  # Allow agent to reply as many times as needed
            )
            created_agents.append(agent)
        logger.info(f"[{time.time():.4f}] All domain agents created in {time.time() - t0:.4f}s")
        logger.info(f"Creating group chat with agents: {[a.name for a in created_agents]}")
        
        # Create a user proxy to interact with the agents
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER"
        )
        user_proxy.max_consecutive_auto_reply = 0 # Prevent UserProxy auto-replies in this workflow
        
        # Create a group chat with all AI agents (excluding user_proxy from the main agent list)
        groupchat = create_group_chat(
            agents=created_agents + [user_proxy],  # Include user_proxy as an agent
            max_round=max_rounds,
            speaker_selection_method="round_robin",
            allow_repeat_speaker=False
        )
        
        # Custom message handler for real-time updates
        async def on_new_message(sender, recipient, message):
            if message_hook and hasattr(message, 'get') and message.get('role') == 'assistant':
                # Send the "thinking" notification when agent is selected
                if message.get('name') and message.get('name') != 'User':
                    await message_hook.on_thinking(
                        user_id=str(user.id),
                        conversation_id=conversation_id,
                        agent_name=message.get('name')
                    )
            
            # When a new message is available from an agent
            if message_hook and message.get('content') and message.get('name') and message.get('name') != 'User':
                agent_message = {
                    "role": message.get('role', 'assistant'),
                    "content": message.get('content', ''),
                    "agent": message.get('name', 'Assistant')
                }
                
                await message_hook.on_message(
                    user_id=str(user.id),
                    conversation_id=conversation_id,
                    message=agent_message
                )
                
            return message
        
        # Register the message handler if we have a hook
        if message_hook:
            for agent in created_agents:
                if hasattr(agent, 'register_message_handler'):
                    agent.register_message_handler(on_new_message)
        
        # Create a manager to orchestrate the chat
        manager = create_group_chat_manager(
            groupchat=groupchat,
            llm_config=llm_config,
            system_message="You are managing a multi-agent conversation. Ensure all agents contribute appropriately and follow a round-robin approach."
        )
        
        # Initialize with history if provided
        if history and isinstance(history, list):
            for msg in history:
                if "role" in msg and "content" in msg:
                    groupchat.messages.append(msg)
        
        # Start the conversation with the user message
        user_proxy.initiate_chat(
            manager,
            message=message
        )
        
        # Extract messages from the conversation
        result_messages = []
        for msg in groupchat.messages:
            if msg.get("role") != "system":  # Filter out system messages
                result_messages.append({
                    "role": msg.get("role", "unknown"),
                    "content": msg.get("content", ""),
                    "agent": msg.get("name", "unknown")
                })
        
        logger.info("Chat workflow completed successfully")
        return result_messages
        
    except Exception as e:
        logger.error(f"Error in chat workflow: {str(e)}", exc_info=True)
        
        # Fallback response in case of error
        error_message = [{
            "role": "system",
            "content": f"Error in chat workflow: {str(e)}"
        }, {
            "role": "assistant",
            "content": (
                "I encountered an issue while processing your chat request. "
                "Please try again later or contact support if the problem persists."
            ),
            "agent": "System"
        }]
        
        # Try to send error via WebSocket if possible
        if message_hook and conversation_id:
            try:
                await message_hook.on_message(
                    user_id=str(user.id),
                    conversation_id=conversation_id,
                    message=error_message[1]
                )
            except:
                pass
                
        return error_message 

async def run_hybrid_orchestration_workflow(
    query: str,
    user: User,
    db: Session,
    agents: List[Dict[str, Any]],
    conversation_id: str = None,
    app: FastAPI = None,
    history: Optional[List[Dict[str, Any]]] = None,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
    max_rounds: int = 10,
    orchestration_type: Optional[str] = None,  # Can be explicitly provided or auto-determined
    use_mcp_tools: bool = True,  # Whether to allow the use of MCP tools
    stream: bool = True  # Whether to stream messages via WebSocket
) -> List[Dict[str, Any]]:
    """
    Run a hybrid orchestration workflow that dynamically chooses between parallel and sequential agent execution.
    
    Args:
        query: The user's query/message
        user: Current user
        db: Database session
        agents: List of agent configurations
        conversation_id: Optional conversation ID for WebSocket notifications
        app: Optional FastAPI app instance for WebSocket notifications
        history: Optional conversation history
        model_id: Optional model ID to use
        temperature: Temperature for LLM
        max_rounds: Maximum conversation rounds
        orchestration_type: Optional explicit orchestration type ("parallel" or "sequential")
        use_mcp_tools: Whether to allow the use of MCP tools
        stream: Whether to stream messages via WebSocket
        
    Returns:
        List of messages exchanged during the workflow
    """
    start_time = time.time()
    logger.info(f"[{start_time:.4f}] Starting hybrid orchestration workflow with query: {query}")
    
    # Initialize message hook if we have app and conversation_id
    message_hook = None
    if app and conversation_id and hasattr(app.state, 'ws_manager'):
        from app.autogen.message_hooks import AutoGenMessageHook
        message_hook = AutoGenMessageHook(app)
    
    try:
        t0 = time.time()
        # Build LLM config based on user preferences
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id, 
            temperature=temperature
        )
        logger.info(f"[{time.time():.4f}] LLM config built in {time.time() - t0:.4f}s")
        
        # Import the conductor agent
        from app.autogen.conductor_agent import ConductorAgent
        from app.autogen.tool_integration import get_relevant_mcp_tools, execute_mcp_tool_for_query
        
        t0 = time.time()
        # Create the conductor agent
        conductor = ConductorAgent(
            name="Conductor",
            llm_config=llm_config
        )
        logger.info(f"[{time.time():.4f}] ConductorAgent created in {time.time() - t0:.4f}s")
        
        # Determine if MCP tools should be used and which ones
        mcp_tools_to_use = []
        if use_mcp_tools:
            t0 = time.time()
            should_use_tools, tool_types = await conductor.should_use_mcp_tools(query, llm_config)
            logger.info(f"[{time.time():.4f}] conductor.should_use_mcp_tools completed in {time.time() - t0:.4f}s. Requires tools: {should_use_tools}, Types: {tool_types}")
            if should_use_tools:
                t0 = time.time()
                mcp_tools_to_use = await get_relevant_mcp_tools(user.email, db, tool_types)
                logger.info(f"[{time.time():.4f}] get_relevant_mcp_tools completed in {time.time() - t0:.4f}s. Selected {len(mcp_tools_to_use)} MCP tools.")
        
        # If orchestration_type is not provided, determine it automatically
        if not orchestration_type:
            t0 = time.time()
            orchestration_type = await conductor.determine_workflow_type(query, llm_config)
            logger.info(f"[{time.time():.4f}] conductor.determine_workflow_type completed in {time.time() - t0:.4f}s. Type: {orchestration_type}")
        
        t0 = time.time()
        # Helper to extract agent config fields without hardcoding
        def get_agent_field(agent_config, field):
            if hasattr(agent_config, '__getitem__') and not hasattr(agent_config, field):
                # dict-like
                return agent_config.get(field)
            return getattr(agent_config, field, None)

        # Create agents from the provided configurations
        created_agents = []
        for agent_config in agents:
            logger.debug(f"Full agent_config: {agent_config}")
            agent = create_assistant(
                name=get_agent_field(agent_config, 'name'),
                system_message=get_agent_field(agent_config, 'system_message'),
                llm_config=llm_config,
                max_consecutive_auto_reply=max_rounds  # Allow agent to reply as many times as needed
            )
            created_agents.append(agent)
        logger.info(f"[{time.time():.4f}] All domain agents created in {time.time() - t0:.4f}s")
        logger.info(f"Creating group chat with agents: {[a.name for a in created_agents]}")
        
        # Create a user proxy to interact with the agents
        t0 = time.time()
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER"
        )
        user_proxy.max_consecutive_auto_reply = 0 # Prevent UserProxy auto-replies in this workflow
        logger.info(f"[{time.time():.4f}] UserProxyAgent created in {time.time() - t0:.4f}s")
        
        # Create a synthesizer agent to combine parallel outputs
        t0 = time.time()
        synthesizer = create_assistant(
            name="Synthesizer",
            system_message=(
                "You are an expert synthesizer who combines multiple agent perspectives into "
                "a coherent, comprehensive response. Identify common themes, resolve "
                "contradictions, and create a unified response that incorporates the most "
                "valuable insights from each agent."
            ),
            llm_config=llm_config,
            max_consecutive_auto_reply=1 # Also for the synthesizer
        )
        logger.info(f"[{time.time():.4f}] Synthesizer agent created in {time.time() - t0:.4f}s")
        
        # Custom message handler for real-time updates
        async def on_new_message(sender, recipient, message):
            if not stream:
                return message
            if message_hook and hasattr(message, 'get') and message.get('role') == 'assistant':
                # Send the "thinking" notification when agent is selected
                if message.get('name') and message.get('name') != 'User':
                    await message_hook.on_thinking(
                        user_id=str(user.id),
                        conversation_id=conversation_id,
                        agent_name=message.get('name')
                    )
            # When a new message is available from an agent
            if message_hook and message.get('content') and message.get('name') and message.get('name') != 'User':
                agent_message = {
                    "role": message.get('role', 'assistant'),
                    "content": message.get('content', ''),
                    "agent": message.get('name', 'Assistant')
                }
                await message_hook.on_message(
                    user_id=str(user.id),
                    conversation_id=conversation_id,
                    message=agent_message
                )
            return message
        
        # Register message handlers
        if message_hook:
            for agent in created_agents + [conductor, synthesizer]:
                if hasattr(agent, 'register_message_handler'):
                    agent.register_message_handler(on_new_message)
        
        all_messages = []
        
        # If we have MCP tools, execute them first and add results to the query
        tool_results = []
        
        if mcp_tools_to_use:
            logger.info(f"[{time.time():.4f}] Starting MCP tool execution. Number of tools: {len(mcp_tools_to_use)}")
            # Let user know we're using tools
            if stream and message_hook:
                await message_hook.on_message(
                    user_id=str(user.id),
                    conversation_id=conversation_id,
                    message={
                        "role": "assistant",
                        "content": f"Using {len(mcp_tools_to_use)} tools to help answer your query...",
                        "agent": "System"
                    }
                )
            # Execute tools and gather results
            for tool_idx, tool in enumerate(mcp_tools_to_use):
                tool_exec_start_time = time.time()
                try:
                    if stream and message_hook:
                        await message_hook.on_message(
                            user_id=str(user.id),
                            conversation_id=conversation_id,
                            message={
                                "role": "assistant",
                                "content": f"Executing tool: {tool.get('name', 'Unknown Tool')}",
                                "agent": "System"
                            }
                        )
                    logger.info(f"[{time.time():.4f}] Executing tool {tool_idx + 1}/{len(mcp_tools_to_use)}: {tool.get('name', 'Unknown Tool')}")
                    result = await execute_mcp_tool_for_query(tool, query, user.email, llm_config)
                    logger.info(f"[{time.time():.4f}] Tool {tool.get('name', 'Unknown Tool')} completed in {time.time() - tool_exec_start_time:.4f}s")
                    if "error" not in result:
                        tool_results.append({
                            "tool_name": tool.get("name", "Unknown Tool"),
                            "result": result
                        })
                        if stream and message_hook:
                            await message_hook.on_message(
                                user_id=str(user.id),
                                conversation_id=conversation_id,
                                message={
                                    "role": "assistant",
                                    "content": f"Tool {tool.get('name', 'Unknown Tool')} executed successfully",
                                    "agent": "System"
                                }
                            )
                except Exception as e:
                    logger.error(f"[{time.time():.4f}] Error executing tool: {e}")
                    if stream and message_hook:
                        await message_hook.on_message(
                            user_id=str(user.id),
                            conversation_id=conversation_id,
                            message={
                                "role": "assistant",
                                "content": f"Error executing tool {tool.get('name', 'Unknown Tool')}: {str(e)}",
                                "agent": "System"
                            }
                        )
            
            # If we got tool results, add them to the query
            if tool_results:
                tool_results_text = "The following tools were executed:\n\n"
                for result in tool_results:
                    tool_results_text += f"--- {result['tool_name']} ---\n"
                    tool_results_text += f"{json.dumps(result['result'], indent=2)}\n\n"
                
                # Update the query to include tool results
                query = f"{query}\n\n{tool_results_text}\nPlease use this information in your response."
                logger.info(f"[{time.time():.4f}] Query updated with tool results.")
        
        logger.info(f"[{time.time():.4f}] Pre-chat setup completed. Total time so far: {time.time() - start_time:.4f}s. Starting agent interaction with orchestration_type: {orchestration_type}")

        # --- Orchestration using group chat/manager (restored pattern) ---
        if orchestration_type == "parallel":
            logger.info(f"[{time.time():.4f}] Using PARALLEL workflow orchestration (manual fan-out)")
            agent_responses = []
            all_messages = []
            for agent in created_agents:
                logger.info(f"[{time.time():.4f}] Initiating chat with parallel agent: {agent.name}")
                user_proxy.initiate_chat(
                    agent,
                    message=query
                )
                # Robustly extract chat history
                chat_history = []
                if agent in user_proxy.chat_messages:
                    chat_history = user_proxy.chat_messages[agent]
                elif hasattr(agent, 'name') and agent.name in user_proxy.chat_messages:
                    chat_history = user_proxy.chat_messages[agent.name]
                logger.debug(f"user_proxy.chat_messages after chatting with {agent.name}: {user_proxy.chat_messages}")
                logger.debug(f"Full chat_history for {agent.name}: {chat_history}")
                # Print every message in chat_history for diagnosis
                for msg in chat_history:
                    logger.debug(f"Message in chat_history for {agent.name}: {msg}")
                # Find the last non-empty message from the agent
                agent_reply = next(
                    (msg for msg in reversed(chat_history)
                     if msg.get('name') == agent.name and msg.get('content', '').strip()),
                    None
                )
                if agent_reply:
                    response = agent_reply['content']
                    logger.debug(f"Extracted agent response for {agent.name}: {repr(response)}")
                    agent_responses.append({
                        "agent": agent.name,
                        "response": response
                    })
                    # Always normalize agent message structure for frontend
                    all_messages.append({
                        "role": "assistant",  # Always 'assistant' for agent replies
                        "content": response,
                        "agent": agent.name    # Always include agent name
                    })
                else:
                    logger.warning(f"No valid response found for agent {agent.name}")
                    all_messages.append({
                        "role": "assistant",
                        "content": "[Agent did not provide a valid response]",
                        "agent": agent.name
                    })
            # Synthesize the responses
            synthesis_prompt = "I need you to synthesize the following agent responses into a comprehensive answer. Ensure the final output is a single, coherent response based on the inputs provided, and does not refer to the synthesis process itself or the individual agents unless it's natural to do so in the context of the combined answer:\n\n"
            for resp in agent_responses:
                synthesis_prompt += f"--- {resp['agent']} ---\n{resp['response']}\n\n"
            logger.info(f"Synthesis prompt for Synthesizer: {synthesis_prompt[:500]}{'...' if len(synthesis_prompt) > 500 else ''}")
            user_proxy.initiate_chat(
                synthesizer,
                message=synthesis_prompt
            )
            if len(user_proxy.chat_messages[synthesizer]) > 0:
                synthesized_response = user_proxy.chat_messages[synthesizer][-1]["content"]
                all_messages.append({
                    "role": "assistant",
                    "content": synthesized_response,
                    "agent": "Synthesizer"
                })
            logger.info(f"[{time.time():.4f}] Parallel orchestration completed. Returning {len(all_messages)} messages.")
            return all_messages
        else:  # Sequential workflow
            logger.info(f"[{time.time():.4f}] Using SEQUENTIAL workflow orchestration (group chat)")
            # Chain the user message through agents in sequence
            current_input = query
            all_messages = []
            # Append the initial user message once
            all_messages.append({
                "role": "user",
                "content": query,
                "agent": "User"
            })
            for i, agent in enumerate(created_agents):
                groupchat = create_group_chat(
                    agents=[agent, user_proxy],
                    max_round=max_rounds,
                    speaker_selection_method="round_robin",
                    allow_repeat_speaker=False
                )
                if message_hook and hasattr(agent, 'register_message_handler'):
                    agent.register_message_handler(on_new_message)
                manager = create_group_chat_manager(
                    groupchat=groupchat,
                    llm_config=llm_config,
                    system_message=f"You are managing a sequential agent conversation. Agent: {agent.name}"
                )
                # Start the conversation with the user message (ASYNC for streaming)
                await user_proxy.a_initiate_chat(
                    manager,
                    message=current_input
                )
                # Extract agent's response
                agent_response = None
                for msg in reversed(groupchat.messages):
                    if msg.get("name") == agent.name and msg.get("content"):
                        agent_response = msg.get("content")
                        # Only append the agent's actual response
                        all_messages.append({
                            "role": "assistant",  # Always 'assistant' for agent replies
                            "content": agent_response,
                            "agent": agent.name    # Always include agent name
                        })
                        break
                if agent_response is None:
                    logger.warning(f"[{time.time():.4f}] Agent {agent.name} did not provide a valid response.")
                    all_messages.append({
                        "role": "assistant",
                        "content": "[Agent did not provide a valid response]",
                        "agent": agent.name
                    })
                # Prepare input for next agent
                if i < len(created_agents) - 1 and agent_response:
                    current_input = f"The previous agent ({agent.name}) provided this analysis:\n\n{agent_response}\n\nPlease build on this and provide your expertise."
                logger.info(f"Group chat messages (sequential, agent {agent.name}): {json.dumps(groupchat.messages, indent=2)}")
            logger.info(f"[{time.time():.4f}] Sequential group chat completed. Returning {len(all_messages)} messages.")
            return all_messages
    
    except Exception as e:
        logger.error(f"[{time.time():.4f}] Error in hybrid orchestration workflow: {str(e)}", exc_info=True)
        total_time = time.time() - start_time
        logger.info(f"[{time.time():.4f}] Hybrid orchestration workflow ERRORED. Total execution time: {total_time:.4f}s")
        return [{
            "role": "assistant",
            "content": f"An error occurred during the workflow: {str(e)}",
            "agent": "System"
        }]
