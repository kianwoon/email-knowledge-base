import axios, { InternalAxiosRequestConfig, AxiosError } from 'axios';
import { refreshToken } from './auth';
import { SharePointSite, SharePointDrive, SharePointItem, UsedInsight, RecentDriveItem } from '../models/sharepoint';

// Get backend URL from environment variables
const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
console.log('[ApiClient] Environment Mode:', import.meta.env.MODE);
console.log('[ApiClient] VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
console.log('[ApiClient] Final API_BASE_URL:', BACKEND_URL);

const apiClient = axios.create({
  baseURL: `${BACKEND_URL}`, 
  withCredentials: true, 
  timeout: 60000, // Example timeout
});

// Function to set up interceptors (can be called from main app setup)
export const setupInterceptors = () => {
  // --- ADDED Log --- 
  console.log('[setupInterceptors] Function CALLED - Setting up Axios interceptors...');
  // --- END Log ---
  
  // Request interceptor (kept minimal as before)
  apiClient.interceptors.request.use(
    (config) => {
      // Minimal request interceptor logic if needed
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor (logic from previous steps)
  apiClient.interceptors.response.use(
    (response) => response, 
    async (error: AxiosError<any>) => { 
      const originalRequest = error.config as InternalAxiosRequestConfig<any> & { _retry?: boolean };
      
      // --- RE-ADD DEBUG LOGGING --- 
      console.log('[Interceptor] Error Handler Triggered.');
      console.log('[Interceptor] error.response?.status:', error.response?.status);
      console.log('[Interceptor] error.response?.data:', error.response?.data);
      console.log('[Interceptor] error.response?.data?.detail:', error.response?.data?.detail);
      // --- END DEBUG LOGGING --- 

      // Check if it's the specific "User not found" 404 error
      if (
        error.response?.status === 404 && 
        error.response?.data?.detail === "User not found"
      ) {
          console.warn('[Interceptor] Detected User Not Found (404). Treating as session invalid.');
          // ... (clear tokens, dispatch event)
          localStorage.removeItem('token'); 
          localStorage.removeItem('expires');
          localStorage.removeItem('refresh_token');
          console.log('[Interceptor] Dispatching session-expired event due to User Not Found 404.');
          window.dispatchEvent(new CustomEvent('session-expired'));
          return Promise.reject(error); 
      }

      // Handle 401 Unauthorized (likely expired token)
      if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
         originalRequest._retry = true; 
         console.log('[Interceptor] Attempting token refresh...');

         try {
           const msRefreshToken = localStorage.getItem('refresh_token');
           if (!msRefreshToken) {
             throw new Error('Cannot refresh: MS refresh token not found in localStorage.');
           }
           await refreshToken(msRefreshToken);
           console.log('[Interceptor] Token refresh successful (expecting cookie to be set).');
           console.log('[Interceptor] Retrying original request (expecting new cookie).');
           return apiClient(originalRequest);
         } catch (refreshError) {
           console.error('[Interceptor] Token refresh failed:', refreshError);
           // ... (clear tokens, dispatch event)
           localStorage.removeItem('token'); 
           localStorage.removeItem('expires');
           localStorage.removeItem('refresh_token');
           console.log('[Interceptor] Dispatching session-expired event due to refresh failure.');
           window.dispatchEvent(new CustomEvent('session-expired'));
           return Promise.reject(refreshError);
         }
      }

      // For any other errors, just reject the promise
      return Promise.reject(error);
    }
  );
};

// --- SharePoint Specific API Calls (Consider moving to a sharepoint.ts file later) ---

// Existing browse functions would go here if moved...

// New function for Quick Access
export const getQuickAccessItems = async (): Promise<UsedInsight[]> => {
  try {
    const response = await apiClient.get('/sharepoint/quick-access');
    return response.data;
  } catch (error) {
    console.error("Error fetching quick access items:", error);
    throw error;
  }
};

// Placeholder for shared items function
// export const getSharedItems = async () => { ... };

// +++ Add Function for Recent Drive Items +++
export const getMyRecentFiles = async (top: number = 25): Promise<RecentDriveItem[]> => {
  try {
    const response = await apiClient.get('/sharepoint/drive/recent', {
      params: { top }
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching recent drive items:", error);
    throw error;
  }
};

// --- Other API Calls (User, Auth, Knowledge, etc.) ---

export default apiClient; 