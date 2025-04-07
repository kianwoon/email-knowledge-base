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
  timeout: 60000, // Increase timeout to 60 seconds
  withCredentials: true
});

// --- REMOVE Authorization Header Request Interceptor --- 
/*
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        console.log(`[Interceptor] Running for request: ${config.method?.toUpperCase()} ${config.url}`);
        const token = getToken(); // Assume getToken is defined elsewhere
        const expired = isTokenExpired(); // Assume isTokenExpired is defined elsewhere
        console.log(`[Interceptor] Retrieved token: ${token ? token.substring(0, 10) + '...' : 'NULL'}`);
        console.log(`[Interceptor] Token expired check: ${expired}`);

        if (token && !expired) {
            console.log('[Interceptor] Attaching token to Authorization header.');
            config.headers.Authorization = `Bearer ${token}`;
        } else {
             if (token && expired) {
                 console.log('[Interceptor] Token found but expired, clearing token.');
                 // clearToken(); // Assume clearToken is defined
            } else if (!token) {
                 console.log('[Interceptor] No token found.');
            }
        }
        console.log('[Interceptor] Request Headers:', JSON.stringify(config.headers));
        return config;
    },
    (error) => {
        console.error('[Interceptor] Request Setup Error:', error);
        return Promise.reject(error);
    }
);
*/

// --- Keep or Modify Response Interceptor (for handling 401s, etc.) --- 
// The response interceptor might still be useful for triggering logout 
// or attempting refresh based on the MS refresh token (which we'll handle later)
// For now, let's simplify it or comment it out if it relies on the old token logic.

// Example: Keeping a simplified response interceptor for 401 logging
// IMPORTANT: Refresh logic needs rework for cookie-based auth
/*
apiClient.interceptors.response.use(
  response => response, // Pass through successful responses
  async error => {
    const originalRequest = error.config;
    
    // Check if it's a 401 Unauthorized error
    if (error.response && error.response.status === 401 && !originalRequest._retry) {
      console.warn('[Interceptor] Received 401 Unauthorized. Cookie might be invalid/expired.');
      originalRequest._retry = true; // Prevent retry loops

      // TODO: Implement MS refresh token logic here if needed later.
      // This would involve:
      // 1. Having the MS refresh token available (e.g., from memory, fetched from /me)
      // 2. Calling a backend endpoint (e.g., /auth/ms-refresh) that uses the MS refresh token
      //    to get a new MS access token AND issues a new JWT cookie.
      // 3. Retrying the original request (browser should automatically send the new cookie).

      // For now, just log and reject, potentially trigger logout in App.tsx
      // Or trigger a global logout event
      window.dispatchEvent(new CustomEvent('auth-error')); // Example event
    }
    
    return Promise.reject(error);
  }
);
*/

// Response interceptor will be added separately to avoid circular dependency
// console.log('[ApiClient] Instance created.');

export default apiClient; 