import apiClient from './apiClient'; // Import the shared client
import { EmailFilter, EmailPreview, EmailContent, PaginatedEmailPreviewResponse } from '../types/email';

/**
 * Get email folders from Outlook
 */
export const getEmailFolders = async () => {
  try {
    // Use apiClient directly
    const response = await apiClient.get('/emails/folders');
    return response.data;
  } catch (error) {
    console.error('Error getting email folders:', error);
    // For demo purposes, return mock data
    return [
      { id: 'inbox', displayName: 'Inbox' },
      { id: 'archive', displayName: 'Archive' },
      { id: 'sent', displayName: 'Sent Items' },
      { id: 'drafts', displayName: 'Drafts' },
      { id: 'deleted', displayName: 'Deleted Items' }
    ];
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
      '/emails/preview', // Correct endpoint path
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
export const submitFilterForAnalysis = async (filter: EmailFilter) => {
  console.log(`[api/email] Submitting filter for analysis to backend...`, filter);
  
  try {
    // Use apiClient directly
    const response = await apiClient.post<{ job_id: string }>('/emails/analyze', filter); // Use apiClient
    
    console.log('[api/email] Backend analysis submission successful:', response.data);
    return response.data;
  } catch (error) {
    console.error('[api/email] Error submitting filter for analysis to backend:', error);
    throw error; 
  }
};

/* 
// --- Old submitEmailIdsForAnalysis - REMOVED (or keep commented out) ---
export const submitEmailIdsForAnalysis = async (emailIds: string[]) => {
  // ... old implementation ...
};
*/
