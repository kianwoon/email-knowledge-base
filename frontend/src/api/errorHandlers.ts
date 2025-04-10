import axios, { AxiosError } from 'axios';

/**
 * Standard error handler for API calls
 * @param error The error object from axios
 * @param defaultMessage Default message to show if we can't extract one from the error
 * @returns Throws the error with an appropriate message
 */
export function handleApiError<T>(error: unknown, defaultMessage: string): T {
  console.error('API Error:', error);
  
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError;
    
    // Check if there's a response with error details from the server
    if (axiosError.response?.data) {
      const responseData = axiosError.response.data as any;
      const errorMessage = responseData.detail || responseData.message || JSON.stringify(responseData);
      throw new Error(errorMessage);
    }
    
    // Network errors
    if (axiosError.code === 'ECONNABORTED') {
      throw new Error('Request timed out. Please try again.');
    }
    
    if (!axiosError.response) {
      throw new Error('Network error. Please check your connection.');
    }
    
    // HTTP status error but no detailed message
    throw new Error(`${defaultMessage} (${axiosError.response.status})`);
  }
  
  // Non-axios errors
  throw new Error(defaultMessage);
} 