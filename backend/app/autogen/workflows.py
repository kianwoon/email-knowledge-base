import logging
from typing import Dict, Any, List, Optional, Tuple
# Temporarily disable autogen imports
# import autogen
# from autogen import Agent, AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from app.autogen.agent_factory import (
    create_assistant, 
    create_user_proxy, 
    create_group_chat, 
    create_group_chat_manager, 
    build_llm_config_for_user,
    Agent
)
# from app.autogen.custom_agents import ResearchAgent, CodingAgent, CriticAgent
from app.services.client_factory import get_user_client
from app.models.user import User
from sqlalchemy.orm import Session

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
        # Build LLM config for the user
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id,
            temperature=temperature
        )
        
        # Create agents for the research team
        researcher = create_assistant(
            name="Researcher",
            system_message=(
                "You are a research assistant that searches for accurate information. "
                "Research the topic thoroughly and provide detailed findings with references when possible."
            ),
            llm_config=llm_config
        )
        
        critic = create_assistant(
            name="Critic",
            system_message=(
                "You are a critical thinker who evaluates research findings. "
                "Your job is to analyze the information provided, identify potential gaps or biases, "
                "and suggest improvements or alternative perspectives."
            ),
            llm_config=llm_config
        )
        
        summarizer = create_assistant(
            name="Summarizer",
            system_message=(
                "You are an expert at summarizing complex information. "
                "Your task is to condense research findings into a clear, concise summary "
                "that captures the key points and insights."
            ),
            llm_config=llm_config
        )
        
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER",  # Automated mode
            code_execution_config=None  # Disable code execution for safety
        )
        
        # Create a group chat
        groupchat = create_group_chat(
            agents=[researcher, critic, summarizer, user_proxy],
            messages=[],
            max_round=max_rounds
        )
        
        # Create manager
        manager = create_group_chat_manager(
            groupchat=groupchat,
            llm_config=llm_config,
            system_message=(
                "You are managing a research discussion. Guide the conversation to thoroughly "
                "explore the topic, ensure all perspectives are considered, and work toward "
                "a comprehensive and accurate summary."
            )
        )
        
        # Start the chat with the research query
        user_proxy.initiate_chat(
            recipient=manager,
            message=f"Research the following topic and provide a detailed summary: {query}"
        )
        
        # Extract messages from the group chat
        messages = []
        for msg in groupchat.messages:
            messages.append({
                "role": "assistant" if msg.get("role") == "assistant" else "user",
                "name": msg.get("name", "System"),
                "content": msg.get("content", "")
            })
        
        # Get the final summary from the last message by the summarizer
        summary_content = "No summary generated."
        for msg in reversed(groupchat.messages):
            if msg.get("name") == "Summarizer":
                summary_content = msg.get("content", "No summary generated.")
                break
        
        # Create summary object
        summary = {
            "query": query,
            "summary": summary_content,
            "agent": "Summarizer"
        }
        
        return messages, summary
    except Exception as e:
        logger.error(f"Error in research workflow: {str(e)}", exc_info=True)
        empty_messages = []
        summary = {
            "query": query,
            "summary": f"An error occurred during the research workflow: {str(e)}",
            "agent": "System"
        }
        return empty_messages, summary

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
        # Build LLM config for the user
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id,
            temperature=temperature
        )
        
        # Create a directory for code execution if it doesn't exist
        import os
        os.makedirs(work_dir, exist_ok=True)
        
        # Create agents for the coding team
        coder = create_assistant(
            name="Coder",
            system_message=(
                "You are an expert software developer. Your task is to implement code based on "
                "requirements. Write clean, efficient, and well-documented code that follows "
                "best practices for the relevant programming language."
            ),
            llm_config=llm_config
        )
        
        code_reviewer = create_assistant(
            name="CodeReviewer",
            system_message=(
                "You are a code review expert. Your task is to review code for errors, "
                "bugs, security issues, and adherence to best practices. Provide constructive "
                "feedback and suggest improvements."
            ),
            llm_config=llm_config
        )
        
        # Code execution config - enable code execution for the user proxy
        code_execution_config = {
            "work_dir": work_dir,
            "use_docker": False,  # For safety in this implementation
            "timeout": 60,
            "last_n_messages": 10,
        }
        
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER",  # Automated mode
            code_execution_config=code_execution_config
        )
        
        # Start the chat
        user_proxy.initiate_chat(
            coder,
            message=(
                f"Task: {task_description}\n\n"
                "Please write code to accomplish this task. Once you've written the code, "
                "I'll review it and provide feedback. If needed, we can iterate to improve the solution."
            )
        )
        
        # After the coder provides a solution, engage the code reviewer
        messages = []
        for msg in user_proxy.chat_messages.get(coder.name, []):
            messages.append({
                "role": msg.get("role", "user"),
                "name": msg.get("name", "System"),
                "content": msg.get("content", "")
            })
        
        # Get the last code implementation from the coder
        code_content = None
        code_file_path = None
        
        for msg in reversed(messages):
            content = msg.get("content", "")
            if "```" in content and msg.get("name") == "Coder":
                # Extract code between triple backticks
                import re
                code_blocks = re.findall(r"```(?:\w+)?\s*([\s\S]+?)```", content)
                if code_blocks:
                    code_content = code_blocks[0].strip()
                    break
        
        if code_content:
            # Save the code to a file in the workspace
            import random
            import string
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            code_file_path = os.path.join(work_dir, f"generated_code_{random_suffix}.py")
            
            with open(code_file_path, "w") as f:
                f.write(code_content)
            
            logger.info(f"Code generated and saved to {code_file_path}")
        
        return messages, code_file_path or work_dir
    except Exception as e:
        logger.error(f"Error in code generation workflow: {str(e)}", exc_info=True)
        empty_messages = []
        return empty_messages, work_dir

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
        # Build LLM config for the user
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id,
            temperature=temperature
        )
        
        # Format the context
        formatted_context = "\n\n".join([f"Context {i+1}:\n{ctx}" for i, ctx in enumerate(context)])
        
        # Create the QA assistant
        qa_assistant = create_assistant(
            name="QA_Assistant",
            system_message=(
                "You are a question-answering assistant. Your task is to provide accurate, "
                "concise answers to questions based on the provided context. Only use information "
                "from the context. If the answer cannot be determined from the context, say so clearly."
            ),
            llm_config=llm_config
        )
        
        # Create user proxy
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER",  # Automated mode
            code_execution_config=None  # Disable code execution for QA
        )
        
        # Create the prompt with context and question
        prompt = (
            f"I need you to answer a question based on the following context information.\n\n"
            f"{formatted_context}\n\n"
            f"Question: {question}\n\n"
            f"Please provide a concise and accurate answer using only the information in the context. "
            f"If the context doesn't contain the answer, indicate that clearly."
        )
        
        # Start the chat
        user_proxy.initiate_chat(
            qa_assistant,
            message=prompt
        )
        
        # Get the answer from the QA assistant
        answer_text = "No answer generated."
        confidence = 0.0
        sources = []
        
        # Extract the answer from the chat
        chat_history = user_proxy.chat_messages.get(qa_assistant.name, [])
        if len(chat_history) >= 2:  # At least user prompt and assistant response
            answer_content = chat_history[1].get("content", "")
            if answer_content:
                answer_text = answer_content
                
                # Estimate confidence based on language markers
                if "definitely" in answer_text.lower() or "certainly" in answer_text.lower():
                    confidence = 0.9
                elif "likely" in answer_text.lower() or "probably" in answer_text.lower():
                    confidence = 0.7
                elif "might" in answer_text.lower() or "may" in answer_text.lower():
                    confidence = 0.5
                elif "unclear" in answer_text.lower() or "cannot determine" in answer_text.lower():
                    confidence = 0.3
                else:
                    confidence = 0.6
                
                # Extract source references if present
                import re
                source_refs = re.findall(r"Context (\d+)", answer_content)
                sources = [int(ref) for ref in source_refs]
        
        # Format the result
        answer = {
            "question": question,
            "answer": answer_text,
            "sources": sources,
            "confidence": confidence
        }
        
        return answer
    except Exception as e:
        logger.error(f"Error in QA workflow: {str(e)}", exc_info=True)
        return {
            "question": question,
            "answer": f"An error occurred during the QA workflow: {str(e)}",
            "sources": [],
            "confidence": 0
        }

async def run_chat_workflow(
    message: str,
    user: User,
    db: Session,
    agents: List[Dict[str, Any]],
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
        history: Optional conversation history
        model_id: Optional model ID to use
        temperature: Temperature for LLM
        max_rounds: Maximum conversation rounds
        
    Returns:
        List of messages in the conversation
    """
    logger.info(f"Starting chat workflow with message: {message}")
    
    try:
        # Build LLM config for the user
        llm_config = await build_llm_config_for_user(
            user=user,
            db=db,
            model_id=model_id,
            temperature=temperature
        )
        
        # Initialize conversation history if None
        history = history or []
        
        # Create assistant agents from the agent configurations
        assistant_agents = []
        for agent_config in agents:
            if agent_config.get("isEnabled", True):
                assistant = create_assistant(
                    name=agent_config.get("name", "Assistant"),
                    system_message=agent_config.get("systemMessage", "You are a helpful assistant."),
                    llm_config=llm_config,
                    human_input_mode="NEVER"
                )
                assistant_agents.append(assistant)
        
        # Create user proxy agent
        user_proxy = create_user_proxy(
            name="user",
            human_input_mode="NEVER",  # We're automating this
            code_execution_config=None  # Disable code execution for safety
        )
        
        # Add initial message from user
        history.append({
            "role": "user",
            "content": message
        })
        
        # Run the chat with each assistant
        for assistant in assistant_agents:
            # Initiate chat between user proxy and the assistant
            user_proxy.initiate_chat(
                assistant,
                message=message,
                max_turns=2  # Keep it simple for now
            )
            
            # Extract the response from the assistant
            chat_history = user_proxy.chat_messages.get(assistant.name, [])
            if chat_history and len(chat_history) >= 2:
                # Get the assistant's response
                assistant_message = chat_history[1]  # Second message is assistant's response
                history.append({
                    "role": "assistant",
                    "name": assistant.name,
                    "content": assistant_message.get("content", "")
                })
        
        return history
    except Exception as e:
        logger.error(f"Error in chat workflow: {str(e)}", exc_info=True)
        # Return basic error message in history
        history = history or []
        history.append({
            "role": "system",
            "content": f"An error occurred during the chat workflow: {str(e)}"
        })
        return history 