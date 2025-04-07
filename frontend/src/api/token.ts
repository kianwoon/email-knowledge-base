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
  sensitivity: string; // Keep as string for now, conversion happens elsewhere if needed
  expiry?: string | null; // ISO 8601 format string or null
  is_editable: boolean;
  allow_rules: AccessRule[];
  deny_rules: AccessRule[];
}

// Interface for updating a token (sent to backend)
export interface TokenUpdate {
  name?: string;
  description?: string | null;
  sensitivity?: string; // Keep as string
  expiry?: string | null; // ISO 8601 format string or null
  is_editable?: boolean;
  allow_rules?: AccessRule[];
  deny_rules?: AccessRule[];
}

// Interface for a token received from the backend
export interface Token {
  id: string;
  name: string;
  description: string | null;
  token_value: string; // The actual token string
  sensitivity: string; // Keep as string
  created_at: string; // ISO 8601 format string
  expiry: string | null; // ISO 8601 format string or null
  is_editable: boolean;
  is_active: boolean; 
  allow_rules: AccessRule[];
  deny_rules: AccessRule[];
  owner_email?: string; // Assuming backend provides this
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
    // Ensure rules are arrays even if empty
    const payload = {
        ...tokenData,
        allow_rules: tokenData.allow_rules || [],
        deny_rules: tokenData.deny_rules || [],
    };
    const response = await apiClient.post<Token>('/token/', payload);
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
    // Ensure rules are included if provided, otherwise don't send empty arrays
    const payload: TokenUpdate = { ...tokenData };
    if (tokenData.allow_rules) {
        payload.allow_rules = tokenData.allow_rules.filter(rule => rule.field && rule.values.length > 0);
    }
    if (tokenData.deny_rules) {
        payload.deny_rules = tokenData.deny_rules.filter(rule => rule.field && rule.values.length > 0);
    }
    // Remove keys with undefined values explicitly if needed by backend, but usually not necessary
    // Object.keys(payload).forEach(key => payload[key] === undefined && delete payload[key]);

    // Use PATCH instead of PUT
    const response = await apiClient.patch<Token>(`/token/${tokenId}`, payload);
    console.log(`API: Token ${tokenId} updated:`, response.data);
    return response.data;
  } catch (error) {
    console.error(`API Error updating token ${tokenId}:`, error);
    throw error;
  }
}; 