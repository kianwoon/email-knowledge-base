import axios from 'axios';

// Types for MCP Tools
export interface MCPTool {
  id?: number;
  name: string;
  description: string;
  parameters: Record<string, any>;
  entrypoint: string;
  version: string;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface MCPToolCreate {
  name: string;
  description: string;
  parameters: Record<string, any>;
  entrypoint: string;
  version: string;
  enabled: boolean;
}

// Get all MCP tools for the current user
export const listMCPTools = async (): Promise<MCPTool[]> => {
  const response = await axios.get('/api/v1/mcp/mcp/tools');
  return response.data;
};

// Get a specific MCP tool by ID
export const getMCPTool = async (id: number): Promise<MCPTool> => {
  const response = await axios.get(`/api/v1/mcp/mcp/tools/${id}`);
  return response.data;
};

// Create a new MCP tool
export const createMCPTool = async (toolData: MCPToolCreate): Promise<MCPTool> => {
  const response = await axios.post('/api/v1/mcp/mcp/tools', toolData);
  return response.data;
};

// Update an existing MCP tool
export const updateMCPTool = async (id: number, toolData: Partial<MCPToolCreate>): Promise<MCPTool> => {
  const response = await axios.put(`/api/v1/mcp/mcp/tools/${id}`, toolData);
  return response.data;
};

// Delete an MCP tool
export const deleteMCPTool = async (id: number): Promise<void> => {
  await axios.delete(`/api/v1/mcp/mcp/tools/${id}`);
};

// Toggle the enabled status of an MCP tool
export const toggleMCPToolStatus = async (id: number, enabled: boolean): Promise<MCPTool> => {
  const response = await axios.patch(`/api/v1/mcp/mcp/tools/${id}/status`, { enabled });
  return response.data;
}; 