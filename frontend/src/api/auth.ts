import axios, { InternalAxiosRequestConfig } from 'axios';

// Get the API base URL from environment variables
const API_BASE_URL = "https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api" //import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

console.log('Using API base URL:', API_BASE_URL); // Add logging to help debug

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    console.log('Making request to:', `${config.baseURL}${config.url}`); // Add logging to help debug
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Get Microsoft login URL
 */
export const getLoginUrl = async () => {
  try {
    const response = await api.get('/auth/login');
    return response.data;
  } catch (error) {
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
export const refreshToken = async () => {
  try {
    const response = await api.post('/auth/refresh');
    
    // Update token in localStorage
    localStorage.setItem('token', response.data.access_token);
    localStorage.setItem('expires', response.data.expires_at);
    
    return response.data;
  } catch (error) {
    console.error('Error refreshing token:', error);
    throw error;
  }
};

export default api;
