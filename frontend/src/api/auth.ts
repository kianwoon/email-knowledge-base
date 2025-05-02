import axios from 'axios'; // Add missing import
import apiClient from './apiClient'; // Import the shared client
import { InternalAxiosRequestConfig } from 'axios'; // Keep if needed elsewhere, or remove
// import { User } from '@/models/user.model'; // Remove this import as the model wasn't found

// Debug environment variables
console.log('=== Auth API Configuration ===');
console.log('Environment Mode:', import.meta.env.MODE);
console.log('VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
console.log("auth.ts - VITE_BACKEND_URL:", import.meta.env.VITE_BACKEND_URL);

/**
 * Get Microsoft login URL
 */
export const getLoginUrl = async (): Promise<string> => {
  console.log('=== Getting Login URL ===');
  try {
    const response = await apiClient.get('/v1/auth/login');
    if (!response.data.auth_url) {
      throw new Error("Auth URL not found in response");
    }
    return response.data.auth_url;
  } catch (error) {
    console.error("Error fetching login URL:", error);
    throw error;
  }
};

/**
 * Get current user information
 */
export const getCurrentUser = async (): Promise<any | null> => {
  try {
    const response = await apiClient.get<any>('/v1/auth/me');
    return response.data;
  } catch (error: any) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      console.log('GetCurrentUser: No active session (401).');
      return null; // No active session
    }
    console.error("Error fetching current user:", error);
    throw error; // Rethrow other errors
  }
};

/**
 * Refresh access token
 * This function is now also used BY the interceptor, so it uses apiClient.
 */
// export const refreshToken = async (msRefreshToken: string) => { // Remove this function
//   console.log('=== Refreshing Token ===');
//   try {
//     if (!msRefreshToken) {
//       throw new Error('No MS refresh token provided to refreshToken function');
//     }
//
//     console.log('Sending MS refresh token to backend...');
//     // Use apiClient directly
//     const response = await apiClient.post('/auth/refresh', {
//       refresh_token: msRefreshToken
//     });
//
//     console.log('Refresh token response received:', response.data);
//
//     return response.data;
//   } catch (error) {
//     console.error('Error refreshing token:', error);
//     // Error handling (clearing tokens) is now primarily done in the interceptor
//     // but we still throw the error for the interceptor to catch.
//     throw error;
//   }
// };

// Function to call the backend logout endpoint
export const logout = async (): Promise<void> => {
  try {
    console.log('Calling backend /v1/auth/logout...');
    await apiClient.post('/v1/auth/logout');
    
    // Also manually clear the cookie on the client side for immediate effect
    document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    console.log('Cleared access_token cookie');
  } catch (error) {
    console.error("Error during logout:", error);
    throw error;
  }
};

/**
 * Get token directly from the backend instead of relying on cookies
 * This is a fallback when cookies don't work properly due to cross-domain issues
 */
export const getTokenDirectly = async (): Promise<string | null> => {
  try {
    console.log('Fetching token directly from backend...');
    const response = await fetch('/api/v1/auth/token', {
      method: 'GET',
      credentials: 'include', // Still try to send cookies
      headers: {
        'Accept': 'application/json',
      }
    });
    
    if (!response.ok) {
      console.log('Failed to get token:', response.status);
      return null;
    }
    
    const data = await response.json();
    if (data.access_token) {
      console.log('Received token directly, setting as local cookie');
      // Set the token as a cookie that the frontend can read
      document.cookie = `access_token=${data.access_token}; path=/; max-age=7200; SameSite=Lax`;
      return data.access_token;
    }
    
    return null;
  } catch (error) {
    console.error('Error fetching token directly:', error);
    return null;
  }
};
