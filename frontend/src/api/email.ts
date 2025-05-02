import apiClient from './apiClient'; // Import the shared client
import { EmailFilter, EmailPreview, EmailContent, PaginatedEmailPreviewResponse } from '../types/email';

/**
 * Get email folders from Outlook
 */
export const getEmailFolders = async () => {
  try {
    const response = await apiClient.get('/v1/email/folders');
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
  // Accept a single object containing all possible parameters
  params: EmailFilter & { page?: number; per_page?: number; next_link?: string }
): Promise<PaginatedEmailPreviewResponse> => {
  
  // Extract pagination parameters for the query string, using defaults
  const page = params.page ?? 1;
  const per_page = params.per_page ?? 10;
  const queryParams = { page, per_page };

  // Prepare the filter data for the body: use all params EXCEPT page/per_page
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { page: _page, per_page: _per_page, ...bodyFilter } = params;

  console.log(`[getEmailPreviews] Calling POST /v1/email/preview`);
  console.log(`[getEmailPreviews] Query Params: ${JSON.stringify(queryParams)}`);
  // Log the body filter, which might include next_link or other criteria
  console.log(`[getEmailPreviews] Body Filter: ${JSON.stringify(bodyFilter)}`); 

  try {
    // Use POST to /preview, send filter criteria (including next_link if present) in body, pagination in query
    const response = await apiClient.post<PaginatedEmailPreviewResponse>(
      '/v1/email/preview', 
      bodyFilter,          // Body contains filters and potentially next_link
      { params: queryParams } // Query string contains page and per_page
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
    const response = await apiClient.get(`/v1/emails/${emailId}/content`); 
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
    const response = await apiClient.post<{ job_id: string }>('/v1/email/analyze', filter);
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
