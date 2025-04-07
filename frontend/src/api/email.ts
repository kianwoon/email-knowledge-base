import apiClient from './apiClient'; // Import the shared client
import { EmailFilter, EmailPreview, EmailContent, PaginatedEmailPreviewResponse } from '../types/email';

/**
 * Get email folders from Outlook
 */
export const getEmailFolders = async () => {
  try {
    const response = await apiClient.get('/email/folders'); // Corrected path
    return response.data;
  } catch (error) {
    console.error('Error fetching email folders:', error);
    throw error;
  }
};

/**
 * Get email previews based on filter criteria
 */
export const getEmailPreviews = async (
  filter: EmailFilter, 
  page: number = 1, 
  per_page: number = 10,
  next_link?: string // Still accept next_link, might be needed in filter body
): Promise<PaginatedEmailPreviewResponse> => {
  
  // Construct query parameters for pagination
  const queryParams: any = { page, per_page };

  // Prepare the filter data to be sent in the body
  // Include next_link if provided
  const bodyFilter: EmailFilter & { next_link?: string } = {
     ...filter,
     next_link: next_link // Add next_link to the body payload
  };

  console.log(`[getEmailPreviews] Calling POST /preview`);
  console.log(`[getEmailPreviews] Query Params: ${JSON.stringify(queryParams)}`);
  console.log(`[getEmailPreviews] Body Filter: ${JSON.stringify(bodyFilter)}`);

  try {
    // Use POST to /preview, send filter in body, pagination in query
    const response = await apiClient.post<PaginatedEmailPreviewResponse>(
      '/email/preview', // Corrected path (singular)
      bodyFilter,   // Filter data (including next_link if present) in the request body
      { params: queryParams } // Pagination data in query parameters
    );
    
    console.log(`[getEmailPreviews] Response status: ${response.status}`);
    return response.data;
  } catch (error: any) {
    console.error('Error fetching email previews:', error.response?.data || error.message);
    // RE-THROW the original error
    throw error;
  }
};

/**
 * Get full content of a specific email
 */
export const getEmailContent = async (emailId: string): Promise<EmailContent> => {
  console.log(`[getEmailContent] Fetching content for email ID: ${emailId}`);
  
  try {
    // Ensure the API endpoint matches backend routes
    const response = await apiClient.get(`/emails/${emailId}/content`); 
    console.log('[getEmailContent] Response received:', response.data);
    // The backend should return data matching the EmailContent interface
    return response.data;
  } catch (error: any) {
    console.error(`[getEmailContent] Error fetching content for email ${emailId}:`, error);
    if (error.response) {
      console.error('Error response data:', error.response.data);
      throw new Error(error.response.data.detail || `Error loading content for email ${emailId}` );
    } else {
      throw new Error('Network error or unexpected issue loading email content');
    }
  }
};

/**
 * Submit email filter criteria for analysis
 */
export const submitFilterForAnalysis = async (filter: EmailFilter): Promise<{ job_id: string }> => {
  try {
    // Ensure the endpoint path is correct (singular 'email')
    const response = await apiClient.post<{ job_id: string }>('/email/analyze', filter);
    return response.data;
  } catch (error) {
    console.error('Error submitting filter for analysis:', error);
    // Re-throw the error so the calling component can handle it (e.g., show toast)
    throw error;
  }
};

/* 
// --- Old submitEmailIdsForAnalysis - REMOVED (or keep commented out) ---
export const submitEmailIdsForAnalysis = async (emailIds: string[]) => {
  // ... old implementation ...
};
*/
