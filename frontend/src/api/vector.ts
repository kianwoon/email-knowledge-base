import apiClient from './apiClient';

// Define the expected response type (adjust if needed based on backend)
interface SaveJobResponse {
  message: string;
  success_count?: number;
  failed_count?: number;
}

/**
 * Sends a request to the backend to save the emails associated with a specific job ID 
 * to the knowledge base (Qdrant).
 * 
 * @param jobId - The ID of the analysis job whose emails should be saved.
 * @returns A promise that resolves with the backend response.
 */
export const saveJobToKnowledgeBase = async (jobId: string): Promise<SaveJobResponse> => {
  if (!jobId) {
    throw new Error("Job ID is required to save to knowledge base.");
  }
  
  console.log(`[api/vector] Sending request to save job ${jobId} to knowledge base...`);
  
  try {
    // Make a POST request to the backend endpoint. 
    // The endpoint expects the job_id in the URL path.
    // No request body is needed for this specific endpoint as defined previously.
    const response = await apiClient.post<SaveJobResponse>(`/vector/save_job/${jobId}`); 
    
    console.log(`[api/vector] Save job request successful for ${jobId}:`, response.data);
    return response.data; // Return the data part of the response
  } catch (error: any) {
    console.error(`[api/vector] Error saving job ${jobId} to knowledge base:`, error);
    // Rethrow the error so the calling component can handle it (e.g., show a toast)
    // You might want to parse the error response for a more specific message if available
    const errorMessage = error.response?.data?.detail || error.message || 'Failed to initiate save operation.';
    throw new Error(errorMessage);
  }
}; 