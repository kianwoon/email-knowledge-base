import axios, { InternalAxiosRequestConfig } from 'axios';

// Get the API base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

console.log('[ApiClient] Environment Mode:', import.meta.env.MODE);
console.log('[ApiClient] VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
console.log('[ApiClient] Final API_BASE_URL:', API_BASE_URL);

if (!API_BASE_URL) {
  console.error('[ApiClient] API_BASE_URL is not configured properly');
  // You might want to throw an error here in a real app
}

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json', // Added Accept based on auth.ts
  },
  timeout: 10000, // 10 second timeout
});

// Add request interceptor to include auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    console.log('[ApiClient] Request:', `${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
    return config;
  },
  (error) => {
    console.error('[ApiClient] Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor will be added separately to avoid circular dependency
// console.log('[ApiClient] Instance created.');

export default apiClient; 