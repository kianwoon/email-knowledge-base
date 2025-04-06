import apiClient from './apiClient'; // Import the shared client
import { EmailFilter, EmailPreview, PaginatedEmailPreviewResponse } from '../types/email';

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
  console.log(`[getEmailPreviews] Checking token. localStorage.getItem('accessToken') value:`, localStorage.getItem('accessToken'));
  const token = localStorage.getItem('accessToken');
  if (!token) throw new Error('No access token found');
  
  // Construct query parameters
  const params: any = { 
    page,
    per_page 
  };

  // Use next_link directly if provided, ignoring other filter params as MS Graph handles it
  if (next_link) {
    params.next_link = next_link;
    // Clear filter params if using next_link, as it contains all context
    // Alternatively, the backend can prioritize next_link over filter params
  }

  // Log the request details
  console.log('[API Call] getEmailPreviews - Request Params:', params, 'Body (Filter):', filter);
  
  try {
    const response = await apiClient.post(
      `/emails/preview`, // <-- Corrected path with /emails prefix
      filter, // Send filter criteria in the body
      {
        params: params, // Send pagination params in query string
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    console.log('[API Response] getEmailPreviews:', response.data);
    // Ensure the response structure matches PaginatedEmailPreviewResponse
    return response.data;
  } catch (error: any) {
    console.error('Error fetching email previews:', error.response?.data || error.message);
    throw new Error(error.response?.data?.detail || 'Failed to fetch email previews');
  }
};

/**
 * Get full content of a specific email
 */
export const getEmailContent = async (emailId: string) => {
  try {
    // Use apiClient directly
    const response = await apiClient.get(`/emails/content/${emailId}`); 
    return response.data;
  } catch (error) {
    console.error('Error getting email content:', error);
    // For demo purposes, return mock data
    return {
      id: emailId,
      internet_message_id: `message_${emailId}`,
      subject: 'Sample Email Content',
      sender: 'John Doe',
      sender_email: 'john.doe@example.com',
      recipients: ['user@example.com'],
      cc_recipients: [],
      received_date: new Date().toISOString(),
      body: 'This is the full content of the sample email. It contains more detailed information than the snippet.',
      is_html: false,
      folder_id: 'inbox',
      folder_name: 'Inbox',
      attachments: [],
      importance: 'normal'
    };
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
