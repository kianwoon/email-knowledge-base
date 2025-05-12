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
            agent = create_assistant(
                name=agent_config.name,
                system_message=agent_config.system_message,
                llm_config=llm_config
            )
            created_agents.append(agent)
        
        # Create a user proxy to interact with the agents
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER"
        )
        
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