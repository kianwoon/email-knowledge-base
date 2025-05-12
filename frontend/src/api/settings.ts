import { api } from './index';

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
  const response = await api.get('/api/v1/settings/');
  return response.data;
};

// Update user settings
export const updateUserSettings = async (settings: Partial<UserSettings>): Promise<UserSettings> => {
  const response = await api.put('/api/v1/settings/', settings);
  return response.data;
}; 