import axios from 'axios';
import { EmailFilter, EmailPreview } from '../types/email';

// Get the API base URL from environment variables
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Get email folders from Outlook
 */
export const getEmailFolders = async () => {
  try {
    const response = await api.get('/emails/folders');
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

    const response = await api.post<{
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
    const response = await api.get(`/api/emails/content/${emailId}`);
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
 * Submit emails for LLM analysis
 */
export const analyzeEmails = async (emailIds: string[]) => {
  try {
    const response = await api.post('/api/emails/analyze', emailIds);
    return response.data;
  } catch (error) {
    console.error('Error submitting emails for analysis:', error);
    throw error;
  }
};

export default api;
