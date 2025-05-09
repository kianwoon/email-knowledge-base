from fastapi import APIRouter, Depends, HTTPException, status, Path, Body, Request
from sqlalchemy.orm import Session
from typing import List
import logging
import time

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user, User
from app.schemas.mcp_tool import MCPTool, MCPToolCreate, MCPToolUpdate, MCPToolStatusUpdate, EXAMPLE_PARAMETERS_SCHEMA
from app.crud import mcp_tool_crud

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/mcp/tools",
    tags=["MCP Tools"],
    responses={404: {"description": "Not found"}}
)

# GET all tools - without trailing slash
@router.get("", response_model=List[MCPTool])
async def get_mcp_tools_no_slash(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all MCP tools for the current user (endpoint without trailing slash)."""
    try:
        tools = mcp_tool_crud.get_mcp_tools(db, current_user.email)
        return tools
    except Exception as e:
        logger.error(f"Error getting MCP tools for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting MCP tools: {str(e)}")

# GET all tools - with trailing slash
@router.get("/", response_model=List[MCPTool])
async def get_mcp_tools(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all MCP tools for the current user."""
    try:
        tools = mcp_tool_crud.get_mcp_tools(db, current_user.email)
        return tools
    except Exception as e:
        logger.error(f"Error getting MCP tools for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting MCP tools: {str(e)}")

@router.get("/{tool_id}", response_model=MCPTool)
async def get_mcp_tool(
    tool_id: int = Path(..., title="The ID of the MCP tool to get"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific MCP tool by ID."""
    try:
        tool = mcp_tool_crud.get_mcp_tool(db, tool_id, current_user.email)
        if not tool:
            raise HTTPException(status_code=404, detail="MCP tool not found")
        return tool
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP tool {tool_id} for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting MCP tool: {str(e)}")

# Create MCP tool - without trailing slash
@router.post("", response_model=MCPTool, status_code=status.HTTP_201_CREATED)
async def create_mcp_tool_no_slash(
    tool: MCPToolCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new MCP tool (endpoint without trailing slash)."""
    try:
        db_tool = mcp_tool_crud.create_mcp_tool(db, tool, current_user.email)
        return db_tool
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating MCP tool for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating MCP tool: {str(e)}")

# Create MCP tool - with trailing slash
@router.post("/", response_model=MCPTool, status_code=status.HTTP_201_CREATED)
async def create_mcp_tool(
    request: Request,
    tool: MCPToolCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new MCP tool."""
    try:
        # Log raw request data for debugging
        raw_data = await request.json()
        logger.info(f"Raw request data: {raw_data}")
        
        # Log Pydantic model data
        logger.info(f"Pydantic model data: name='{tool.name}', description='{tool.description}'")
        logger.info(f"Tool data dict: {tool.model_dump()}")
        
        db_tool = mcp_tool_crud.create_mcp_tool(db, tool, current_user.email)
        return db_tool
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating MCP tool for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating MCP tool: {str(e)}")

# Update MCP tool
@router.put("/{tool_id}", response_model=MCPTool)
async def update_mcp_tool(
    tool_id: int = Path(..., title="The ID of the MCP tool to update"),
    tool: MCPToolUpdate = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update an existing MCP tool."""
    try:
        db_tool = mcp_tool_crud.update_mcp_tool(db, tool_id, tool, current_user.email)
        if not db_tool:
            raise HTTPException(status_code=404, detail="MCP tool not found")
        return db_tool
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating MCP tool {tool_id} for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating MCP tool: {str(e)}")

# Delete MCP tool
@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_tool(
    tool_id: int = Path(..., title="The ID of the MCP tool to delete"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an MCP tool."""
    try:
        success = mcp_tool_crud.delete_mcp_tool(db, tool_id, current_user.email)
        if not success:
            raise HTTPException(status_code=404, detail="MCP tool not found")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting MCP tool {tool_id} for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting MCP tool: {str(e)}")

# Update MCP tool status
@router.patch("/{tool_id}/status", response_model=MCPTool)
async def update_mcp_tool_status(
    tool_id: int = Path(..., title="The ID of the MCP tool to update"),
    status_update: MCPToolStatusUpdate = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update the enabled status of an MCP tool."""
    try:
        db_tool = mcp_tool_crud.update_mcp_tool_status(db, tool_id, status_update.enabled, current_user.email)
        if not db_tool:
            raise HTTPException(status_code=404, detail="MCP tool not found")
        return db_tool
    except Exception as e:
        logger.error(f"Error updating MCP tool status {tool_id} for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating MCP tool status: {str(e)}")

# Add an endpoint to get an example template
@router.get("/example", response_model=MCPToolCreate)
async def get_mcp_tool_example():
    """Get an example MCP tool template to use as reference."""
    example_tool = MCPToolCreate(
        name="example.hello_world",
        description="A simple example tool that demonstrates the required format",
        parameters=EXAMPLE_PARAMETERS_SCHEMA,
        entrypoint="/api/example/hello-world"
    )
    return example_tool

# Add documentation endpoint with complete JSON example
@router.get("/docs/example")
async def get_mcp_tool_docs_example():
    """Get a complete JSON example with explanation for creating an MCP tool."""
    return {
        "example_json": {
            "name": "jira.create_issue",
            "description": "Creates a new issue in Jira",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Issue summary/title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Issue description"
                    },
                    "project_key": {
                        "type": "string",
                        "description": "Jira project key"
                    },
                    "issue_type": {
                        "type": "string", 
                        "description": "Type of issue",
                        "default": "Task"
                    }
                },
                "required": ["summary", "project_key"]
            },
            "entrypoint": "/integrations/jira/create-issue",
            "version": "1.0",
            "enabled": true
        },
        "notes": "The 'parameters' field must be a valid JSON Schema with 'type': 'object', 'properties' object, and 'required' array. Even if empty, these fields must be present."
    }

# Add a debug endpoint for creating a test tool
@router.post("/debug/test-tool", response_model=MCPTool)
async def create_test_tool(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to create a test tool with hardcoded values."""
    try:
        # Generate a unique name with timestamp to avoid conflicts
        timestamp = int(time.time())
        
        test_tool = MCPToolCreate(
            name=f"test.debug.tool.{timestamp}",
            description=f"Debug test tool created at {timestamp}",
            parameters={
                "type": "object",
                "properties": {
                    "debug_param": {
                        "type": "string",
                        "description": "Debug parameter"
                    }
                },
                "required": ["debug_param"]
            },
            entrypoint="/debug/test-endpoint",
            version="1.0",
            enabled=True
        )
        
        logger.info(f"Creating debug test tool with name={test_tool.name}, description={test_tool.description}")
        
        db_tool = mcp_tool_crud.create_mcp_tool(db, test_tool, current_user.email)
        return db_tool
    except Exception as e:
        logger.error(f"Error creating debug test tool: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating debug test tool: {str(e)}")

# Add a raw debug endpoint that bypasses Pydantic
@router.post("/debug/raw-tool", status_code=status.HTTP_201_CREATED)
async def create_raw_tool(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint that creates a tool directly using SQLAlchemy model."""
    try:
        timestamp = int(time.time())
        test_name = f"raw.debug.tool.{timestamp}"
        test_description = f"Raw debug tool created at {timestamp} without Pydantic"
        
        logger.info(f"Creating raw debug tool with name={test_name}, description={test_description}")
        
        # Create directly using the SQLAlchemy model
        db_tool = MCPToolDB(
            name=test_name,
            description=test_description,
            parameters={
                "type": "object",
                "properties": {
                    "raw_param": {
                        "type": "string",
                        "description": "Raw test parameter"
                    }
                },
                "required": ["raw_param"]
            },
            entrypoint="/debug/raw-endpoint",
            version="1.0",
            enabled=True,
            user_email=current_user.email
        )
        
        logger.info(f"Raw tool object created: name={db_tool.name}, description={db_tool.description}")
        
        # Add to session and commit
        db.add(db_tool)
        db.commit()
        db.refresh(db_tool)
        
        logger.info(f"Raw tool saved to database: id={db_tool.id}, name={db_tool.name}, description={db_tool.description}")
        
        # Return as a dictionary since we're not using response_model here
        return {
            "id": db_tool.id,
            "name": db_tool.name,
            "description": db_tool.description,
            "parameters": db_tool.parameters,
            "entrypoint": db_tool.entrypoint,
            "version": db_tool.version,
            "enabled": db_tool.enabled,
            "created_at": db_tool.created_at,
            "updated_at": db_tool.updated_at
        }
        
    except Exception as e:
        logger.error(f"Error creating raw debug tool: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating raw debug tool: {str(e)}")

# Add a debug endpoint to log the raw request body
@router.post("/debug/log-request")
async def log_request_body(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Debug endpoint that logs the raw request body."""
    try:
        body = await request.json()
        logger.info(f"Raw request body: {body}")
        logger.info(f"Request headers: {request.headers}")
        return {"message": "Request logged", "body": body}
    except Exception as e:
        logger.error(f"Error logging request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error logging request: {str(e)}")

# Add a debug endpoint to check the database
@router.get("/debug/check-db")
async def check_db(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to directly check the database table."""
    try:
        # Directly query the database table
        all_tools = db.query(MCPToolDB).filter(MCPToolDB.user_email == current_user.email).all()
        
        # Convert to a list of dictionaries for JSON serialization
        result = []
        for tool in all_tools:
            result.append({
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "entrypoint": tool.entrypoint,
                "version": tool.version,
                "enabled": tool.enabled,
                "created_at": tool.created_at,
                "updated_at": tool.updated_at
            })
        
        return {
            "count": len(result),
            "tools": result
        }
        
    except Exception as e:
        logger.error(f"Error checking database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error checking database: {str(e)}") 