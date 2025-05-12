import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.models.user import User
from app.db.session import get_db
from app.dependencies.auth import get_current_active_user
from app.autogen.workflows import (
    run_research_workflow, 
    run_code_generation_workflow, 
    run_qa_workflow,
    run_chat_workflow
)

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Pydantic Models for Request/Response ---

class ResearchRequest(BaseModel):
    query: str = Field(..., description="Research question to investigate")
    model_id: Optional[str] = Field(None, description="Optional model ID to use")
    max_rounds: Optional[int] = Field(15, description="Maximum conversation rounds")
    temperature: Optional[float] = Field(0.5, description="Temperature for LLM")

class ResearchResponse(BaseModel):
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages")
    summary: Dict[str, Any] = Field(..., description="Summary of research findings")

class CodeGenRequest(BaseModel):
    task_description: str = Field(..., description="Description of the coding task")
    model_id: Optional[str] = Field(None, description="Optional model ID to use")
    max_rounds: Optional[int] = Field(10, description="Maximum conversation rounds")
    temperature: Optional[float] = Field(0.2, description="Temperature for LLM")
    work_dir: Optional[str] = Field("workspace", description="Working directory for code execution")

class CodeGenResponse(BaseModel):
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages")
    output_path: str = Field(..., description="Path to the generated code")

class QARequest(BaseModel):
    question: str = Field(..., description="Question to answer")
    context: List[str] = Field(..., description="List of context passages")
    model_id: Optional[str] = Field(None, description="Optional model ID to use")
    temperature: Optional[float] = Field(0.3, description="Temperature for LLM")

class QAResponse(BaseModel):
    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="Generated answer")
    context_used: List[str] = Field(..., description="Context used for answering")
    confidence: str = Field(..., description="Confidence level (high/low)")

# New models for agent-based chat
class AgentConfig(BaseModel):
    name: str = Field(..., description="Name of the agent")
    type: str = Field(..., description="Type of agent (assistant, researcher, coder, critic, custom)")
    system_message: str = Field(..., description="System message defining the agent's behavior")

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    model_id: Optional[str] = Field(None, description="Optional model ID to use")
    temperature: Optional[float] = Field(0.7, description="Temperature for LLM")
    history: Optional[List[Dict[str, Any]]] = Field([], description="Previous conversation history")
    agents: List[AgentConfig] = Field(..., description="List of custom agents to use in the conversation")
    max_rounds: Optional[int] = Field(5, description="Maximum conversation rounds")

class ChatResponse(BaseModel):
    messages: List[Dict[str, Any]] = Field(..., description="Agent messages in response to the query")

# --- API Endpoints ---

@router.post("/research", response_model=ResearchResponse, status_code=status.HTTP_200_OK)
async def research_endpoint(
    request: ResearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Run a multi-agent research workflow on a given query.
    
    This creates a team of specialized AI agents:
    - Researcher: Gathers information and provides facts
    - Critic: Evaluates the research, identifies biases and gaps
    - Synthesizer: Integrates information into a coherent whole
    
    The agents discuss the topic and produce a comprehensive summary.
    """
    try:
        logger.info(f"Research request from user {current_user.email}: {request.query}")
        
        messages, summary = await run_research_workflow(
            query=request.query,
            user=current_user,
            db=db,
            model_id=request.model_id,
            max_rounds=request.max_rounds,
            temperature=request.temperature
        )
        
        return ResearchResponse(
            messages=messages,
            summary=summary
        )
    except Exception as e:
        logger.error(f"Error in research workflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research workflow failed: {str(e)}"
        )

@router.post("/code-generation", response_model=CodeGenResponse, status_code=status.HTTP_200_OK)
async def code_generation_endpoint(
    request: CodeGenRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Run a multi-agent code generation workflow.
    
    This creates a team of specialized AI agents:
    - Architect: Designs the high-level solution
    - Coder: Implements the code
    - Tester: Reviews code and suggests improvements
    
    The agents collaborate to produce working code for the given task.
    """
    try:
        logger.info(f"Code generation request from user {current_user.email}: {request.task_description}")
        
        messages, output_path = await run_code_generation_workflow(
            task_description=request.task_description,
            user=current_user,
            db=db,
            model_id=request.model_id,
            max_rounds=request.max_rounds,
            temperature=request.temperature,
            work_dir=request.work_dir
        )
        
        return CodeGenResponse(
            messages=messages,
            output_path=output_path
        )
    except Exception as e:
        logger.error(f"Error in code generation workflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation workflow failed: {str(e)}"
        )

@router.post("/qa", response_model=QAResponse, status_code=status.HTTP_200_OK)
async def qa_endpoint(
    request: QARequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Run a question-answering workflow using the provided context.
    
    This creates a specialized QA agent that uses the given context
    to answer the question. The agent will only use information from
    the context and will indicate if the context doesn't contain the
    necessary information.
    """
    try:
        logger.info(f"QA request from user {current_user.email}: {request.question}")
        
        result = await run_qa_workflow(
            question=request.question,
            context=request.context,
            user=current_user,
            db=db,
            model_id=request.model_id,
            temperature=request.temperature
        )
        
        return QAResponse(
            question=result["question"],
            answer=result["answer"],
            context_used=result["context_used"],
            confidence=result["confidence"]
        )
    except Exception as e:
        logger.error(f"Error in QA workflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"QA workflow failed: {str(e)}"
        )

@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Run a multi-agent chat workflow with custom agent configurations.
    
    This creates a team of AI agents based on the provided configurations.
    The agents discuss and respond to the user's message.
    """
    try:
        logger.info(f"Chat request from user {current_user.email}: {request.message}")
        logger.info(f"Using {len(request.agents)} agents for chat")
        
        # Use a smaller max_rounds value to avoid indefinite conversations
        max_rounds = min(request.max_rounds if hasattr(request, 'max_rounds') else 5, 10)
        
        messages = await run_chat_workflow(
            message=request.message,
            user=current_user,
            db=db,
            model_id=request.model_id,
            temperature=request.temperature,
            history=request.history,
            agents=request.agents,
            max_rounds=max_rounds
        )
        
        return ChatResponse(
            messages=messages
        )
    except Exception as e:
        logger.error(f"Error in chat workflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat workflow failed: {str(e)}"
        )

@router.get("/status", status_code=status.HTTP_200_OK)
async def check_autogen_status(
    current_user: User = Depends(get_current_active_user)
):
    """
    Check the status of AutoGen module and its dependencies.
    """
    try:
        # Report that AutoGen is temporarily disabled
        return {
            "status": "maintenance",
            "version": "0.1.0",
            "user": current_user.email,
            "features": [],
            "message": "AutoGen is temporarily disabled due to compatibility issues between AutoGen and OpenAI packages. The feature will be restored in a future update."
        }
    except Exception as e:
        logger.error(f"Error checking AutoGen status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AutoGen status check failed: {str(e)}"
        ) 