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

/**
 * Determine if a query might be a good candidate for MCP tools
 */
export const shouldUseMcpTools = (message: string): { use: boolean, tools: string[] } => {
  // Logic to determine if this query is for MCP tools
  const jiraPattern = /\b(jira|issue|ticket|task|bug|project|sprint|backlog|todo|to-do|to do)\b/i;
  const outlookPattern = /outlook|email|mail|calendar|meeting|schedule|appointment|message|invite/i;
  
  console.log(`Checking if message "${message}" matches MCP patterns. Jira pattern: ${jiraPattern}`);
  
  let tools = [];
  if (jiraPattern.test(message)) {
    console.log(`✅ Jira pattern matched in message: "${message}"`);
    tools.push('jira_list_issues', 'jira_create_issue');
  } else {
    console.log(`❌ Jira pattern did NOT match in message: "${message}" (Pattern: ${jiraPattern})`);
  }
  
  if (outlookPattern.test(message)) {
    console.log(`✅ Outlook pattern matched in message: "${message}"`);
    tools.push('outlook_list_events', 'outlook_create_event', 
               'outlook_list_messages', 'outlook_send_message');
  } else {
    console.log(`❌ Outlook pattern did NOT match in message: "${message}" (Pattern: ${outlookPattern})`);
  }
  
  const result = { 
    use: tools.length > 0,
    tools
  };
  
  console.log(`shouldUseMcpTools result: ${result.use ? 'true' : 'false'}, tools: [${result.tools.join(', ')}] for message: "${message}"`);
  return result;
}; 