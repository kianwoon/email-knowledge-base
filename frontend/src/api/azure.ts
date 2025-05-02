import apiClient from './apiClient';
// Models defined inline for now
// import { AzureConnection, AzureContainer, AzureBlob, AzureSyncItem, AzureSyncItemCreate } from '../models/azure';
import { TaskStatus } from '../models/tasks';

// --- Models (Defined inline) ---

export interface AzureConnection {
  id: string;
  name: string;
  account_name: string; // Add account_name based on backend schema
  // account_name might be available on the backend but not needed for listing,
  // or handled differently. We assume the Create type needs it.
}

// Revert payload: Only name and credentials (connection string) are needed
export interface AzureConnectionCreatePayload {
    name: string;
    // account_name is implicit in the connection string
    // account_name: string; 
    credentials: string; // Represents the connection string
    // account_key?: string | null; 
    // connection_string?: string | null; 
    is_active?: boolean;
}

// Keep AzureConnection (Read model) the same for now, 
// although the backend might stop sending auth_type or credentials if not needed
export interface AzureConnection extends AzureConnectionCreatePayload {
    id: string;
    user_id: string;
    auth_type: string; // Might become less relevant
    container_name?: string | null;
    created_at: string;
    updated_at: string;
}

export interface AzureContainer { name: string; }
export interface AzureBlob {
  name: string;
  path: string;
  isDirectory: boolean;
  size?: number | null;
  lastModified?: string | null;
}
export interface AzureSyncItem {
  id: number;
  item_name: string;
  container_name: string;
  item_path: string;
  item_type: 'blob' | 'prefix';
  status: 'pending' | 'processing' | 'completed' | 'error';
}
export interface AzureSyncItemCreate {
  connection_id: string; // Need connection_id to link item
  item_name: string;
  container_name: string;
  item_path: string;
  item_type: 'blob' | 'prefix';
}

// --- Connection & Browsing --- 

export const getAzureConnections = async (): Promise<AzureConnection[]> => {
    const response = await apiClient.get<AzureConnection[]>('/v1/azure_blob/connections');
    // Ensure ID compatibility if backend sends UUID as string
    return response.data.map(conn => ({ ...conn, id: String(conn.id) }));
};

export const listAzureContainers = async (connectionId: string): Promise<AzureContainer[]> => {
    if (!connectionId) throw new Error("Connection ID is required to list containers");
    const response = await apiClient.get<string[]>(`/v1/azure_blob/connections/${connectionId}/containers`);
    return response.data.map(name => ({ name })); // Map string array to AzureContainer objects
};

export const listAzureBlobs = async (connectionId: string, containerName: string, prefix: string = ''): Promise<AzureBlob[]> => {
  if (!connectionId || !containerName) {
      throw new Error("Connection ID and Container Name are required to list blobs");
  }
  const encodedContainerName = encodeURIComponent(containerName);
  const url = `/v1/azure_blob/connections/${connectionId}/containers/${encodedContainerName}/objects`;
  const response = await apiClient.get<AzureBlob[]>(url, { params: { prefix } });
  return response.data;
};

// Create function remains largely the same, but payload type changed
export const createAzureConnection = async (
    connectionData: AzureConnectionCreatePayload // Use updated type
): Promise<AzureConnection> => {
    // Backend endpoint remains the same for now
    const response = await apiClient.post<AzureConnection>('/v1/azure_blob/connections', connectionData);
    return response.data;
};

// Add function to delete a connection
export const deleteAzureConnection = async (connectionId: string): Promise<void> => {
    try {
        await apiClient.delete(`/v1/azure_blob/connections/${connectionId}`);
    } catch (error: any) {
        console.error("Failed to delete Azure connection:", error);
        throw new Error(`Failed to delete connection: ${error.response?.data?.detail || error.message || 'Unknown error'}`);
    }
};

// --- Sync List Management --- 

export const getAzureSyncList = async (connectionId?: string, status?: string): Promise<AzureSyncItem[]> => {
    console.log(`[API getAzureSyncList] Fetching for connection: ${connectionId ?? 'all'}, status: ${status ?? 'all'}`);
    const params: Record<string, string> = {};
    if (connectionId) {
        params.connection_id = connectionId;
    }
    if (status) {
        params.status = status;
    }
    const response = await apiClient.get<AzureSyncItem[]>('/v1/azure_blob/sync_items', { params });
    return response.data;
};

export const addAzureSyncItem = async (itemData: AzureSyncItemCreate): Promise<AzureSyncItem> => {
    console.log("API CALL: addAzureSyncItem", itemData);
    try {
        const response = await apiClient.post<AzureSyncItem>('/v1/azure_blob/sync_items', itemData);
        return response.data;
    } catch (error: any) {
        console.error("Failed to add Azure sync item:", error);
        throw new Error(`Failed to add sync item: ${error.message || 'Unknown error'}`);
    }
};

export const removeAzureSyncItem = async (itemId: number): Promise<void> => {
    console.log("API CALL: removeAzureSyncItem", itemId);
    try {
        await apiClient.delete(`/v1/azure_blob/sync_items/${itemId}`);
    } catch (error: any) {
        console.error("Failed to remove Azure sync item:", error);
        throw new Error(`Failed to remove sync item: ${error.message || 'Unknown error'}`);
    }
};

// --- Ingestion Trigger --- 

export interface TriggerIngestResponse {
    task_id: string | null;
    message: string;
}

// Modify to accept connectionId
export const triggerAzureIngestion = async (connectionId: string): Promise<TriggerIngestResponse> => {
    // Check if connectionId is provided
    if (!connectionId) {
        console.error("triggerAzureIngestion called without a connectionId.");
        // Return an error-like response or throw an error
        // Mimic backend NO_OP response structure for consistency?
        return { task_id: null, message: "Connection ID is required to trigger ingestion." }; 
        // Or: throw new Error("Connection ID is required to trigger ingestion.");
    }

    console.log("API CALL: triggerAzureIngestion for connection", connectionId);
    try {
        // Send connection_id in the request body
        const response = await apiClient.post<TriggerIngestResponse>('/v1/azure_blob/ingest', { connection_id: connectionId });
        return response.data;
    } catch (error: any) {
        console.error("Failed to trigger Azure ingestion:", error);
        // Extract backend error message if possible
        const message = error.response?.data?.detail || error.message || 'Unknown error';
        throw new Error(`Failed to trigger ingestion: ${message}`);
    }
}; 