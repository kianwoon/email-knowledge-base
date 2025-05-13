import { apiClient } from './client';

// Types for settings-related operations
export interface UserSettings {
  id: string;
  maxRounds: number;
  defaultModel: string;
  createdAt: Date;
  updatedAt: Date;
}

// Get user settings
export const getUserSettings = async (): Promise<UserSettings> => {
  const response = await apiClient.get('/settings/');
  return response.data;
};

// Update user settings
export const updateUserSettings = async (settings: Partial<UserSettings>): Promise<UserSettings> => {
  const response = await apiClient.put('/settings/', settings);
  return response.data;
}; 