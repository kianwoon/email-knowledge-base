import apiClient from './apiClient';
// Remove unused import if axiosInstance is not defined/used elsewhere
// import axiosInstance from './axiosInstance'; 
import { EmailFilter } from '../types/email'; // <-- Import EmailFilter type

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

// --- NEW API FUNCTION --- 

// Define the expected response type for the ASYNCHRONOUS task submission
interface SubmitTaskResponse {
  task_id: string;
  message: string;
}

export const saveFilteredEmailsToKnowledgeBase = async (filter: EmailFilter): Promise<SubmitTaskResponse> => {
  console.log('[API Call] Submitting task to save filtered emails to KB with filter:', filter);
  
  try {
    // Use the existing apiClient
    const response = await apiClient.post<SubmitTaskResponse>( // Specify the expected response type
      `/vector/save_filtered_emails`, // Use the endpoint that dispatches the task
      filter // Send the filter object as the request body
    );
    console.log('[API Response] saveFilteredEmailsToKnowledgeBase (Task Submission):', response.data);
    // Expecting { task_id: "...", message: "..." }
    if (!response.data || !response.data.task_id) {
        throw new Error("API response did not include a task_id.");
    }
    return response.data; 
  } catch (error: any) {
    console.error('Error submitting task to save filtered emails:', error.response?.data || error.message);
    // Re-throw a more specific error message if available from backend
    throw new Error(error.response?.data?.detail || 'Failed to submit task to save filtered emails');
  }
}; 

// Generic search function
export const searchEmails = async (query: string, limit: number = 10): Promise<any[]> => {
  console.log(`[searchEmails] Searching for: "${query}", limit: ${limit}`);
  
  try {
    const response = await apiClient.post('/vector/search', 
      { query, limit },
    );
    console.log('[searchEmails] Response received:', response.data);
    return response.data.results || []; // Assuming results are in response.data.results
  } catch (error: any) {
    console.error('[searchEmails] Error searching emails:', error);
    if (error.response) {
        console.error('Error response data:', error.response.data);
        throw new Error(error.response.data.detail || 'Error performing vector search');
    } else {
        throw new Error('Network error or unexpected issue during vector search');
    }
  }
};

// Add other vector-related API calls here if needed, ensuring they also don't use localStorage