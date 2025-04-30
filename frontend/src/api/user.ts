import apiClient from './apiClient';
import { handleApiError } from './errorHandlers';

// Define the provider type
export type ApiProvider = 'openai' | 'anthropic' | 'google' | 'deepseek';

// Legacy function for backward compatibility
export const saveOpenAIApiKey = async (apiKey: string): Promise<void> => {
  try {
    await apiClient.post('/user/api-key', { api_key_data: { api_key: apiKey } });
    console.log('OpenAI API key saved successfully');
  } catch (error) {
    console.error('Error saving OpenAI API key:', error);
    throw handleApiError(error, 'Failed to save OpenAI API key');
  }
};

// New function to save API key for any provider
export const saveProviderApiKey = async (provider: ApiProvider, apiKey: string, modelBaseUrl?: string): Promise<void> => {
  try {
    // Construct the payload, including the optional model_base_url
    const payload: { api_key: string; model_base_url?: string } = { api_key: apiKey };
    if (modelBaseUrl) {
      payload.model_base_url = modelBaseUrl;
    }
    
    await apiClient.post(`/user/provider-api-keys/${provider}`, { api_key_data: payload });
    console.log(`${provider} API key (and base URL if provided) saved successfully`);
  } catch (error) {
    console.error(`Error saving ${provider} API key:`, error);
    throw handleApiError(error, `Failed to save ${provider} API key`);
  }
};

// Legacy function for backward compatibility
export const getOpenAIApiKey = async (): Promise<string | null> => {
  try {
    const response = await apiClient.get('/user/api-key');
    return response.data.api_key;
  } catch (error) {
    console.error('Error getting OpenAI API key:', error);
    throw handleApiError(error, 'Failed to get OpenAI API key');
  }
};

// New function to get API key for any provider
export const getProviderApiKey = async (provider: ApiProvider): Promise<string | null> => {
  try {
    const response = await apiClient.get(`/user/provider-api-keys/${provider}`);
    return response.data.api_key;
  } catch (error) {
    console.error(`Error getting ${provider} API key:`, error);
    throw handleApiError(error, `Failed to get ${provider} API key`);
  }
};

// Legacy function for backward compatibility
export const deleteOpenAIApiKey = async (): Promise<void> => {
  try {
    await apiClient.delete('/user/api-key');
    console.log('OpenAI API key deleted successfully');
  } catch (error) {
    console.error('Error deleting OpenAI API key:', error);
    throw handleApiError(error, 'Failed to delete OpenAI API key');
  }
};

// New function to delete API key for any provider
export const deleteProviderApiKey = async (provider: ApiProvider): Promise<void> => {
  try {
    await apiClient.delete(`/user/provider-api-keys/${provider}`);
    console.log(`${provider} API key deleted successfully`);
  } catch (error) {
    console.error(`Error deleting ${provider} API key:`, error);
    throw handleApiError(error, `Failed to delete ${provider} API key`);
  }
};

// Get all API keys
// Update the return type to match the backend APIKey model
export interface ApiKeyInfo {
  provider: string;
  id: string; // Added id
  user_email: string; // Added user_email
  model_base_url?: string | null; // Added optional model_base_url
  created_at: string; // Keep as string from JSON
  last_used?: string | null; // Keep as string from JSON
  is_active: boolean; // Added is_active
}

export const getAllApiKeys = async (): Promise<ApiKeyInfo[]> => {
  try {
    const response = await apiClient.get('/user/provider-api-keys');
    // Assuming response.data is an array matching the APIKey model structure
    return response.data as ApiKeyInfo[]; 
  } catch (error) {
    console.error('Error getting all API keys:', error);
    throw handleApiError(error, 'Failed to get API keys');
  }
};

export async function saveDefaultModel(modelId: string): Promise<void> {
  try {
    await apiClient.post('/user/default-model', { model_id: modelId });
  } catch (error) {
    handleApiError(error, 'Failed to save default model');
  }
}

export async function getDefaultModel(): Promise<string> {
  try {
    const response = await apiClient.get('/user/default-model');
    return response.data.model_id;
  } catch (error) {
    handleApiError(error, 'Failed to get default model');
    return 'gpt-3.5-turbo'; // Default fallback
  }
} 