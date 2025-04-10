import apiClient from './apiClient';
import { AxiosError } from 'axios'; // Import AxiosError for type safety

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

/**
 * Sends a chat message to the backend (OpenAI only endpoint).
 */
export const sendChatMessage = async (
  message: string,
  chatHistory?: Array<{ role: 'user' | 'assistant', content: string }>,
  modelId?: string // Add model ID parameter
): Promise<string> => {
  try {
    const payload: ChatRequestPayload = {
      message,
      chat_history: chatHistory, // Pass history if provided
    };

    // Add model ID if provided
    if (modelId) {
      payload.model_id = modelId;
    }
    
    // Make sure the path matches the backend route: /api/v1/chat/openai
    // (apiClient likely adds /api/v1 automatically)
    const response = await apiClient.post<ChatResponsePayload>('/chat/openai', payload);
    
    return response.data.reply;
  } catch (error) {
    console.error('Error sending chat message:', error);
    
    // Type checking for Axios error
    const axiosError = error as AxiosError<{ detail?: string }>; // Cast to AxiosError with potential detail

    if (axiosError.response && axiosError.response.data && axiosError.response.data.detail) {
        throw new Error(`Chat API Error: ${axiosError.response.data.detail}`);
    } else if (axiosError instanceof Error) {
        // Handle generic errors
        throw new Error(`Failed to get chat response: ${axiosError.message}`);
    } else {
        // Handle unexpected error types
        throw new Error('An unexpected error occurred while fetching the chat response.');
    }
  }
}; 