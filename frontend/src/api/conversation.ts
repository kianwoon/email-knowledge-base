import { apiClient } from './client';

// Types for conversation-related operations
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agentName?: string;
  timestamp: Date;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  maxRounds: number;
  agentsConfig: any[];
}

export interface ConversationCreate {
  title: string;
  maxRounds: number;
}

export interface ConversationUpdate {
  title?: string;
  maxRounds?: number;
}

// Get all conversations for the current user
export const getUserConversations = async (): Promise<Conversation[]> => {
  const response = await apiClient.get('/conversations/');
  return response.data;
};

// Get a specific conversation by ID
export const getConversationById = async (id: string): Promise<Conversation> => {
  const response = await apiClient.get(`/conversations/${id}`);
  return response.data;
};

// Create a new conversation
export const createConversation = async (conversation: ConversationCreate): Promise<Conversation> => {
  const response = await apiClient.post('/conversations/', conversation);
  return response.data;
};

// Update an existing conversation
export const updateConversation = async (id: string, updates: ConversationUpdate): Promise<Conversation> => {
  const response = await apiClient.put(`/conversations/${id}`, updates);
  return response.data;
};

// Delete a conversation
export const deleteConversation = async (id: string): Promise<void> => {
  await apiClient.delete(`/conversations/${id}`);
};

// Add a message to a conversation
export const addMessageToConversation = async (conversationId: string, message: Omit<Message, 'id' | 'timestamp'>): Promise<Message> => {
  const response = await apiClient.post(`/conversations/${conversationId}/messages`, message);
  return response.data;
}; 