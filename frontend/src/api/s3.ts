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
    bucket_name: bucket,
    object_keys: keys
  });
  return response.data;
};

// Set or update the S3 configuration (Role ARN) for the user
export const configureS3 = async (roleArn: string): Promise<S3Config> => {
  const response = await apiClient.post<S3Config>('/s3/configure', {
    role_arn: roleArn
  });
  return response.data;
}; 