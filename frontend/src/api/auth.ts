import apiClient from './apiClient'; // Import the shared client
import { InternalAxiosRequestConfig } from 'axios'; // Keep if needed elsewhere, or remove

// Debug environment variables
console.log('=== Auth API Configuration ===');
console.log('Environment Mode:', import.meta.env.MODE);
console.log('VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);

/**
 * Get Microsoft login URL
 */
export const getLoginUrl = async () => {
  console.log('=== Getting Login URL ===');
  try {
    // Use apiClient directly
    const response = await apiClient.get('/auth/login');
    console.log('Login URL Response:', response.data);
    return response.data;
  } catch (error) {
    console.error('=== Login URL Error ===');
    console.error('Error getting login URL:', error);
    throw error;
  }
};

/**
 * Get current user information
 */
export const getCurrentUser = async () => {
  try {
    // Use apiClient directly
    const response = await apiClient.get('/auth/me');
    return response.data;
  } catch (error) {
    console.error('Error getting user info:', error);
    throw error;
  }
};

/**
 * Refresh access token
 * This function is now also used BY the interceptor, so it uses apiClient.
 */
export const refreshToken = async (msRefreshToken: string) => {
  console.log('=== Refreshing Token ===');
  try {
    if (!msRefreshToken) {
      throw new Error('No MS refresh token provided to refreshToken function');
    }

    console.log('Sending MS refresh token to backend...');
    // Use apiClient directly
    const response = await apiClient.post('/auth/refresh', {
      refresh_token: msRefreshToken
    });
    
    console.log('Refresh token response received:', response.data);
    
    return response.data;
  } catch (error) {
    console.error('Error refreshing token:', error);
    // Error handling (clearing tokens) is now primarily done in the interceptor
    // but we still throw the error for the interceptor to catch.
    throw error;
  }
};

// Function to call the backend logout endpoint
export const logout = async () => {
  try {
    console.log('Calling backend /auth/logout...');
    // No data needs to be sent, just make the POST request
    const response = await apiClient.post('/auth/logout'); 
    console.log('Logout API response:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error calling logout API:', error);
    // Re-throw the error so the caller can handle it if needed
    throw error; 
  }
};
