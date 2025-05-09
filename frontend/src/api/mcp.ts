import mcpClient from './mcpClient';
import axios from 'axios';
import { useToast } from '@chakra-ui/react';

// Basic chat message type (matching the one used in JarvisPage)
export type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

// Define types for MCP tool responses
export type McpToolResponse = {
  text: string;
  toolResults?: any;
};

// Authentication error response
export type McpAuthError = {
  status: 'error';
  error_type: 'authentication';
  message: string;
  requires_auth: true;
  auth_service: string;
  callback_endpoint?: string;
};

/**
 * Send a specific tool invocation request to the MCP server.
 * @throws {AuthenticationError} When a tool requires authentication
 */
export const sendMcpMessage = async (
  // OLD PARAMS REMOVED: message: string, history: ChatMessage[], model: string, toolNames: string[]
  // NEW PARAM: Structured tool call payload
  toolCallPayload: { name: string; arguments: Record<string, any> } 
): Promise<string | McpToolResponse> => {
  try {
    // Log the specific tool being invoked
    console.log(`Invoking MCP tool: ${toolCallPayload.name} with arguments:`, toolCallPayload.arguments); 
    
    // Use the internal API for tool execution instead of MCP server directly
    const response = await axios.post('/api/v1/tool/tools/execute', toolCallPayload);
    
    // Check for authentication errors
    const data = response.data;
    if (data && data.status === 'error' && data.error_type === 'authentication') {
      console.warn('Authentication error from tool:', data);
      throw new AuthenticationError(
        data.message || 'Authentication required',
        data.auth_service,
        data.callback_endpoint
      );
    }
    
    // Return the response data
    console.log('Received response from tool execution:', typeof data);
    return data;
  } catch (error) {
    // Re-throw authentication errors
    if (error instanceof AuthenticationError) {
      throw error;
    }
    
    // Handle other errors
    console.error(`Error invoking MCP tool ${toolCallPayload?.name || '(unknown)'}:`, error);
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        throw new Error("Tool endpoint not found. Please check your configuration.");
      }
      throw new Error(`Tool execution error: ${error.response?.data?.detail || error.message}`);
    }
    throw error;
  }
};

/**
 * Custom error class for authentication errors.
 */
export class AuthenticationError extends Error {
  service: string;
  callbackEndpoint?: string;
  
  constructor(message: string, service: string, callbackEndpoint?: string) {
    super(message);
    this.name = 'AuthenticationError';
    this.service = service;
    this.callbackEndpoint = callbackEndpoint;
  }
}

/**
 * Hook to check authentication status for a service
 */
export const checkAuthStatus = async (service: string): Promise<boolean> => {
  try {
    const response = await axios.get(`/api/v1/tool/tools/auth-status/${service}`);
    return response.data.authenticated;
  } catch (error) {
    console.error(`Error checking auth status for ${service}:`, error);
    return false;
  }
};

/**
 * Redirect to the appropriate authorization page
 */
export const initiateAuth = (service: string): void => {
  if (service === 'microsoft') {
    window.location.href = '/api/v1/auth/microsoft/login';
  } else if (service === 'jira') {
    window.location.href = '/api/v1/auth/jira/login';
  } else {
    console.error(`Unknown authentication service: ${service}`);
  }
};

// The shouldUseMcpTools function (lines 40-68) has been removed.
// THIS LINE SHOULD BE EMPTY AFTER REMOVAL 