import mcpClient from './mcpClient';
import axios from 'axios';

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

/**
 * Send a specific tool invocation request to the MCP server.
 */
export const sendMcpMessage = async (
  // OLD PARAMS REMOVED: message: string, history: ChatMessage[], model: string, toolNames: string[]
  // NEW PARAM: Structured tool call payload
  toolCallPayload: { name: string; arguments: Record<string, any> } 
): Promise<string | McpToolResponse> => {
  try {
    // Log the specific tool being invoked
    console.log(`Invoking MCP tool: ${toolCallPayload.name} with arguments:`, toolCallPayload.arguments); 
    
    // Send the structured payload directly to the /invoke endpoint
    const response = await mcpClient.post('/invoke', toolCallPayload); // Send the payload directly
    
    // Existing response handling...
    console.log('Received response from MCP server:', typeof response.data);
    return response.data;
  } catch (error) {
    console.error(`Error invoking MCP tool ${toolCallPayload?.name || '(unknown)'}:`, error); // Improved error logging
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        throw new Error("MCP endpoint not found. Please check your MCP server configuration.");
      }
      throw new Error(`MCP service error: ${error.response?.data?.detail || error.message}`);
    }
    throw error;
  }
};

// The shouldUseMcpTools function (lines 40-68) has been removed.
// THIS LINE SHOULD BE EMPTY AFTER REMOVAL 