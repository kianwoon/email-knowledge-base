import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { refreshToken } from './auth'; // Assuming refreshToken handles MSAL/backend communication

// Get backend URL from environment variables
// const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'; // No longer needed for local dev proxy

const apiClient = axios.create({
  // baseURL: `${BACKEND_URL}/api`, // REMOVE THIS LINE
  baseURL: '/api', // USE THIS RELATIVE PATH for Vite proxy
  withCredentials: true, // Send cookies (like HttpOnly refresh token)
});

// Function to set up interceptors (can be called from main app setup)
export const setupInterceptors = () => {
  // Request interceptor (optional: can add token here if not using cookies)
  apiClient.interceptors.request.use(
    (config) => {
      // If using Authorization header instead of cookies:
      // const token = localStorage.getItem('token');
      // if (token) {
      //   config.headers.Authorization = `Bearer ${token}`;
      // }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor for handling errors and token refresh
  apiClient.interceptors.response.use(
    (response) => response, // Pass through successful responses
    async (error: AxiosError<any>) => { // Add type <any> for error.response.data
      const originalRequest = error.config as InternalAxiosRequestConfig<any> & { _retry?: boolean }; // Cast and add _retry
      
      // --- ADDED DEBUG LOGGING --- 
      console.log('[Interceptor] Error Handler Triggered.');
      console.log('[Interceptor] error.response?.status:', error.response?.status);
      console.log('[Interceptor] error.response?.data:', error.response?.data);
      console.log('[Interceptor] error.response?.data?.detail:', error.response?.data?.detail);
      // --- END DEBUG LOGGING --- 

      // Check if it's the specific "User not found" 404 error
      // Ensure data and detail exist before checking the detail value
      if (
        error.response?.status === 404 && 
        error.response?.data?.detail === "User not found"
      ) {
          console.warn('[Interceptor] Detected User Not Found (404). Treating as session invalid.');
          // Clear tokens 
          localStorage.removeItem('token'); 
          localStorage.removeItem('expires');
          localStorage.removeItem('refresh_token');
          // Dispatch the event to trigger the modal
          console.log('[Interceptor] Dispatching session-expired event due to User Not Found 404.');
          window.dispatchEvent(new CustomEvent('session-expired'));
          return Promise.reject(error); // Reject the original request
      }

      // Handle 401 Unauthorized (likely expired token)
      // Ensure originalRequest exists before accessing _retry
      if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
        originalRequest._retry = true; // Mark to prevent infinite loops
        console.log('[Interceptor] Attempting token refresh...');

        try {
          // --- Restore logic to get refresh token and pass it --- 
          const msRefreshToken = localStorage.getItem('refresh_token');
          if (!msRefreshToken) {
            throw new Error('Cannot refresh: MS refresh token not found in localStorage.');
          }
          // Pass the refresh token string to the function
          const refreshResponse = await refreshToken(msRefreshToken);
          console.log('[Interceptor] Token refresh successful (expecting cookie to be set).');
          // --- End Restore --- 
          
          // No need to manually set Authorization header if using HttpOnly cookies
          // Just retry the original request; the browser should send the new cookie
          console.log('[Interceptor] Retrying original request (expecting new cookie).');
          return apiClient(originalRequest); // Retry original request
        } catch (refreshError) {
          console.error('[Interceptor] Token refresh failed:', refreshError);
          // Clear tokens 
          localStorage.removeItem('token'); 
          localStorage.removeItem('expires');
          localStorage.removeItem('refresh_token');
          // Dispatch an event instead of redirecting immediately
          console.log('[Interceptor] Dispatching session-expired event due to refresh failure.');
          window.dispatchEvent(new CustomEvent('session-expired'));
          return Promise.reject(refreshError); // Reject the promise after dispatching
        }
      }

      // For any other errors, just reject the promise
      return Promise.reject(error);
    }
  );
  console.log('[Interceptor] Response interceptor set up.');
};

export default apiClient; 