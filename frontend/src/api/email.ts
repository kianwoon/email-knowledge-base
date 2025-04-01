import axios from 'axios';
import { EmailFilter } from '../types/email';

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
export const getEmailPreviews = async (filterParams: EmailFilter) => {
  try {
    const response = await api.post('/emails/preview', filterParams);
    return response.data;
  } catch (error) {
    console.error('Error getting email previews:', error);
    // For demo purposes, return mock data
    return Array(5).fill(0).map((_, i) => ({
      id: `email_${i}`,
      subject: `Sample Email ${i + 1}`,
      sender: 'John Doe',
      received_date: new Date().toISOString(),
      snippet: 'This is a sample email snippet for preview purposes...',
      has_attachments: i % 2 === 0, // Every other email has attachments
      importance: ['high', 'normal', 'low'][i % 3] // Rotate through importance levels
    }));
  }
};

/**
 * Get full content of a specific email
 */
export const getEmailContent = async (emailId: string) => {
  try {
    const response = await api.get(`/emails/content/${emailId}`);
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
    const response = await api.post('/emails/analyze', emailIds);
    return response.data;
  } catch (error) {
    console.error('Error submitting emails for analysis:', error);
    throw error;
  }
};

export default api;
