export interface CustomKnowledgeFile {
  id: number;
  user_email: string;
  filename: string;
  content_type: string;
  file_size: number;
  qdrant_collection: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  uploaded_at: string;
}
