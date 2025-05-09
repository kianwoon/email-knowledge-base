import apiClient from './apiClient';
import { AxiosError } from 'axios';
// Import the MODIFIED sendMcpMessage and other types
import { sendMcpMessage, ChatMessage as McpChatMessage, McpToolResponse, AuthenticationError, initiateAuth } from './mcp';

// Define request body structure for Phase 1 and Phase 3
interface BackendChatRequestPayload {
  message: string;
  chat_history?: Array<{ role: string; content: string }>;
  model_id?: string;
  tool_results?: Array<{ call_id: string; name: string; result: any }>; // For Phase 3
}

// Define response structure from Phase 1
interface BackendPhase1Response {
  type: 'text' | 'tool_call';
  reply?: string; // If type is 'text'
  tool_calls?: Array<{ call_id: string; name: string; arguments: Record<string, any> }>; // If type is 'tool_call'
}

// Define response structure from Phase 3 (always text)
interface BackendPhase3Response {
  type: 'text'; // Should always be text after synthesis
  reply: string;
}

// Auth-related states and types
type AuthRequiredInfo = {
  service: string;
  message: string;
};

/**
 * Sends a chat message to the backend, managing the three-phase tool calling process.
 * @returns A string response or throws an AuthRequiredError if authentication is needed
 */
export const sendChatMessage = async (
  message: string,
  chatHistory?: Array<McpChatMessage>,
  modelId?: string
): Promise<string> => {
  try {
    // --- Phase 1: Tool Call Decision ---
    console.log("[Phase 1] Sending message to backend for tool decision...");
    const phase1Payload: BackendChatRequestPayload = {
      message,
      chat_history: chatHistory,
      model_id: modelId,
    };

    // Assume the primary chat endpoint is /v1/chat/ for now
    // This endpoint needs to be updated on the backend to support the new flow
    const phase1Response = await apiClient.post<BackendPhase1Response>('/v1/chat/', phase1Payload);
    const phase1Data = phase1Response.data;

    console.log("[Phase 1] Received response:", phase1Data);

    if (phase1Data.type === 'text') {
      // LLM decided no tool was needed, or it's a direct answer
      console.log("[Phase 1] Direct text response received.");
      return phase1Data.reply || "Received an empty reply.";
    }

    if (phase1Data.type === 'tool_call' && phase1Data.tool_calls && phase1Data.tool_calls.length > 0) {
      console.log("[Phase 2] Tool call(s) requested by backend:", phase1Data.tool_calls);
      const toolResults: Array<{ call_id: string; name: string; result: any }> = [];

      // --- Phase 2: Tool Execution ---
      let authError: AuthenticationError | null = null;
      
      for (const toolCall of phase1Data.tool_calls) {
        console.log(`[Phase 2] Executing tool: ${toolCall.name} (Call ID: ${toolCall.call_id})`);
        try {
          // sendMcpMessage now directly calls /invoke with { name, arguments }
          const mcpToolRawResult = await sendMcpMessage({
            name: toolCall.name,
            arguments: toolCall.arguments,
          });
          console.log(`[Phase 2] Raw result for ${toolCall.name} (Call ID: ${toolCall.call_id}):`, mcpToolRawResult);
          toolResults.push({
            call_id: toolCall.call_id,
            name: toolCall.name,
            result: mcpToolRawResult,
          });
        } catch (toolExecError) {
          console.error(`[Phase 2] Error executing tool ${toolCall.name} (Call ID: ${toolCall.call_id}):`, toolExecError);
          
          // Check for authentication errors specifically
          if (toolExecError instanceof AuthenticationError) {
            // Store the authentication error for later handling
            authError = toolExecError;
            // Add a placeholder result indicating auth required
            toolResults.push({
              call_id: toolCall.call_id,
              name: toolCall.name,
              result: { 
                error: "Authentication required",
                auth_service: toolExecError.service,
                requires_auth: true,
                message: toolExecError.message
              },
            });
          } else {
            // Normal error handling
            toolResults.push({
              call_id: toolCall.call_id,
              name: toolCall.name,
              result: { error: `Failed to execute tool: ${(toolExecError as Error).message}` },
            });
          }
        }
      }

      // If we encountered an auth error, throw it after collecting all results
      // This allows the UI to present the auth requirement to the user
      if (authError) {
        throw new AuthRequiredError(
          authError.message || "Authentication required to complete this request",
          authError.service
        );
      }

      // --- Phase 3: Final Response Generation ---
      if (toolResults.length > 0) {
        console.log("[Phase 3] Sending tool results back to backend for final response...");
        const phase3Payload: BackendChatRequestPayload = {
          message, // Original message
          chat_history: chatHistory, // Original history
          model_id: modelId,
          tool_results: toolResults,
        };

        // Call the same backend endpoint, now with tool_results
        const phase3Response = await apiClient.post<BackendPhase3Response>('/v1/chat/', phase3Payload);
        const phase3Data = phase3Response.data;

        console.log("[Phase 3] Received final response:", phase3Data);
        if (phase3Data.type === 'text') {
          return phase3Data.reply || "Received an empty final reply.";
        } else {
          console.error("[Phase 3] Expected a 'text' response but got:", phase3Data);
          return "Error: Did not receive the expected final text response from the AI.";
        }
      } else {
        // Should not happen if phase1Data.tool_calls was populated, but handle defensively
        console.warn("[Phase 2] No tool results were collected despite tool_calls being present.");
        return "An internal error occurred while processing tool calls (no results).";
      }
    }

    // Fallback if the response type from Phase 1 is unexpected
    console.warn("[Phase 1] Unexpected response type or empty tool_calls:", phase1Data);
    return "Received an unexpected response from the AI.";

  } catch (error) {
    // Re-throw AuthRequiredError for handling in UI
    if (error instanceof AuthRequiredError) {
      throw error;
    }
  
    console.error('Error in sendChatMessage multi-phase process:', error);
    const axiosError = error as AxiosError<{ detail?: string }>;
    if (axiosError.response?.data?.detail) {
      throw new Error(`Chat API Error: ${axiosError.response.data.detail}`);
    } else if (axiosError.isAxiosError) { // More robust check for AxiosError
        // Try to get more specific error from response if available
        const errorDetail = axiosError.response?.data?.detail || axiosError.response?.data || axiosError.message;
        throw new Error(`Chat service communication error: ${errorDetail}`);
    } else if (error instanceof Error) { // Standard JS error
      throw new Error(`Failed to get chat response: ${error.message}`);
    } else { // Unknown error type
      throw new Error('An unexpected error occurred during the chat process.');
    }
  }
};

/**
 * Custom error class for authentication requirements
 */
export class AuthRequiredError extends Error {
  service: string;
  
  constructor(message: string, service: string) {
    super(message);
    this.name = 'AuthRequiredError';
    this.service = service;
  }
}

/**
 * Handle authentication requirements
 * @returns A promise that resolves when the user has completed authentication
 */
export const handleAuthenticationRequired = async (authInfo: AuthRequiredInfo): Promise<void> => {
  // Could show a modal or UI element here before redirecting
  console.log(`Authentication required for service: ${authInfo.service}`);
  
  // Redirect to the appropriate auth endpoint
  initiateAuth(authInfo.service);
  
  // Return a never-resolving promise since we're redirecting away
  return new Promise<void>(() => {});
}; 