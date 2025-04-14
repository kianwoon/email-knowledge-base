import axios, { InternalAxiosRequestConfig, AxiosError } from 'axios';
// import { refreshToken } from './auth'; // Remove this import
import { SharePointSite, SharePointDrive, SharePointItem, UsedInsight, RecentDriveItem, SharePointSyncItem, SharePointSyncItemCreate } from '../models/sharepoint';
import { TaskStatus } from '../models/tasks';

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
      // const originalRequest = error.config as InternalAxiosRequestConfig<any> & { _retry?: boolean }; // No longer needed
      
      // --- RE-ADD DEBUG LOGGING --- 
      console.log('[Interceptor] Error Handler Triggered.');
      console.log('[Interceptor] error.response?.status:', error.response?.status);
      console.log('[Interceptor] error.response?.data:', error.response?.data);
      console.log('[Interceptor] error.response?.data?.detail:', error.response?.data?.detail);
      // --- END DEBUG LOGGING --- 

      // --- REMOVE ALL 401 and 404 HANDLING LOGIC FROM HERE --- 
      // The session-expired event logic in App.tsx now handles 401 consequences.
      // // Check if it's the specific "User not found" 404 error
      // if (
      //   error.response?.status === 404 && 
      //   error.response?.data?.detail === "User not found"
      // ) {
      //     console.warn('[Interceptor] Detected User Not Found (404). Treating as session invalid.');
      //     // ... (clear tokens, dispatch event)
      //     localStorage.removeItem('token'); 
      //     localStorage.removeItem('expires');
      //     localStorage.removeItem('refresh_token');
      //     console.log('[Interceptor] Dispatching session-expired event due to User Not Found 404.');
      //     window.dispatchEvent(new CustomEvent('session-expired'));
      //     return Promise.reject(error); 
      // }

      // // Handle 401 Unauthorized (likely expired token)
      // if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      //    originalRequest._retry = true; 
      //    console.log('[Interceptor] Attempting token refresh...');
      //
      //    try {
      //      const msRefreshToken = localStorage.getItem('refresh_token');
      //      if (!msRefreshToken) {
      //        throw new Error('Cannot refresh: MS refresh token not found in localStorage.');
      //      }
      //      await refreshToken(msRefreshToken); // <--- This was the remaining call
      //      console.log('[Interceptor] Token refresh successful (expecting cookie to be set).');
      //      console.log('[Interceptor] Retrying original request (expecting new cookie).');
      //      return apiClient(originalRequest);
      //    } catch (refreshError) {
      //      console.error('[Interceptor] Token refresh failed:', refreshError);
      //      // ... (clear tokens, dispatch event)
      //      localStorage.removeItem('token'); 
      //      localStorage.removeItem('expires');
      //      localStorage.removeItem('refresh_token');
      //      console.log('[Interceptor] Dispatching session-expired event due to refresh failure.');
      //      window.dispatchEvent(new CustomEvent('session-expired'));
      //      return Promise.reject(refreshError);
      //    }
      // }
      // --- END REMOVAL --- 

      // For ALL errors, just reject the promise
      // The App.tsx event listener will handle the session-expired event if triggered by a 401
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

// --- SharePoint Sync List API Calls ---

/**
 * Fetches the current list of items selected for syncing by the user.
 */
export const getSyncList = async (): Promise<SharePointSyncItem[]> => {
    try {
        const response = await apiClient.get('/sharepoint/sync-list');
        return response.data;
    } catch (error) {
        console.error("Error fetching SharePoint sync list:", error);
        throw error;
    }
};

/**
 * Adds an item to the user's SharePoint sync list.
 */
export const addSyncItem = async (itemData: SharePointSyncItemCreate): Promise<SharePointSyncItem> => {
    try {
        const response = await apiClient.post('/sharepoint/sync-list/add', itemData);
        return response.data;
    } catch (error) {
        // Handle potential 409 Conflict specifically if needed
        if (axios.isAxiosError(error) && error.response?.status === 409) {
            console.warn('Attempted to add duplicate item to sync list:', itemData.sharepoint_item_id);
            // Rethrow the original error so the UI can handle the 409
        }
        console.error("Error adding item to SharePoint sync list:", error);
        throw error;
    }
};

/**
 * Removes an item from the user's SharePoint sync list.
 * @param sharepointItemId The SharePoint ID of the item to remove.
 */
export const removeSyncItem = async (sharepointItemId: string): Promise<SharePointSyncItem> => {
    try {
        const response = await apiClient.delete(`/sharepoint/sync-list/remove/${sharepointItemId}`);
        return response.data;
    } catch (error) {
        // Handle potential 404 Not Found specifically if needed
        if (axios.isAxiosError(error) && error.response?.status === 404) {
            console.warn('Attempted to remove non-existent item from sync list:', sharepointItemId);
             // Rethrow the original error so the UI can handle the 404
        }
        console.error("Error removing item from SharePoint sync list:", error);
        throw error;
    }
};

/**
 * Submits the user's current sync list for processing.
 * Returns the ID of the initiated Celery task.
 */
export const processSyncList = async (): Promise<{ task_id: string }> => {
    try {
        const response = await apiClient.post('/sharepoint/sync-list/process');
        return response.data; // Should be { task_id: "some-uuid" }
    } catch (error) {
         // Handle potential 400 Bad Request (empty list)
         if (axios.isAxiosError(error) && error.response?.status === 400) {
            console.warn('Attempted to process an empty sync list.');
             // Rethrow the original error so the UI can handle the 400
        }
        console.error("Error submitting SharePoint sync list for processing:", error);
        throw error;
    }
};

// --- Task Status API Call ---

/**
 * Fetches the status of a specific Celery task.
 */
export const getTaskStatus = async (taskId: string): Promise<TaskStatus> => {
    try {
        const response = await apiClient.get(`/tasks/status/${taskId}`);
        return response.data;
    } catch (error) {
        console.error(`Error fetching status for task ${taskId}:`, error);
        throw error;
    }
};

// --- Other API Calls (User, Auth, Knowledge, etc.) ---

export default apiClient; 