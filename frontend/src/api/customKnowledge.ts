import apiClient from './apiClient';
import { CustomKnowledgeFile } from '../models/customKnowledge';

// New: Upload files as base64 to the backend (no FormData, no multipart)
export const uploadCustomKnowledgeFiles = async (files: File[]): Promise<void> => {
  for (const file of files) {
    const base64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        // Remove data:...;base64, prefix
        const result = reader.result as string;
        resolve(result.split(',')[1]);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
    await apiClient.post('/custom-knowledge/upload-base64', {
      filename: file.name,
      content_type: file.type,
      file_size: file.size,
      content_base64: base64,
    });
  }
};

export const getCustomKnowledgeHistory = async (): Promise<CustomKnowledgeFile[]> => {
  const response = await apiClient.get<CustomKnowledgeFile[]>('/custom-knowledge/history');
  return response.data;
};
