import apiClient from './apiClient';

// Define the expected response structure for the summary
export interface CollectionSummaryResponse {
  count: number;
  // Add other summary stats here if needed in the future
}

// Define valid collection names
export type KnowledgeCollectionName = 'email_knowledge' | 'email_knowledge_base';

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