import apiClient from './apiClient';

// Define the structure of the task status response from the backend
// Matches the TaskStatusResponse model in backend/app/routes/tasks.py
export interface TaskStatus {
  task_id: string;
  status: string; // e.g., 'PENDING', 'STARTED', 'PROGRESS', 'SUCCESS', 'FAILURE'
  progress?: number | null; // Percentage (0-100)
  details?: any | null; // Status message, result data, or error info
}

/**
 * Fetches the status of a background task from the backend.
 *
 * @param taskId - The ID of the task to check.
 * @returns A promise that resolves with the task status information.
 */
export const getTaskStatus = async (taskId: string): Promise<TaskStatus> => {
  if (!taskId) {
    throw new Error("Task ID is required to check status.");
  }

  console.debug(`[api/tasks] Fetching status for task_id: ${taskId}`);

  try {
    const response = await apiClient.get<TaskStatus>(`/v1/tasks/status/${taskId}`);

    console.debug(`[api/tasks] Status received for task ${taskId}:`, response.data);
    // Basic validation
    if (!response.data || response.data.task_id !== taskId) {
        console.error("[api/tasks] Invalid status response received:", response.data);
        throw new Error("Invalid status response received from server.");
    }
    return response.data;
  } catch (error: any) {
    console.error(`[api/tasks] Error fetching status for task ${taskId}:`, error);
    // Rethrow the error for the component to handle
    const errorMessage = error.response?.data?.detail || error.message || 'Failed to fetch task status.';
    throw new Error(errorMessage);
  }
};

// +++ Add function to get latest active KB task +++
export const getMyLatestKbTask = async (): Promise<TaskStatus | null> => {
  console.log('[API Call] Getting latest active KB task status...');
  try {
    // Assuming the backend endpoint is /tasks/my_latest_kb_task
    // This endpoint should return the full TaskStatus if an active task exists, otherwise null or 404
    const response = await apiClient.get<TaskStatus | null>('/v1/tasks/my_latest_kb_task');
    
    // The backend might return 200 OK with null body if no active task, 
    // or 404 Not Found. Handle appropriately.
    if (response.status === 200 && response.data) {
        console.log('[API Response] Found active KB task:', response.data);
        return response.data;
    } else {
        console.log('[API Response] No active KB task found or task finished.');
        return null; 
    }
  } catch (error: any) {
    // If the API returns 404 specifically, treat it as "no active task"
    if (error.response && error.response.status === 404) {
        console.log('[API Response] No active KB task found (404).');
        return null;
    }
    // Log other errors
    console.error('Error fetching latest KB task status:', error.response?.data || error.message);
    // Re-throw other errors so the calling component can potentially show a message
    throw new Error(error.response?.data?.detail || 'Failed to fetch latest task status');
  }
};
// +++ End Add function +++ 