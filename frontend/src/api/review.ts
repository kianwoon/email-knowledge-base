import apiClient from './apiClient'; // Import the shared client
import { EmailPreview, EmailApproval } from '../types/email';

/**
 * Get pending email reviews
 */
export const getPendingReviews = async (params: { page?: number; per_page?: number } & Record<string, any> = {}) => {
  try {
    // Use apiClient directly
    const response = await apiClient.get('/v1/review/pending', { params });
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
    // Use apiClient directly
    const response = await apiClient.post(`/v1/review/decision/${emailId}`, approval);
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
    // Use apiClient directly
    const response = await apiClient.post('/v1/review/bulk-decision', {
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
    // Use apiClient directly
    const response = await apiClient.get('/v1/review/history', { params: filters });
    return response.data;
  } catch (error) {
    console.error('Error getting review history:', error);
    throw error;
  }
};
