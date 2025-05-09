from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator
from datetime import datetime

# Example parameters schema to help users
EXAMPLE_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "A message to display"
        }
    },
    "required": ["message"]
}

# Default parameters schema structure
DEFAULT_PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": []
}

class MCPToolBase(BaseModel):
    """Base class for MCP Tool models."""
    name: str = Field(..., description="Tool name, e.g., jira.create_issue")
    description: Optional[str] = Field(None, description="Human-readable description of what the tool does")
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: DEFAULT_PARAMETERS_SCHEMA.copy(),
        description="JSON Schema for the tool parameters"
    )
    entrypoint: str = Field(..., description="Endpoint or function name to call when this tool is invoked")
    version: str = Field("1.0", description="Tool version for versioning")
    enabled: bool = Field(True, description="Whether the tool is currently enabled")

    @model_validator(mode='before')
    @classmethod
    def ensure_parameters_structure(cls, data):
        """Pre-validate and ensure parameters has the correct structure."""
        if isinstance(data, dict):
            # If parameters is empty, set default schema
            if "parameters" in data and (data["parameters"] is None or data["parameters"] == {}):
                data["parameters"] = DEFAULT_PARAMETERS_SCHEMA.copy()
            # If parameters exists but missing required fields, add them
            elif "parameters" in data and isinstance(data["parameters"], dict):
                params = data["parameters"]
                if "type" not in params:
                    params["type"] = "object"
                if "properties" not in params:
                    params["properties"] = {}
                if "required" not in params:
                    params["required"] = []
        return data

    @model_validator(mode='after')
    def check_parameters_schema(self) -> 'MCPToolBase':
        """Validate that parameters is a JSON schema object."""
        params = self.parameters
        if not isinstance(params, dict):
            raise ValueError("Parameters must be a dictionary")
        
        # Basic validation that it looks like a JSON schema
        if "type" not in params:
            params["type"] = "object"  # Add it if missing
        
        if params["type"] != "object":
            raise ValueError("Parameters must be a valid JSON schema with 'type': 'object'")
        
        if "properties" not in params:
            params["properties"] = {}  # Add it if missing
        
        if not isinstance(params["properties"], dict):
            raise ValueError("Parameters must include 'properties' as a dictionary")
        
        # Ensure required is present
        if "required" not in params:
            params["required"] = []
            
        return self

class MCPToolCreate(MCPToolBase):
    """Schema for creating a new MCP Tool."""
    pass

class MCPToolUpdate(BaseModel):
    """Schema for updating an existing MCP Tool."""
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    entrypoint: Optional[str] = None
    version: Optional[str] = None
    enabled: Optional[bool] = None

class MCPToolStatusUpdate(BaseModel):
    """Schema for updating the enabled status of an MCP Tool."""
    enabled: bool = Field(..., description="New enabled status")

class MCPTool(MCPToolBase):
    """Schema for a complete MCP Tool with DB attributes."""
    id: int
    user_email: str
    created_at: datetime
    updated_at: datetime

    class Config:
        """Configure Pydantic to work with SQLAlchemy models."""
        from_attributes = True 