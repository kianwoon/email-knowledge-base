import apiClient from './apiClient';

/**
 * Fetches the available column names from the email_facts Iceberg table.
 * 
 * @returns {Promise<string[]>} A promise that resolves to an array of column names.
 * @throws {Error} If the API call fails.
 */
export const getEmailFactsColumns = async (): Promise<string[]> => {
  try {
    const response = await apiClient.get<string[]>('/schema/email-facts/columns');
    return response.data;
  } catch (error: any) {
    console.error('API Error fetching email facts columns:', error);
    // Re-throw the error so the calling component can handle it (e.g., display a message)
    throw new Error(error.response?.data?.detail || error.message || 'Failed to fetch column schema');
  }
}; 