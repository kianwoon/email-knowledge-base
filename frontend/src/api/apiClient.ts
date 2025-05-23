import axios, { InternalAxiosRequestConfig, AxiosError } from 'axios';
// import { refreshToken } from './auth'; // Remove this import
import { SharePointSite, SharePointDrive, SharePointItem, UsedInsight, RecentDriveItem, SharePointSyncItem, SharePointSyncItemCreate } from '../models/sharepoint';
import { TaskStatus } from '../models/tasks';

// Get backend URL from environment variables
const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
console.log('[ApiClient] Environment Mode:', import.meta.env.MODE);
console.log('[ApiClient] VITE_API_BASE_URL:', import.meta.env.VITE_API_BASE_URL);
console.log('[ApiClient] Final API_BASE_URL:', BACKEND_URL);

// Create an interceptor to log all requests and responses
const apiClient = axios.create({
  baseURL: '/api', // This will use the Vite proxy at /api
  withCredentials: true, // Ensure credentials (cookies) are included in all requests
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // Increased timeout to 120 seconds
});

// Add a request interceptor for debugging
apiClient.interceptors.request.use(
  (config) => {
    // Get token from localStorage (primary source)
    const token = localStorage.getItem('access_token');
    
    console.log(`[ApiClient] Request to ${config.url}`, { 
      headers: config.headers,
      withCredentials: config.withCredentials,
      cookies: document.cookie || 'none',
      hasToken: !!token
    });
    
    // Always add token to Authorization header if it exists in localStorage
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
      console.log(`[ApiClient] Added token from localStorage to Authorization header.`);
    }
    
    // +++ Added Log +++
    console.log(`[ApiClient] Final Authorization header before sending request to ${config.url}:`, config.headers['Authorization'] || 'Not Set');
    // --- End Added Log ---
    
    return config;
  },
  (error) => {
    console.error('[ApiClient] Request error:', error);
    return Promise.reject(error);
  }
);

// Add a response interceptor for debugging
apiClient.interceptors.response.use(
  (response) => {
    console.log(`[ApiClient] Response from ${response.config.url}:`, {
      status: response.status,
      headers: response.headers
    });
    return response;
  },
  (error) => {
    console.error(`[ApiClient] Response error from ${error.config?.url}:`, {
      status: error.response?.status,
      message: error.message,
      response: error.response?.data
    });
    
    // Check if the error is due to 401 Unauthorized (session expired/invalid)
    if (error.response && error.response.status === 401) {
      console.log('Session expired or unauthorized. Dispatching event...');
      window.dispatchEvent(new CustomEvent('session-expired'));
    }
    return Promise.reject(error);
  }
);

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

// =========================================
// Azure Blob Storage API Calls
// =========================================

// Define interfaces for Azure Blob connections based on backend schemas
export interface AzureBlobConnection {
  id: string; // Assuming UUID is string
  user_id: string;
  name: string;
  account_name: string;
  auth_type: string; // 'connection_string', etc.
  container_name?: string | null;
  is_active: boolean;
  created_at: string; // ISO date string
  updated_at: string; // ISO date string
}

export interface AzureBlobConnectionCreatePayload {
  name: string;
  account_name: string;
  credentials: string; // The connection string
  auth_type?: string; // Defaults to 'connection_string' on backend
  container_name?: string;
  is_active?: boolean;
}

export const createAzureBlobConnection = async (
  connectionData: AzureBlobConnectionCreatePayload
): Promise<AzureBlobConnection> => {
  const response = await apiClient.post<AzureBlobConnection>('/azure_blob/connections', connectionData);
  return response.data;
};

export const getAzureBlobConnections = async (): Promise<AzureBlobConnection[]> => {
  const response = await apiClient.get<AzureBlobConnection[]>('/azure_blob/connections');
  return response.data;
};

export const listAzureBlobContainers = async (connectionId: string): Promise<string[]> => {
  const response = await apiClient.get<string[]>(`/azure_blob/connections/${connectionId}/containers`);
  return response.data;
};

// Add more functions later: update, delete, list blobs, upload etc.

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