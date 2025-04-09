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