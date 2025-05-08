import apiClient from './apiClient';
import { AxiosError } from 'axios';
// Import the MODIFIED sendMcpMessage and other types
import { sendMcpMessage, shouldUseMcpTools, ChatMessage as McpChatMessage, McpToolResponse } from './mcp';

// Define request body structure based on backend route
interface ChatRequestPayload {
  message: string;
  chat_history?: Array<{ role: string; content: string }>; // Basic types for chat history items
  model_id?: string; // Optional model ID to use for this message
}

// Define response structure based on backend route
interface ChatResponsePayload {
  reply: string;
}

// --- Placeholder for LLM-based Tool Call Generation ---
// In a real application, this would likely involve an LLM call
// (potentially via a dedicated backend endpoint) to determine the
// specific tool and arguments based on the message, history, and allowed tools.
async function generateToolCallPayload(
  message: string,
  chatHistory: Array<{ role: 'user' | 'assistant', content: string }> | undefined,
  toolNames: string[]
): Promise<{ name: string; arguments: Record<string, any> } | null> {
  console.warn("--- generateToolCallPayload ---");
  console.warn("This is a placeholder function.");
  console.warn("Input message:", message);
  console.warn("Allowed tools:", toolNames);

  // --- !!! Critical Missing Logic !!! ---
  // Here, you would typically:
  // 1. Format the message, history, and tool schemas for an LLM.
  // 2. Call an LLM (e.g., via a backend endpoint) with a prompt designed for function/tool calling.
  // 3. Instruct the LLM to choose ONE tool from 'toolNames' and generate the necessary arguments based on 'message'.
  // 4. Parse the LLM's response to extract the tool name and arguments.
  // 5. Validate the response against the tool schema from manifest.json (optional but recommended).
  // --- Example Placeholder Logic ---
  // This basic example just looks for keywords and creates a *hardcoded* JQL
  // A real implementation MUST use an LLM for flexibility.
  if (message.toLowerCase().includes("jira") && message.toLowerCase().includes("to do") && toolNames.includes("jira_list_issues")) {
    console.warn("Placeholder: Detected 'jira' and 'to do'. Generating hardcoded jira_list_issues call.");
    return {
      name: "jira_list_issues",
      arguments: {
        // THIS IS HARDCODED - LLM should generate this based on the message context
        jql: "status = 'To Do' ORDER BY created DESC"
      }
    };
  }
   // Add more placeholder logic for other tools/scenarios if needed for testing
   // else if (message.toLowerCase().includes("create jira issue") && ...) { ... }

  console.warn("Placeholder: Could not determine specific tool call from message.");
  return null; // Return null if no specific tool call could be generated
}
// --- End Placeholder ---


/**
 * Sends a chat message to the backend with intelligent routing.
 * Includes LLM step to generate specific tool calls for MCP.
 */
export const sendChatMessage = async (
  message: string,
  chatHistory?: Array<{ role: 'user' | 'assistant', content: string }>,
  modelId?: string // Keep modelId for potential use in tool generation LLM call
): Promise<string> => {
  try {
    // 1. Check if MCP tools *might* be relevant
    const mcpToolsCheck = shouldUseMcpTools(message);

    if (mcpToolsCheck.use) {
      console.log('Message appears potentially relevant for MCP tools, attempting tool call generation.');
      console.log(`Potential MCP tools: [${mcpToolsCheck.tools.join(', ')}]`);

      try {
        // 2. Generate the SPECIFIC tool call payload using LLM (Placeholder used here)
        const toolCallPayload = await generateToolCallPayload(
            message,
            chatHistory,
            mcpToolsCheck.tools
            // Potentially pass modelId here if the generation logic needs it
        );

        // 3. If a specific tool call was generated, execute it via MCP
        if (toolCallPayload) {
          console.log('Specific tool call generated:', toolCallPayload);
          console.log(`Attempting to invoke MCP tool: ${toolCallPayload.name}`);

          // Call the MODIFIED sendMcpMessage with the structured payload
          const mcpResponse = await sendMcpMessage(toolCallPayload);

          console.log('Received response from MCP server:', typeof mcpResponse);
          // ADDED: Log the actual response for debugging structure
          console.log('MCP Response Content:', JSON.stringify(mcpResponse).substring(0, 500));

          // Process MCP response - START
          // 1. Handle simple string response
          if (typeof mcpResponse === 'string') {
            return mcpResponse;
          }

          // 2. Handle structured object response
          if (typeof mcpResponse === 'object' && mcpResponse !== null) {
            
            // --- START: JIRA LIST ISSUES FORMATTING ---
            const toolResultData = (mcpResponse as any).result || (mcpResponse as any).toolResults?.result; // Use type assertion cautiously
            
            if (toolCallPayload.name === 'jira_list_issues' && toolResultData && Array.isArray(toolResultData.issues)) {
                console.log("Processing JIRA list issues response.");
                const issues = toolResultData.issues;
                if (issues.length === 0) {
                    return "No open Jira issues found matching your criteria.";
                }
                let reply = "Okay, here are the open Jira issues I found:\n";
                issues.forEach((issue: any) => { // Added : any type
                    const key = issue?.key ?? "N/A";
                    const summary = issue?.fields?.summary ?? "No summary";
                    const statusName = issue?.fields?.status?.name ?? "No status";
                    const assigneeName = issue?.fields?.assignee?.displayName ?? "Unassigned";
                    // Corrected template literal line endings
                    reply += `  - [${key}] ${summary} (Status: ${statusName}, Assignee: ${assigneeName})\n`; 
                });
                return reply.trim();
            }
            // --- END: JIRA LIST ISSUES FORMATTING ---

            // 2b. Check for standard { text: ... } response
            if (typeof (mcpResponse as McpToolResponse).text === 'string') {
              console.log("Processing standard text response from MCP.");
              return (mcpResponse as McpToolResponse).text;
            }
            
            // 2c. Handle other potential structured tools here if needed...

          }
          // --- END processing structured object ---
          
          // 3. Fallback for unexpected formats
          console.log("MCP response format not recognized for direct display:", mcpResponse);
          return 'Received a structured response from MCP tools, but could not format it for display.';
          // --- Process MCP response - END ---

        } else {
          // Tool generation decided not to call a tool, or failed
          console.log('Tool generation did not produce a specific MCP call. Falling back to standard chat.');
          // Fall through to standard chat API
        }

      } catch (toolGenOrExecError) {
         // Catch errors from either generateToolCallPayload OR sendMcpMessage
        console.error('Error during MCP tool generation or invocation:', toolGenOrExecError);
        if (toolGenOrExecError instanceof Error) {
          console.error('Error message:', toolGenOrExecError.message);
          // Avoid logging potentially large stacks unless needed
          // console.error('Error stack:', toolGenOrExecError.stack);
        }
        console.error('Falling back to standard chat API due to MCP error.');
        // Fall through to regular chat API on MCP failure
      }
    } else {
      console.log('Message does not appear related to MCP tools, using standard chat API.');
    }

    // Standard chat API call (fallback or non-MCP message)
    console.log("Proceeding with standard RAG API call.");
    const payload: ChatRequestPayload = {
      message,
      chat_history: chatHistory,
    };
    if (modelId) {
      payload.model_id = modelId;
    }
    const response = await apiClient.post<ChatResponsePayload>('/v1/chat/', payload);
    return response.data.reply;

  } catch (error) {
     // General error handling (mostly for the standard chat path now)
    console.error('Error in sendChatMessage main block:', error);
    const axiosError = error as AxiosError<{ detail?: string }>;
    if (axiosError.response?.data?.detail) {
      throw new Error(`Chat API Error: ${axiosError.response.data.detail}`);
    } else if (axiosError instanceof Error) {
      throw new Error(`Failed to get chat response: ${axiosError.message}`);
    } else {
      throw new Error('An unexpected error occurred.');
    }
  }
}; 