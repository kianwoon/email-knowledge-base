/**
 * Basic chat message type shared across the application
 */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

/**
 * Structured tool response type for MCP tools
 */
export interface McpToolResponse {
  text: string;
  toolResults?: any;
}

/**
 * Extended chat message type that can handle complex tool responses
 */
export interface ExtendedChatMessage {
  role: 'user' | 'assistant';
  content: string | McpToolResponse;
} 