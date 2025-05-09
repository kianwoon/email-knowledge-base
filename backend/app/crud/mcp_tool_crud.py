from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.db.models.mcp_tool import MCPToolDB
from app.schemas.mcp_tool import MCPToolCreate, MCPToolUpdate

logger = logging.getLogger(__name__)

def get_mcp_tools(db: Session, user_email: str) -> List[MCPToolDB]:
    """Get all MCP tools for a user."""
    return db.query(MCPToolDB).filter(MCPToolDB.user_email == user_email).all()

def get_mcp_tool(db: Session, tool_id: int, user_email: str) -> Optional[MCPToolDB]:
    """Get a specific MCP tool by ID."""
    return db.query(MCPToolDB).filter(
        MCPToolDB.id == tool_id,
        MCPToolDB.user_email == user_email
    ).first()

def get_mcp_tool_by_name(db: Session, name: str, user_email: str) -> Optional[MCPToolDB]:
    """Get a specific MCP tool by name."""
    return db.query(MCPToolDB).filter(
        MCPToolDB.name == name,
        MCPToolDB.user_email == user_email
    ).first()

def create_mcp_tool(db: Session, tool: MCPToolCreate, user_email: str) -> MCPToolDB:
    """Create a new MCP tool."""
    try:
        # Log the incoming tool data
        logger.info(f"Creating MCP tool: name={tool.name}, description={tool.description}, user={user_email}")
        
        # Check for duplicate name
        existing_tool = get_mcp_tool_by_name(db, tool.name, user_email)
        if existing_tool:
            raise ValueError(f"A tool with name '{tool.name}' already exists")
        
        # Log the data just before creating the database object
        logger.info(f"Tool data validated, creating DB object with name={tool.name}, description={tool.description}, parameters={tool.parameters}")
        
        # Create new tool
        db_tool = MCPToolDB(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            entrypoint=tool.entrypoint,
            version=tool.version,
            enabled=tool.enabled,
            user_email=user_email
        )
        
        # Log the db object after creation
        logger.info(f"Created DB object: name={db_tool.name}, description={db_tool.description}")
        
        db.add(db_tool)
        db.commit()
        db.refresh(db_tool)
        
        # Log the final object after commit and refresh
        logger.info(f"Saved MCP tool to database: id={db_tool.id}, name={db_tool.name}, description={db_tool.description}")
        
        return db_tool
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating MCP tool for user {user_email}: {e}", exc_info=True)
        raise

def update_mcp_tool(db: Session, tool_id: int, tool: MCPToolUpdate, user_email: str) -> Optional[MCPToolDB]:
    """Update an existing MCP tool."""
    try:
        db_tool = get_mcp_tool(db, tool_id, user_email)
        if not db_tool:
            return None
        
        # Update fields if provided
        if tool.name is not None:
            # Check if name is changing and if new name already exists
            if tool.name != db_tool.name:
                existing_tool = get_mcp_tool_by_name(db, tool.name, user_email)
                if existing_tool:
                    raise ValueError(f"A tool with name '{tool.name}' already exists")
            db_tool.name = tool.name
            
        if tool.description is not None:
            db_tool.description = tool.description
        if tool.parameters is not None:
            db_tool.parameters = tool.parameters
        if tool.entrypoint is not None:
            db_tool.entrypoint = tool.entrypoint
        if tool.version is not None:
            db_tool.version = tool.version
        if tool.enabled is not None:
            db_tool.enabled = tool.enabled
        
        db.commit()
        db.refresh(db_tool)
        return db_tool
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating MCP tool {tool_id} for user {user_email}: {e}", exc_info=True)
        raise

def delete_mcp_tool(db: Session, tool_id: int, user_email: str) -> bool:
    """Delete an MCP tool."""
    try:
        db_tool = get_mcp_tool(db, tool_id, user_email)
        if not db_tool:
            return False
        
        db.delete(db_tool)
        db.commit()
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error deleting MCP tool {tool_id} for user {user_email}: {e}", exc_info=True)
        raise

def update_mcp_tool_status(db: Session, tool_id: int, enabled: bool, user_email: str) -> Optional[MCPToolDB]:
    """Update the enabled status of an MCP tool."""
    try:
        db_tool = get_mcp_tool(db, tool_id, user_email)
        if not db_tool:
            return None
        
        db_tool.enabled = enabled
        db.commit()
        db.refresh(db_tool)
        return db_tool
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating MCP tool status {tool_id} for user {user_email}: {e}", exc_info=True)
        raise 