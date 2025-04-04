import axios, { InternalAxiosRequestConfig } from 'axios';

// Get the API base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// Debug environment variables
console.log('=== Auth API Configuration ===');
console.log('Environment Mode:', import.meta.env.MODE);
console.log('VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
console.log('Final API_BASE_URL:', API_BASE_URL);

if (!API_BASE_URL) {
  console.error('API_BASE_URL is not configured properly');
}

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  },
  timeout: 10000 // 10 second timeout
});

// Add request interceptor to include auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    console.log('=== Auth API Request ===');
    console.log('Full Request URL:', `${config.baseURL}${config.url}`);
    console.log('Request Method:', config.method?.toUpperCase());
    return config;
  },
  (error) => {
    console.error('=== Auth API Request Error ===');
    console.error('Request failed:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for handling token refresh
api.interceptors.response.use(
  (response) => {
    console.log('=== Auth API Response ===');
    console.log('Response Status:', response.status);
    return response;
  },
  async (error) => {
    console.error('=== Auth API Response Error ===');
    console.error('Response Error:', error);
    
    const originalRequest = error.config;
    
    // If the error is 401 and we haven't tried to refresh the token yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        // Try to refresh the token
        const msRefreshToken = localStorage.getItem('refresh_token');
        if (!msRefreshToken) {
          throw new Error('Cannot refresh: MS refresh token not found in localStorage.');
        }
        const response = await refreshToken(msRefreshToken);
        if (response.access_token) {
          // Update the authorization header
          originalRequest.headers.Authorization = `Bearer ${response.access_token}`;
          // Retry the original request
          return api(originalRequest);
        }
      } catch (refreshError) {
        console.error('Token refresh failed:', refreshError);
        // Clear tokens and redirect to login
        localStorage.removeItem('token');
        localStorage.removeItem('expires');
        localStorage.removeItem('refresh_token');
        window.location.href = '/';
      }
    }
    
    return Promise.reject(error);
  }
);

/**
 * Get Microsoft login URL
 */
export const getLoginUrl = async () => {
  console.log('=== Getting Login URL ===');
  try {
    const response = await api.get('/auth/login');
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
    const response = await api.get('/auth/me');
    return response.data;
  } catch (error) {
    console.error('Error getting user info:', error);
    throw error;
  }
};

/**
 * Refresh access token
 */
export const refreshToken = async (msRefreshToken: string) => {
  console.log('=== Refreshing Token ===');
  try {
    if (!msRefreshToken) {
      throw new Error('No MS refresh token provided to refreshToken function');
    }

    console.log('Sending MS refresh token to backend...');
    // Send the MS refresh token in the request body
    const response = await api.post('/auth/refresh', {
      refresh_token: msRefreshToken
    });
    
    console.log('Refresh token response received:', response.data);
    
    if (response.data.access_token) {
      // Update internal JWT access token and expiry in localStorage
      localStorage.setItem('token', response.data.access_token);
      localStorage.setItem('expires', response.data.expires_at); 
      
      // NOTE: The backend currently doesn't return the NEW MS refresh token.
      // If the backend were updated to return it (e.g., in a field like `ms_refresh_token`),
      // you would update it in localStorage here:
      // if (response.data.ms_refresh_token) {
      //   localStorage.setItem('refresh_token', response.data.ms_refresh_token);
      // }
    }
    
    return response.data; // Return the new internal token details
  } catch (error) {
    console.error('Error refreshing token:', error);
    // Clear tokens on refresh failure to force re-login
    localStorage.removeItem('token');
    localStorage.removeItem('expires');
    localStorage.removeItem('refresh_token');
    // Consider redirecting to login or notifying user
    // window.location.href = '/'; 
    throw error;
  }
};

export default api;
