import apiClient from './apiClient';
import { handleApiError } from './errorHandlers';

export const saveOpenAIApiKey = async (apiKey: string): Promise<void> => {
  try {
    await apiClient.post('/user/api-key', { api_key: apiKey });
    console.log('OpenAI API key saved successfully');
  } catch (error) {
    console.error('Error saving OpenAI API key:', error);
    throw handleApiError(error, 'Failed to save OpenAI API key');
  }
};

export const getOpenAIApiKey = async (): Promise<string | null> => {
  try {
    const response = await apiClient.get('/user/api-key');
    return response.data.api_key;
  } catch (error) {
    console.error('Error getting OpenAI API key:', error);
    throw handleApiError(error, 'Failed to get OpenAI API key');
  }
};

export const deleteOpenAIApiKey = async (): Promise<void> => {
  try {
    await apiClient.delete('/user/api-key');
    console.log('OpenAI API key deleted successfully');
  } catch (error) {
    console.error('Error deleting OpenAI API key:', error);
    throw handleApiError(error, 'Failed to delete OpenAI API key');
  }
}; 