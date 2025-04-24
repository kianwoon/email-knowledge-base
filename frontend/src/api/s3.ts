import apiClient from './apiClient';

// Interface for S3 Configuration (adjust based on actual backend response)
export interface S3Config {
  role_arn: string | null; // Assuming the ARN is the key config item needed
  // Add other relevant config fields if needed
}

// Interface for an S3 Bucket
export interface S3Bucket {
  name: string;
  creation_date: string; // Assuming date is returned as string
}

// Interface for an S3 Object (File or Folder)
export interface S3Object {
  key: string;
  is_folder: boolean;
  size?: number; // Optional size for files
  last_modified?: string; // Optional last modified date
}

// Interface for the response from the ingest endpoint (adjust as needed)
export interface IngestResponse {
  message: string;
  task_id?: string; // Optional task ID if backend returns it
}

// Interface for the response from the trigger ingest endpoint
export interface TriggerIngestResponse {
  message: string;
  task_id: string | null; // Task ID is null if no pending items
  status: string; // e.g., PENDING, NO_OP
}

// +++ Add S3 Sync Item Interface +++
export interface S3SyncItem {
  id: number; // DB primary key
  user_id: string;
  item_type: 'file' | 'prefix';
  s3_bucket: string;
  s3_key: string;
  item_name: string;
  status: 'pending' | 'processing' | 'completed' | 'failed'; // Status from DB
}

// +++ Add S3 Sync Item Create Interface +++
// Used when adding an item (id, user_id, status handled by backend)
export interface S3SyncItemCreate {
  item_type: 'file' | 'prefix';
  s3_bucket: string;
  s3_key: string;
  item_name: string;
}

// Fetch S3 configuration for the user
export const getS3Config = async (): Promise<S3Config> => {
  const response = await apiClient.get<S3Config>('/s3/configure');
  return response.data;
};

// Fetch the list of accessible S3 buckets
export const listS3Buckets = async (): Promise<S3Bucket[]> => {
  const response = await apiClient.get<S3Bucket[]>('/s3/buckets');
  return response.data;
};

// Fetch objects (files/folders) within a bucket/prefix
export const listS3Objects = async (bucket: string, prefix: string = ''): Promise<S3Object[]> => {
  const response = await apiClient.get<S3Object[]>('/s3/objects', {
    params: {
      bucket_name: bucket,
      prefix: prefix
    }
  });
  return response.data;
};

// Start the ingestion process for selected S3 objects
export const ingestS3Objects = async (bucket: string, keys: string[]): Promise<IngestResponse> => {
  const response = await apiClient.post<IngestResponse>('/s3/ingest', {
    bucket: bucket,
    keys: keys
  });
  return response.data;
};

// Trigger the ingestion process for pending S3 sync items
export const triggerS3Ingestion = async (): Promise<TriggerIngestResponse> => {
  // No body needed for this POST request anymore
  const response = await apiClient.post<TriggerIngestResponse>('/s3/ingest');
  return response.data;
};

// Set or update the S3 configuration (Role ARN) for the user
export const configureS3 = async (roleArn: string): Promise<S3Config> => {
  const response = await apiClient.post<S3Config>('/s3/configure', {
    role_arn: roleArn
  });
  return response.data;
};

// Clear the S3 configuration (Role ARN) for the user
export const clearS3Config = async (): Promise<void> => {
  await apiClient.delete('/s3/configure');
  // DELETE requests often don't return content, especially on success (204 No Content)
};

// --- S3 Sync List API Calls ---

/**
 * Fetches the current list of S3 items in the sync list for the user.
 */
export const getS3SyncList = async (): Promise<S3SyncItem[]> => {
  const response = await apiClient.get<S3SyncItem[]>('/s3/sync-list');
  return response.data;
};

export const getS3SyncHistory = async (limit: number = 100): Promise<S3SyncItem[]> => {
  const response = await apiClient.get<S3SyncItem[]>('/s3/sync-list/history', {
    params: { limit },
  });
  return response.data;
};

/**
 * Adds an S3 item (file or prefix) to the user's sync list.
 * @param itemData The details of the item to add.
 */
export const addS3SyncItem = async (itemData: S3SyncItemCreate): Promise<S3SyncItem> => {
  const response = await apiClient.post<S3SyncItem>('/s3/sync-list/add', itemData);
  return response.data;
};

/**
 * Removes an item from the user's S3 sync list by its database ID.
 * @param itemId The database ID of the sync item to remove.
 */
export const removeS3SyncItem = async (itemId: number): Promise<S3SyncItem> => {
  try {
    const response = await apiClient.delete<S3SyncItem>(`/s3/sync-list/remove/${itemId}`);
    return response.data; // Returns the removed item data
  } catch (error) {
    console.error("Error removing item from S3 sync list:", error);
    throw error;
  }
}; 