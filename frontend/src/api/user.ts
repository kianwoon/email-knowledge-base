import apiClient from './apiClient';
import { handleApiError } from './errorHandlers';

export type ApiProvider = 'openai' | 'anthropic' | 'google';

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
export const saveProviderApiKey = async (provider: ApiProvider, apiKey: string): Promise<void> => {
  try {
    await apiClient.post(`/user/provider-api-keys/${provider}`, { api_key_data: { api_key: apiKey } });
    console.log(`${provider} API key saved successfully`);
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
export const getAllApiKeys = async (): Promise<Array<{provider: string, created_at: string, last_used?: string}>> => {
  try {
    const response = await apiClient.get('/user/provider-api-keys');
    return response.data;
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