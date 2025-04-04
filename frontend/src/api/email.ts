import apiClient from './apiClient'; // Import the shared client
import { EmailFilter, EmailPreview } from '../types/email';

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
export const getEmailPreviews = async (filterParams: EmailFilter & { page?: number; per_page?: number; next_link?: string }) => {
  try {
    // Directly clean the incoming parameters
    const cleanParams = Object.fromEntries(
      Object.entries(filterParams).filter(([_, value]) => 
        value !== undefined && 
        value !== null && 
        (Array.isArray(value) ? value.length > 0 : true) &&
        value !== '' // Also remove empty strings
      )
    );

    // --- ADD LOGGING --- 
    console.log('[api/email] Final parameters being sent to /emails/preview:', JSON.stringify(cleanParams));
    // --- END LOGGING ---

    console.log('[api/email] Sending email preview request params:', cleanParams);

    // Use apiClient directly
    const response = await apiClient.post<{
      items: EmailPreview[];
      total: number;
      next_link?: string;
      total_pages: number;
      current_page: number;
    }>(
      '/emails/preview',
      cleanParams
    );

    console.log('Email preview response:', response.data);

    return response.data;
  } catch (error) {
    console.error('Error getting email previews:', error);
    throw error;
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
