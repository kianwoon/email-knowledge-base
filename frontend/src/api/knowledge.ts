import apiClient from './apiClient';
import axios from 'axios';

// Define the expected response structure for the summary
export interface CollectionSummaryResponse {
  count: number;
  // Add other summary stats here if needed in the future
}

// Define valid collection names
export type KnowledgeCollectionName = 'email_knowledge' | 'email_knowledge_base';

// NEW: Define the expected response structure for the combined summary
export interface KnowledgeSummaryResponse {
  raw_data_count?: number;
  sharepoint_raw_data_count?: number;
  s3_raw_data_count?: number;
  azure_blob_raw_data_count?: number;
  custom_raw_data_count?: number;
  vector_data_count?: number;
  email_facts_count?: number;
  last_updated?: string | null;
}

/**
 * Fetches the summary statistics for a specific knowledge collection.
 * @param collectionName The name of the collection ('email_knowledge' or 'email_knowledge_base').
 * @returns A promise resolving to the collection summary data.
 */
export const getCollectionSummary = async (
  collectionName: KnowledgeCollectionName
): Promise<CollectionSummaryResponse> => {
  console.log(`[api/knowledge] Fetching summary for collection: ${collectionName}`);
  try {
    // Endpoint path matches the backend route we will create (including prefix)
    const response = await apiClient.get<CollectionSummaryResponse>(
      `/knowledge/summary/${collectionName}`
    );
    console.log(`[api/knowledge] Received summary for ${collectionName}:`, response.data);
    return response.data;
  } catch (error: any) {
    console.error(`[api/knowledge] Error fetching summary for ${collectionName}:`, error.response?.data || error.message);
    // Re-throw a more specific error message if available
    throw new Error(
      error.response?.data?.detail || 
      `Failed to fetch summary for collection ${collectionName}`
    );
  }
};

// NEW: Function to fetch the combined knowledge base summary
/**
 * Fetches the combined summary statistics for the knowledge base.
 * Assumes a backend endpoint GET /knowledge/summary exists.
 * @returns A promise resolving to the knowledge base summary data.
 */
export const getKnowledgeBaseSummary = async (): Promise<KnowledgeSummaryResponse> => {
  console.log(`[api/knowledge] Fetching combined knowledge base summary...`);
  try {
    const response = await axios.get<KnowledgeSummaryResponse>('/api/v1/knowledge/summary');
    return response.data;
  } catch (error: any) {
    console.error(`[api/knowledge] Error fetching combined summary:`, error.response?.data || error.message);
    // Provide default values or re-throw a more specific error
    // Ensure the returned object matches the KnowledgeSummaryResponse structure even on error
    return {
      raw_data_count: 0,
      sharepoint_raw_data_count: 0,
      s3_raw_data_count: 0,
      azure_blob_raw_data_count: 0,
      custom_raw_data_count: 0,
      vector_data_count: 0,
      email_facts_count: 0,
      last_updated: null,
    };
  }
};