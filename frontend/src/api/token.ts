import apiClient from './apiClient';

// Define interfaces for Token data (align with backend models)
// Consider sharing types via a common package if project grows

// Interface for the structure of an access rule
export interface AccessRule {
  field: string;       // e.g., 'tags', 'source_id'
  values: string[];    // e.g., ['project-x'], ['email-123']
}

// Interface for creating a token (sent to backend)
export interface TokenCreate {
  name: string;
  description?: string | null;
  sensitivity: string;
  allow_rules?: AccessRule[]; 
  deny_rules?: AccessRule[];  
  expiry?: string | null; // Align with backend model (TokenBase uses datetime)
}

// Interface for updating a token (sent to backend)
export interface TokenUpdate {
  name?: string;
  description?: string | null;
  sensitivity?: string;
  allow_topics?: string[]; // Optional array of strings
  deny_topics?: string[];  // Optional array of strings
  is_active?: boolean; // Keep is_active as per backend model
  expiry?: string | null; // ISO 8601 format string or null
}

// Interface for a token received from the backend
export interface Token {
  id: number;
  name: string;
  description?: string | null;
  sensitivity: string;
  token_preview: string;
  owner_email: string;
  created_at: string; // Keep as string, conversion happens in UI
  expiry: string | null; // Keep as string
  is_active: boolean;
  allow_topics?: string[]; // Updated field
  deny_topics?: string[];  // Updated field
  token_value?: string; // Keep token_value for create response
}

// --- API Functions --- 

/**
 * Fetch all tokens associated with the current user.
 */
export const getUserTokens = async (): Promise<Token[]> => {
  console.log('API: Fetching user tokens...');
  try {
    const response = await apiClient.get<Token[]>('/token/');
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
export const createToken = async (tokenData: TokenCreate): Promise<Token> => {
  console.log('API: Creating token:', tokenData);
  try {
    // The backend POST /token/ route returns TokenCreateResponse which includes token_value
    // The Token type includes optional token_value to handle this.
    const response = await apiClient.post<Token>('/token/', tokenData);
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
    await apiClient.delete(`/token/${tokenId}`);
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
    const response = await apiClient.get<Token>(`/token/${tokenId}`);
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
export const updateToken = async (tokenId: string, tokenData: TokenUpdate): Promise<Token> => {
  console.log(`API: Updating token ${tokenId}:`, tokenData);
  try {
    // Backend returns standard TokenResponse (mapped to Token type)
    const response = await apiClient.patch<Token>(`/token/${tokenId}`, tokenData);
    console.log(`API: Token ${tokenId} updated:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`API Error updating token ${tokenId}:`, error); 
    throw error;
  }
};