import logging
from typing import Dict, Any, List, Optional, Tuple
import autogen
from autogen import Agent, AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from app.autogen.agent_factory import (
    create_assistant, 
    create_user_proxy, 
    create_group_chat, 
    create_group_chat_manager, 
    build_llm_config_for_user
)
from app.autogen.custom_agents import ResearchAgent, CodingAgent, CriticAgent
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
    
    # Build LLM config based on user settings
    llm_config = await build_llm_config_for_user(
        user=user, 
        db=db, 
        model_id=model_id,
        temperature=temperature
    )
    
    # Create specialized research agents
    researcher = create_assistant(
        name="Researcher",
        system_message=(
            "You are an expert researcher. Your role is to research the topic thoroughly and "
            "provide comprehensive information with citations when possible. "
            "Always consider multiple perspectives and sources. "
            "Avoid making claims without evidence."
        ),
        llm_config=llm_config
    )
    
    critic = create_assistant(
        name="Critic",
        system_message=(
            "You are a critical thinker and fact-checker. Your role is to evaluate "
            "the research, identify potential biases, logical fallacies, or missing information. "
            "Push for rigor and balanced perspectives. Question assumptions and ask for evidence."
        ),
        llm_config=llm_config
    )
    
    synthesizer = create_assistant(
        name="Synthesizer",
        system_message=(
            "You are a synthesis expert. Your role is to integrate and organize information "
            "from different sources and perspectives into a coherent whole. "
            "Create structured summaries and extract key insights. "
            "Focus on presenting a balanced view that addresses the core query."
        ),
        llm_config=llm_config
    )
    
    user_proxy = create_user_proxy(
        name="ResearchManager",
        human_input_mode="NEVER",
        system_message=(
            f"You are coordinating a research effort on the following query: {query}\n"
            "Start the conversation by introducing the research question to the other agents. "
            "At the end, ask the Synthesizer to provide a final comprehensive summary of findings."
        ),
        code_execution_config=None  # No code execution for this workflow
    )
    
    # Set up the group chat
    groupchat = create_group_chat(
        agents=[user_proxy, researcher, critic, synthesizer],
        messages=[{"role": "user", "content": f"Research Question: {query}"}],
        max_round=max_rounds,
    )
    
    # Create the manager
    manager = create_group_chat_manager(
        groupchat=groupchat,
        llm_config=llm_config,
        system_message=(
            "You are managing a research conversation. Ensure all perspectives are heard. "
            "Select the most appropriate agent to speak next based on the conversation flow. "
            "Prefer the Researcher for initial information gathering, the Critic for evaluation, "
            "and the Synthesizer for organizing and summarizing findings."
        )
    )
    
    # Start the conversation
    await user_proxy.a_initiate_chat(
        manager,
        message=f"Let's research the following question thoroughly: {query}",
    )
    
    # Return conversation history and final summary
    # Extract final summary from the last messages of the Synthesizer
    final_summary = {}
    for message in reversed(groupchat.messages):
        if message.get("name") == "Synthesizer":
            # Parse the final summary into a structured format
            final_summary = {
                "query": query,
                "summary": message.get("content", "No summary provided"),
                "agent": "Synthesizer"
            }
            break
    
    return groupchat.messages, final_summary

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
    
    # Build LLM config based on user settings
    llm_config = await build_llm_config_for_user(
        user=user, 
        db=db, 
        model_id=model_id,
        temperature=temperature
    )
    
    # Create specialized coding agents
    architect = create_assistant(
        name="Architect",
        system_message=(
            "You are a software architect. Your role is to design high-level solutions and "
            "system structures before implementation begins. "
            "Focus on patterns, component interactions, and best practices. "
            "Provide clear architectural guidance and consider maintainability, "
            "scalability, and security in your designs."
        ),
        llm_config=llm_config
    )
    
    coder = create_assistant(
        name="Coder",
        system_message=(
            "You are an expert programmer. Your role is to implement the code based on "
            "the architectural design. Write clean, efficient, and well-documented code. "
            "Follow best practices for the language/framework being used. "
            "When providing code, make sure it's complete and executable."
        ),
        llm_config=llm_config
    )
    
    tester = create_assistant(
        name="Tester",
        system_message=(
            "You are a software quality engineer. Your role is to review code, identify bugs, "
            "edge cases, or potential issues. Suggest tests and quality improvements. "
            "Focus on correctness, test coverage, error handling, and edge cases. "
            "Provide specific test scenarios or test code when appropriate."
        ),
        llm_config=llm_config
    )
    
    # User proxy that can execute code
    user_proxy = create_user_proxy(
        name="CodeManager",
        human_input_mode="NEVER",
        system_message=(
            f"You are coordinating a code development effort for the following task: {task_description}\n"
            "Start by introducing the task to the team. You can execute code to test it. "
            "At the end, run the code a final time to ensure it works as expected."
        ),
        code_execution_config={
            "work_dir": work_dir,
            "use_docker": False,  # Set to True for secure execution in production
            "timeout": 60,
            "last_n_messages": 10,
        }
    )
    
    # Set up the group chat
    groupchat = create_group_chat(
        agents=[user_proxy, architect, coder, tester],
        messages=[{"role": "user", "content": f"Coding Task: {task_description}"}],
        max_round=max_rounds,
    )
    
    # Create the manager
    manager = create_group_chat_manager(
        groupchat=groupchat,
        llm_config=llm_config,
        system_message=(
            "You are managing a software development conversation. "
            "Start with the Architect for high-level design, then the Coder for implementation, "
            "followed by the Tester for validation. Allow iterations as needed."
        )
    )
    
    # Start the conversation
    await user_proxy.a_initiate_chat(
        manager,
        message=f"We need to develop code for the following task: {task_description}. Let's collaborate on this.",
    )
    
    # Find the output file path from the conversation
    output_path = work_dir  # Default if no specific file is created
    for message in groupchat.messages:
        # Look for file paths in messages, particularly from the Coder
        if "file is saved at" in message.get("content", "").lower():
            content = message.get("content", "")
            # Simple extraction, can be improved for robustness
            lines = content.split("\n")
            for line in lines:
                if "file is saved at" in line.lower():
                    parts = line.split(":")
                    if len(parts) > 1:
                        path = parts[1].strip()
                        if path:
                            output_path = path
                            break
    
    return groupchat.messages, output_path

async def run_qa_workflow(
    question: str,
    context: List[str],
    user: User,
    db: Session,
    model_id: Optional[str] = None,
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """
    Run a question-answering workflow with a specialized agent.
    
    Args:
        question: The question to answer
        context: List of context passages to use for answering
        user: Current user
        db: Database session
        model_id: Optional model ID to use
        temperature: Temperature for LLM
        
    Returns:
        Dict with the answer and metadata
    """
    logger.info(f"Starting QA workflow for question: {question}")
    
    # Build LLM config based on user settings
    llm_config = await build_llm_config_for_user(
        user=user, 
        db=db, 
        model_id=model_id,
        temperature=temperature
    )
    
    # Prepare context
    formatted_context = "\n\n---\n\n".join([f"Context {i+1}:\n{ctx}" for i, ctx in enumerate(context)])
    
    # Create a QA assistant
    qa_assistant = create_assistant(
        name="QA_Expert",
        system_message=(
            "You are an expert at answering questions based on the provided context. "
            "Always base your answers on the information in the context. "
            "If the context doesn't contain the information needed, say so clearly. "
            "Do not make up or infer facts not supported by the context. "
            "Cite your sources from the context when possible."
        ),
        llm_config=llm_config
    )
    
    # Create a simple user proxy
    user_proxy = create_user_proxy(
        name="QA_User",
        human_input_mode="NEVER"
    )
    
    # Formulate the prompt with context and question
    prompt = f"""
Here is the context information to use for answering:

{formatted_context}

Based strictly on the above context, please answer the following question:
{question}

If you cannot answer based on the context provided, please state that clearly.
"""
    
    # Start the conversation
    await user_proxy.a_initiate_chat(
        qa_assistant,
        message=prompt,
    )
    
    # Extract the answer from the conversation
    answer = "No answer provided"
    if len(user_proxy.chat_messages[qa_assistant]) > 0:
        answer = user_proxy.chat_messages[qa_assistant][-1]["content"]
    
    result = {
        "question": question,
        "answer": answer,
        "context_used": context,
        "confidence": "high" if "I cannot answer" not in answer else "low"
    }
    
    return result

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
    Run a chat workflow with customizable agents specified by the user.
    
    Args:
        message: The user's message
        user: Current user
        db: Database session
        agents: List of agent configurations (name, type, system_message)
        history: Optional chat history
        model_id: Optional model ID to use
        temperature: Temperature for LLM
        max_rounds: Maximum conversation rounds
        
    Returns:
        List of messages from the agents in response to the query
    """
    logger.info(f"Starting chat workflow for message: {message}")
    logger.info(f"Using {len(agents)} custom agents")
    
    # Check if we have at least one agent
    if not agents or len(agents) == 0:
        logger.warning("No agents provided for chat workflow")
        return [{
            "role": "assistant",
            "name": "System",
            "content": "No agents are configured. Please provide at least one agent."
        }]
    
    try:
        # Build LLM config based on user settings
        llm_config = await build_llm_config_for_user(
            user=user, 
            db=db, 
            model_id=model_id,
            temperature=temperature
        )
        
        # Check if we have a valid API key (not placeholder)
        if (not llm_config or 
            not llm_config.get("config_list") or 
            not llm_config["config_list"][0].get("api_key") or 
            llm_config["config_list"][0]["api_key"] == "PLACEHOLDER_KEY"):
            logger.error("No valid API key found for chat workflow")
            return [{
                "role": "assistant",
                "name": "System",
                "content": "No valid API key found. Please configure an API key for the selected model."
            }]
            
        # Create all the agents based on the provided configurations
        autogen_agents = []
        
        # Create a simplified user proxy
        user_proxy = create_user_proxy(
            name="User",
            human_input_mode="NEVER",
            system_message=f"You are asking: {message}"
        )
        autogen_agents.append(user_proxy)
        
        # Create the custom agents
        for agent_config in agents:
            # Access attributes directly since agent_config is a Pydantic model
            agent_name = agent_config.name if hasattr(agent_config, 'name') else "Assistant"
            agent_type = agent_config.type if hasattr(agent_config, 'type') else "assistant"
            
            # Enhance the system message based on message type
            base_system_message = agent_config.system_message if hasattr(agent_config, 'system_message') else "You are a helpful AI assistant."
            
            # Check if message is a complex query requiring research
            is_research_query = len(message.split()) > 10 or any(kw in message.lower() for kw in 
                                ["research", "explain", "analyze", "investigate", "what is", "how does", 
                                 "why is", "when did", "who is", "where is"])
            
            enhanced_system_message = base_system_message
            if is_research_query:
                enhanced_system_message += "\n\nThis appears to be a research question. Provide a comprehensive, accurate response with relevant facts and context. If appropriate, organize your response in a structured format."
            else:
                enhanced_system_message += "\n\nRespond in a conversational, helpful manner appropriate to the query."
            
            if agent_type == "researcher":
                agent = ResearchAgent(
                    name=agent_name,
                    system_message=enhanced_system_message,
                    llm_config=llm_config,
                )
            elif agent_type == "coder":
                agent = CodingAgent(
                    name=agent_name,
                    system_message=enhanced_system_message,
                    llm_config=llm_config,
                )
            elif agent_type == "critic":
                agent = CriticAgent(
                    name=agent_name,
                    system_message=enhanced_system_message,
                    llm_config=llm_config,
                )
            else:  # Default to assistant
                agent = create_assistant(
                    name=agent_name,
                    system_message=enhanced_system_message,
                    llm_config=llm_config,
                )
            
            autogen_agents.append(agent)
        
        # Format previous history as messages
        initial_messages = []
        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role and content:
                    if role == "user":
                        initial_messages.append({"role": "user", "content": content, "name": "User"})
                    else:
                        # Try to match the assistant message to an agent name
                        agent_name = msg.get("name", "Assistant")
                        initial_messages.append({"role": "assistant", "content": content, "name": agent_name})
        
        # Add the user's current message
        initial_messages.append({"role": "user", "content": message, "name": "User"})
        
        # Set up the group chat with the agents and the previous messages
        # Determine rounds based on query complexity
        max_rounds_value = 1  # Default for greetings
        
        # For complex queries or explicit research questions, allow more rounds for better answers
        if is_research_query:
            max_rounds_value = 3  # More rounds for research questions
            logger.info(f"Using {max_rounds_value} rounds for research query: {message[:50]}...")
        
        groupchat = create_group_chat(
            agents=autogen_agents,
            messages=initial_messages,
            max_round=max_rounds_value,
            speaker_selection_method="round_robin",  # Use round-robin to give each agent a chance to speak
            allow_repeat_speaker=False
        )
        
        # Create the manager to orchestrate the conversation
        manager = create_group_chat_manager(
            groupchat=groupchat,
            llm_config=llm_config,
            system_message=(
                "You are managing a conversation between multiple AI agents. "
                "Ensure each agent contributes according to their expertise. "
                "Keep the conversation focused on addressing the user's query. "
                "The conversation should end naturally after the user's query has been addressed."
            )
        )
        
        # Modified to get just one response and then terminate
        # Instead of initiating a full conversation, we'll send the message manually
        
        # Just use the manager with the simplest possible approach - 
        # Group chat is already set to max_round=1, so it will only do one exchange
        try:
            # Use the normal group chat approach but with limited rounds
            await manager.a_run(message)
        except Exception as e:
            logger.error(f"Error in manager.a_run: {str(e)}", exc_info=True)
            # Fallback for errors - add a basic response
            groupchat.messages.append({
                "role": "assistant", 
                "content": f"I received your message: {message}. How can I help?", 
                "name": "Assistant"
            })
        
        # Format the response
        response_messages = []
        
        # Process the messages from the group chat
        # We're only interested in the assistants' responses, not the user messages or empty messages
        for i, msg in enumerate(groupchat.messages):
            if isinstance(msg, dict) and msg.get("role") != "user" and msg.get("content", "").strip():
                # Only include messages after the initial user message
                if i > len(initial_messages) - 1:  # Skip initial messages including the user's query
                    agent_name = msg.get("name", "Assistant")
                    content = msg.get("content", "")
                    
                    # Add to response if it's not empty
                    if content.strip():
                        # Format content nicely depending on query type
                        final_content = content
                        
                        # For research queries, ensure the response is well-formatted
                        if is_research_query and len(content) > 300 and "\n\n" not in content:
                            # Break long text into paragraphs if needed
                            sentences = content.split(". ")
                            paragraphs = []
                            current_paragraph = []
                            
                            for sentence in sentences:
                                current_paragraph.append(sentence)
                                if len(". ".join(current_paragraph)) > 150:
                                    paragraphs.append(". ".join(current_paragraph) + ".")
                                    current_paragraph = []
                            
                            if current_paragraph:
                                paragraphs.append(". ".join(current_paragraph) + ".")
                                
                            final_content = "\n\n".join(paragraphs)
                            
                        response_messages.append({
                            "role": "assistant",
                            "name": agent_name,
                            "content": final_content
                        })
        
        # If no response was generated, provide a helpful default response
        if not response_messages:
            if is_research_query:
                response_messages.append({
                    "role": "assistant",
                    "name": "Researcher",
                    "content": "I understand you've asked about: \"" + message + "\".\n\nI'd be happy to research this for you. Could you provide a bit more context about what specific aspects you're interested in?"
                })
            else:
                response_messages.append({
                    "role": "assistant",
                    "name": "Assistant",
                    "content": "Hello! How can I assist you today? Feel free to ask me any questions or request information on a topic you're interested in."
                })
        
        return response_messages
        
    except Exception as e:
        logger.error(f"Error in chat workflow: {str(e)}", exc_info=True)
        return [{
            "role": "assistant",
            "name": "System",
            "content": f"An error occurred: {str(e)}. Please try again or check your configuration."
        }] 