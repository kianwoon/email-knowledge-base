import axiosInstance from './apiClient';
// import { apiDELETE, apiGET, apiPOST, apiPUT } from './apiClient'; // REMOVE THIS LINE
import apiClient from './apiClient'; // Import the configured axios instance

// Define interfaces for Token data (align with backend models)
// Consider sharing types via a common package if project grows

// Define TokenType Enum matching backend
export enum TokenType {
  PUBLIC = 'public',
  SHARE = 'share',
}

// Interface for creating a token (sent to backend)
export interface TokenCreatePayload {
  name: string;
  description?: string;
  sensitivity: string;
  allow_rules?: string[];
  deny_rules?: string[];
  allow_embeddings?: string[];
  deny_embeddings?: string[];
  expiry_days?: number | null;
  is_editable?: boolean;
  token_type?: TokenType;
  provider_base_url?: string;
  audience?: Record<string, any>;
  can_export_vectors?: boolean;
  allow_columns?: string[];
  allow_attachments?: boolean;
  row_limit?: number;
}

// Interface for updating a token (sent to backend)
export interface TokenUpdatePayload {
  name?: string;
  description?: string;
  sensitivity?: string;
  allow_rules?: string[];
  deny_rules?: string[];
  expiry?: string | null;
  expiry_days?: number | null;
  is_active?: boolean;
  is_editable?: boolean;
  provider_base_url?: string;
  audience?: Record<string, any>;
  can_export_vectors?: boolean;
  allow_columns?: string[];
  allow_attachments?: boolean;
  row_limit?: number;
}

// Interface for a token received from the backend
export interface Token {
  id: number;
  name: string;
  description: string | null;
  sensitivity: string;
  token_preview: string;
  owner_email: string;
  created_at: string; // ISO string format from backend
  expiry: string | null; // ISO string format or null
  is_active: boolean;
  is_editable: boolean;
  allow_rules: string[] | null;
  deny_rules: string[] | null;
  token_type: TokenType;
  provider_base_url?: string | null;
  audience?: Record<string, any> | null;
  accepted_by?: number | null;
  accepted_at?: string | null;
  can_export_vectors: boolean;
  allow_columns?: string[] | null;
  allow_attachments: boolean;
  row_limit: number;
}

// Interface for the response when creating a token (includes the raw value)
export interface TokenCreateResponse extends Token {
  token_value: string;
}

// Interface for bundling tokens
export interface TokenBundlePayload {
  token_ids: number[];
  name: string;
  description?: string;
}

// +++ ADDED: Interface matching the backend SharedMilvusResult +++
export interface SharedMilvusResult {
  id: string;
  score: number;
  metadata: Record<string, any>;
}
// --- END ADDITION ---

// --- START: Types for Catalog Search ---

// Matches backend/app/schemas/shared_knowledge.py -> CatalogSearchRequest
export interface CatalogSearchRequest {
  query: string;
  sender?: string | null;
  date_from?: string | null; // ISO date string (YYYY-MM-DD)
  date_to?: string | null;   // ISO date string (YYYY-MM-DD)
  limit?: number; // Optional limit from frontend, backend will cap by token
}

// Matches backend/app/schemas/shared_knowledge.py -> CatalogSearchResult
// Represents a single item returned from the catalog search.
// The actual keys present will depend on the token's allow_columns.
export interface CatalogSearchResult {
  [key: string]: any; // Use a generic index signature as columns vary
  // Example common fields (actual fields depend on token allow_columns):
  // id?: number | string;
  // subject?: string;
  // sender_name?: string;
  // created_at?: string; // ISO datetime string
  // content_preview?: string;
  // attachment_filenames?: string[];
  // attachment_count?: number;
}

// --- END: Types for Catalog Search ---

// --- API Functions --- 

/**
 * Fetch all tokens associated with the current user.
 */
export const getUserTokens = async (): Promise<Token[]> => {
  console.log('API: Fetching user tokens...');
  try {
    const response = await axiosInstance.get<Token[]>('/v1/token/');
    console.log('API: Tokens received:', response.data);
    return response.data;
  } catch (error) {
    console.error('API Error fetching tokens:', error);
    throw error; // Re-throw for component error handling
  }
};

/**
 * Create a new token.
 */
export const createToken = async (payload: TokenCreatePayload): Promise<TokenCreateResponse> => {
  console.log('API: Creating token:', payload);
  try {
    // The backend POST /token/ route returns TokenCreateResponse which includes token_value
    // The Token type includes optional token_value to handle this.
    const response = await axiosInstance.post<TokenCreateResponse>('/v1/token/', payload);
    console.log('API: Token created:', response.data);
    return response.data;
  } catch (error) {
    console.error('API Error creating token:', error);
    throw error;
  }
};

/**
 * Delete a specific token by its ID.
 */
export const deleteTokenApi = async (tokenId: string): Promise<void> => {
  console.log(`API: Deleting token: ${tokenId}...`);
  try {
    await axiosInstance.delete(`/v1/token/${tokenId}`);
    console.log(`API: Token ${tokenId} deleted successfully.`);
  } catch (error) {
    console.error(`API Error deleting token ${tokenId}:`, error);
    throw error;
  }
};

/**
 * Fetch a single token by its ID.
 */
export const getTokenById = async (tokenId: string): Promise<Token> => {
  console.log(`API: Fetching token by ID: ${tokenId}...`);
  try {
    const response = await axiosInstance.get<Token>(`/v1/token/${tokenId}`);
    console.log(`API: Token ${tokenId} received:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`API Error fetching token ${tokenId}:`, error);
    throw error; // Re-throw for component error handling
  }
};

/**
 * Update an existing token.
 */
export const updateToken = async (tokenId: string, payload: TokenUpdatePayload): Promise<Token> => {
  console.log(`API: Updating token ${tokenId}:`, payload);
  try {
    // Backend returns standard TokenResponse (mapped to Token type)
    const response = await axiosInstance.patch<Token>(`/v1/token/${tokenId}`, payload);
    console.log(`API: Token ${tokenId} updated:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`API Error updating token ${tokenId}:`, error); 
    throw error;
  }
};

// Bundle existing tokens
export const bundleTokens = async (payload: TokenBundlePayload): Promise<Token> => {
  const response = await axiosInstance.post<Token>('/v1/token/bundle', payload);
  return response.data;
};

// +++ ADDED: Function to test token search permissions +++
/**
 * Allows the token owner to test the search results for a specific token.
 * Calls the backend endpoint that applies the token's permissions against the owner's data.
 */
export const testTokenSearch = async (
  tokenId: number,
  query: string
): Promise<SharedMilvusResult[]> => {
  console.log(`API: Testing search for token ID ${tokenId} with query: "${query}"`);
  try {
    const payload = { query };
    const response = await axiosInstance.post<SharedMilvusResult[]>(
      `/v1/token/${tokenId}/test-search`, 
      payload
    );
    console.log(`API: Test search for token ${tokenId} returned ${response.data.length} results.`);
    return response.data;
  } catch (error: any) {
    // Log the error and re-throw for component handling
    console.error(`API Error testing search for token ${tokenId}:`, error);
    // Extract backend error detail if available
    const detail = error?.response?.data?.detail || error.message || 'Failed to perform test search.';
    throw new Error(detail);
  }
};
// --- END ADDITION ---

// --- ADDED for Token Usage Report --- 

// Interface matching the backend response (TokenUsageStat from token.py)
export interface TokenUsageStat {
  token_id: number;
  token_name: string;
  token_description?: string | null;
  token_preview: string;
  usage_count: number;
  last_used_at?: string | null; // ISO string from backend
  blocked_column_count?: number; // Added this field based on P6 requirements
}

// Interface for the overall usage report response
export interface TokenUsageReportResponse {
  usage_stats: TokenUsageStat[];
}

/**
 * Fetch usage statistics for tokens owned by the current user.
 * Optionally filters by date range (YYYY-MM-DD format).
 */
export const getTokenUsageReport = async (
  startDate?: string, 
  endDate?: string
): Promise<TokenUsageReportResponse> => {
  console.log(`API: Fetching token usage report (Start: ${startDate}, End: ${endDate})`);
  try {
    const params = new URLSearchParams();
    if (startDate) {
      params.append('start_date', startDate);
    }
    if (endDate) {
      params.append('end_date', endDate);
    }

    const response = await axiosInstance.get<TokenUsageReportResponse>('/v1/token/usage-report', {
      params: params
    });
    console.log('API: Token usage report received:', response.data);
    return response.data;
  } catch (error) {
    console.error('API Error fetching token usage report:', error);
    throw error; // Re-throw for component error handling
  }
};
// --- END ADDED ---

// --- ADDED for Time Series API --- 

// Interface matching the backend response (TimeSeriesDataPoint from token.py)
export interface TimeSeriesDataPoint {
  date: string; // Expecting date string like YYYY-MM-DD
  usage_count: number;
}

// Interface for the overall time series response
export interface TimeSeriesResponse {
  time_series: TimeSeriesDataPoint[];
}

/**
 * Fetch time series usage statistics for tokens owned by the current user.
 * Optionally filters by date range (YYYY-MM-DD format) and token ID.
 */
export const getTokenUsageTimeSeries = async (
  tokenId?: number | string, // Can be number or the string 'all'
  startDate?: string,
  endDate?: string
): Promise<TimeSeriesResponse> => {
  console.log(`API: Fetching token usage time series (Token: ${tokenId}, Start: ${startDate}, End: ${endDate})`);
  try {
    const params = new URLSearchParams();
    if (tokenId && tokenId !== 'all') {
      params.append('token_id', tokenId.toString());
    }
    if (startDate) {
      params.append('start_date', startDate);
    }
    if (endDate) {
      params.append('end_date', endDate);
    }

    const response = await axiosInstance.get<TimeSeriesResponse>('/v1/token/usage-timeseries', {
      params: params
    });
    console.log('API: Token usage time series received:', response.data);
    return response.data;
  } catch (error) {
    console.error('API Error fetching token usage time series:', error);
    throw error; // Re-throw for component error handling
  }
};
// --- END ADDED ---

// GET /token/{token_id} - Fetch details for a specific token
export const getTokenDetails = async (tokenId: number): Promise<any> => {
  try {
    // Add /v1 prefix
    const response = await axiosInstance.get<any>(`/v1/token/${tokenId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching details for token ${tokenId}:`, error);
    throw error; // Re-throw to allow caller handling
  }
};

// --- NEW: Regenerate Token Secret ---

// Interface for the response from the regeneration endpoint
interface RegenerateResponse {
  new_token_value: string;
}

/**
 * Regenerates the secret for a given token ID.
 * Returns the new full token value (prefix.secret).
 */
export const regenerateTokenSecret = async (tokenId: number): Promise<RegenerateResponse> => {
  console.log(`API: Regenerating secret for token ID ${tokenId}`);
  try {
    const response = await axiosInstance.post<RegenerateResponse>(`/v1/token/${tokenId}/regenerate`);
    console.log(`API: Secret regenerated successfully for token ${tokenId}.`);
    return response.data; // Should contain { new_token_value: "..." }
  } catch (error: any) {
    console.error(`API Error regenerating secret for token ${tokenId}:`, error);
    // Extract backend error detail if available
    const detail = error?.response?.data?.detail || error.message || 'Failed to regenerate token secret.';
    throw new Error(detail);
  }
};
// --- END NEW ---

// --- START: API Function for Catalog Search Test ---

/**
 * Tests the /api/v1/shared-knowledge/search_catalog endpoint with a specific token.
 * @param tokenId The ID of the token to test (used for context).
 * @param requestBody The search parameters (query, filters, limit).
 * @param kbTokenValue The actual Knowledge Base token string (e.g., "kb_...") to use for authorization.
 * @returns A promise resolving to an array of catalog search results.
 */
export const testTokenCatalogSearch = async (
  tokenId: number, 
  requestBody: CatalogSearchRequest,
  kbTokenValue: string | null // Added parameter for the KB token value
): Promise<CatalogSearchResult[]> => {
  // For catalog search, we need one of:
  // 1. The full token value (with secret)
  // 2. The token prefix (if owner is authenticated)
  if (!kbTokenValue) {
    throw new Error('Knowledge Base token identifier is required for catalog search test.');
  }
  
  // Remove any inadvertent whitespace that might be causing issues
  const cleanedToken = kbTokenValue.trim();
  
  // Check if token is prefix-only (no period) - this is owner-only mode
  const ownerOnlyMode = !cleanedToken.includes('.');
  if (ownerOnlyMode) {
    console.log('Using token in owner-only mode (prefix only)');
  }
  
  try {
    // Get the user's session JWT token from cookies
    // This will help authenticate as the owner when using prefix-only mode
    const getUserToken = (): string => {
      const cookies = document.cookie.split('; ');
      const accessTokenCookie = cookies.find(cookie => cookie.startsWith('access_token='));
      if (accessTokenCookie) {
        return accessTokenCookie.split('=')[1];
      }
      return '';
    };
    
    const sessionToken = getUserToken();
    
    // Use apiClient instance directly
    const response = await apiClient.post<CatalogSearchResult[]>(
      '/v1/shared-knowledge/search_catalog',
      requestBody,
      {
        headers: {
          // Use both the KB token and session token for authentication
          'Authorization': `Bearer ${cleanedToken}`,
          // Add the session token as a custom header
          'X-User-Session': sessionToken
        }
      }
    );
    return response.data;
  } catch (error: any) {
    console.error('Error in catalog search test:', error);
    throw new Error(error.response?.data?.detail || 'Failed to perform catalog search test');
  }
};

// --- END: API Function for Catalog Search Test ---

export interface TokenResponse extends Token {
  token_value?: string; // Add this field for token owner responses
}

/**
 * Debug function to validate a token's format
 */
export const debugTokenValue = async (tokenId: number): Promise<any> => {
  console.log(`API: Debugging token value format for ID ${tokenId}`);
  try {
    const response = await axiosInstance.get<any>(`/v1/token/${tokenId}/debug-token-value`);
    console.log(`Debug token response:`, response.data);
    return response.data;
  } catch (error: any) {
    console.error(`Error debugging token value for ID ${tokenId}:`, error);
    throw new Error(error.response?.data?.detail || 'Failed to debug token value.');
  }
};

/**
 * Test catalog search as the token owner, using a dedicated owner-only endpoint.
 * This provides a more reliable way for token owners to test their tokens.
 */
export const ownerTestTokenCatalogSearch = async (
  tokenId: number,
  tokenPrefix: string,
  requestBody: CatalogSearchRequest
): Promise<CatalogSearchResult[]> => {
  console.log(`API: Using owner-only token test for token prefix: ${tokenPrefix}`);
  
  try {
    // Create the request with the token prefix
    const ownerRequest = {
      ...requestBody,
      token_prefix: tokenPrefix
    };
    
    // Call the owner-specific endpoint
    const response = await apiClient.post<CatalogSearchResult[]>(
      '/v1/shared-knowledge/owner_search_catalog',
      ownerRequest
    );
    
    return response.data;
  } catch (error: any) {
    console.error('Error in owner catalog search test:', error);
    throw new Error(error.response?.data?.detail || 'Failed to perform owner catalog search test');
  }
};