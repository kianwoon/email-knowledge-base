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
  next_link?: string // Optional: Pass the next_link from the previous response
): Promise<PaginatedEmailPreviewResponse> => {
  
  // REMOVE LOCALSTORAGE CHECK - Handled by cookie
  // console.log(`[getEmailPreviews] Checking token. localStorage.getItem('accessToken') value:`, localStorage.getItem('accessToken'));
  // const token = localStorage.getItem('accessToken');
  // if (!token) throw new Error('No access token found');
  
  // Construct query parameters
  const params: any = { 
    page,
    per_page 
  };

  // Use next_link directly if provided
  if (next_link) {
    params.next_link = next_link;
  }

  console.log('[API Call] getEmailPreviews - Request Params:', params, 'Body (Filter):', filter);
  
  try {
    const response = await apiClient.post(
      `/emails/preview`, 
      filter, // Send filter criteria in the body
      { 
        params: params, // Send pagination params in query string
        // REMOVE EXPLICIT HEADERS - Handled by cookie + apiClient
        // headers: { Authorization: `Bearer ${token}` }, 
      }
    );
    console.log('[API Response] getEmailPreviews:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('Error fetching email previews:', error.response?.data || error.message);
    throw new Error(error.response?.data?.detail || 'Failed to fetch email previews');
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
