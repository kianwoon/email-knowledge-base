import axiosInstance from './apiClient';

// Define interfaces for Token data (align with backend models)
// Consider sharing types via a common package if project grows

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
}

// Interface for updating a token (sent to backend)
export interface TokenUpdatePayload {
  name?: string;
  description?: string;
  sensitivity?: string;
  allow_rules?: string[];
  deny_rules?: string[];
  allow_embeddings?: string[];
  deny_embeddings?: string[];
  expiry?: string | null;
  is_active?: boolean;
}

// Interface for a token received from the backend
export interface Token {
  id: number;
  name: string;
  description?: string | null;
  sensitivity: string;
  token_preview: string;
  owner_email: string;
  created_at: string; // ISO string format from backend
  expiry?: string | null; // ISO string format or null
  is_active: boolean;
  allow_rules?: string[];
  deny_rules?: string[];
  allow_embeddings?: string[];
  deny_embeddings?: string[];
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

// --- API Functions --- 

/**
 * Fetch all tokens associated with the current user.
 */
export const getUserTokens = async (): Promise<Token[]> => {
  console.log('API: Fetching user tokens...');
  try {
    const response = await axiosInstance.get<Token[]>('/token/');
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
    const response = await axiosInstance.post<TokenCreateResponse>('/token/', payload);
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
    await axiosInstance.delete(`/token/${tokenId}`);
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
    const response = await axiosInstance.get<Token>(`/token/${tokenId}`);
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
    const response = await axiosInstance.patch<Token>(`/token/${tokenId}`, payload);
    console.log(`API: Token ${tokenId} updated:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`API Error updating token ${tokenId}:`, error); 
    throw error;
  }
};

// Bundle existing tokens
export const bundleTokens = async (payload: TokenBundlePayload): Promise<Token> => {
  const response = await axiosInstance.post<Token>('/token/bundle', payload);
  return response.data;
};

// --- ADDED for Token Usage Report --- 

// Interface matching the backend response (TokenUsageStat from token.py)
export interface TokenUsageStat {
  token_id: number;
  token_name: string;
  token_description?: string | null;
  token_preview: string;
  usage_count: number;
  last_used_at?: string | null; // ISO string from backend
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

    const response = await axiosInstance.get<TokenUsageReportResponse>('/token/usage-report', {
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

    const response = await axiosInstance.get<TimeSeriesResponse>('/token/usage-timeseries', {
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