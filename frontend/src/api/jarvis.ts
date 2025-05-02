import apiClient from './apiClient';

// --- TypeScript Interfaces --- 

// Interface for displaying tokens (matches JarvisTokenDisplay schema)
export interface JarvisTokenDisplay {
    id: number;
    token_nickname: string;
    created_at: string; // Representing datetime as string
    last_used_at?: string | null;
    is_valid: boolean;
    endpoint_url: string;
}

// Interface for creating a token (matches JarvisTokenCreate schema)
export interface JarvisTokenCreate {
    token_nickname: string;
    raw_token_value: string;
    endpoint_url: string;
}

// --- API Functions --- 

/**
 * Fetches the list of external Jarvis tokens added by the current user.
 */
export const listExternalTokens = async (): Promise<JarvisTokenDisplay[]> => {
    try {
        const response = await apiClient.get<JarvisTokenDisplay[]>('/v1/jarvis/external-tokens');
        return response.data;
    } catch (error) {
        console.error("Error fetching external Jarvis tokens:", error);
        // Consider more specific error handling or re-throwing
        throw error;
    }
};

/**
 * Adds a new external Jarvis token for the current user.
 * @param tokenData - The nickname and raw value of the token to add.
 */
export const addExternalToken = async (tokenData: JarvisTokenCreate): Promise<JarvisTokenDisplay> => {
    try {
        const response = await apiClient.post<JarvisTokenDisplay>('/v1/jarvis/external-tokens', tokenData);
        return response.data;
    } catch (error) {
        console.error("Error adding external Jarvis token:", error);
        // Handle specific errors like 409 Conflict (duplicate nickname) if needed
        // if (axios.isAxiosError(error) && error.response?.status === 409) { ... }
        throw error;
    }
};

/**
 * Deletes a specific external Jarvis token by its ID.
 * @param tokenId - The ID of the token to delete.
 */
export const deleteExternalToken = async (tokenId: number): Promise<void> => {
    try {
        await apiClient.delete(`/v1/jarvis/external-tokens/${tokenId}`);
        // No content is returned on successful DELETE (status 204)
    } catch (error) {
        console.error(`Error deleting external Jarvis token ID ${tokenId}:`, error);
        throw error;
    }
}; 