import axios, { InternalAxiosRequestConfig } from 'axios';

// Get the API base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL?.trim();

// Debug environment variables
console.log('=== Auth API Configuration ===');
console.log('Environment Mode:', import.meta.env.MODE);
console.log('VITE_BACKEND_URL:', import.meta.env.VITE_BACKEND_URL);
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

// Add response interceptor for better error handling
api.interceptors.response.use(
  (response) => {
    console.log('=== Auth API Response ===');
    console.log('Response Status:', response.status);
    return response;
  },
  (error) => {
    console.error('=== Auth API Response Error ===');
    console.error('Response Error:', error);
    if (error.response) {
      console.error('Error Response Status:', error.response.status);
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
