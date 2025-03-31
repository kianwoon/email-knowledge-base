import axios from 'axios';
import { EmailReview, EmailApproval } from '../types/email';

// Determine if we're in production by checking the current URL
const isProduction = window.location.hostname !== 'localhost';
const API_BASE_URL = isProduction 
  ? 'https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app'
  : (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');

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
 * Get pending email reviews
 */
export const getPendingReviews = async (filters: any = {}) => {
  try {
    const response = await api.get('/review/pending', { params: filters });
    return response.data;
  } catch (error) {
    console.error('Error getting pending reviews:', error);
    throw error;
  }
};

/**
 * Approve or reject an email review
 */
export const submitReviewDecision = async (emailId: string, approval: EmailApproval) => {
  try {
    const response = await api.post(`/review/decision/${emailId}`, approval);
    return response.data;
  } catch (error) {
    console.error('Error submitting review decision:', error);
    throw error;
  }
};

/**
 * Bulk approve or reject email reviews
 */
export const submitBulkReviewDecision = async (emailIds: string[], approval: EmailApproval) => {
  try {
    const response = await api.post('/review/bulk-decision', {
      email_ids: emailIds,
      ...approval
    });
    return response.data;
  } catch (error) {
    console.error('Error submitting bulk review decision:', error);
    throw error;
  }
};

/**
 * Get review history
 */
export const getReviewHistory = async (filters: any = {}) => {
  try {
    const response = await api.get('/review/history', { params: filters });
    return response.data;
  } catch (error) {
    console.error('Error getting review history:', error);
    throw error;
  }
};
