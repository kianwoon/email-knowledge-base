// Defines the structure for processed file data returned from the backend API,
// typically used for displaying history or managing ingested files.

export interface ProcessedFile {
  id: number;
  owner_email: string;
  source_type: string; // e.g., \'custom_upload\', \'s3\', \'sharepoint\'
  source_identifier: string; // Original identifier (e.g., filename for custom upload, s3 key)
  original_filename: string;
  r2_object_key: string; // The key used for storage in R2
  content_type?: string | null; // Optional: MIME type
  size_bytes?: number | null; // Optional: File size in bytes
  status: string; // e.g., \'pending_analysis\', \'analysis_complete\', \'analysis_failed\', \'ingestion_failed\'
  uploaded_at: string; // ISO date string
  updated_at: string; // ISO date string
  error_message?: string | null; // Optional: Error message if status is failed
  // additional_data?: Record<string, any> | null; // Optional: Any extra source-specific data
} 