import { api } from './index';

// Types for agent-related operations
export interface Agent {
  id: string;
  name: string;
  type: 'assistant' | 'researcher' | 'coder' | 'critic' | 'custom';
  systemMessage: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface AgentCreate {
  name: string;
  type: 'assistant' | 'researcher' | 'coder' | 'critic' | 'custom';
  systemMessage: string;
}

// Get all agents for the current user
export const getUserAgents = async (): Promise<Agent[]> => {
  const response = await api.get('/api/v1/agents/');
  return response.data;
};

// Get a specific agent by ID
export const getAgentById = async (id: string): Promise<Agent> => {
  const response = await api.get(`/api/v1/agents/${id}`);
  return response.data;
};

// Create a new agent
export const createAgent = async (agent: AgentCreate): Promise<Agent> => {
  const response = await api.post('/api/v1/agents/', agent);
  return response.data;
};

// Update an existing agent
export const updateAgent = async (id: string, agent: Partial<AgentCreate>): Promise<Agent> => {
  const response = await api.put(`/api/v1/agents/${id}`, agent);
  return response.data;
};

// Delete an agent
export const deleteAgent = async (id: string): Promise<void> => {
  await api.delete(`/api/v1/agents/${id}`);
}; 