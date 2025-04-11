// Define enums mirroring the backend (tasks.py)

export enum TaskType {
    PROCESS_EMAIL = "process_email",
    GENERATE_TAGS = "generate_tags",
    PROCESS_ATTACHMENT = "process_attachment",
    PROCESS_SHAREPOINT_FILE = "process_sharepoint_file",
    // Add other task types as needed
}
  
export enum TaskStatusEnum {
    PENDING = "pending",
    RUNNING = "running",
    COMPLETED = "completed",
    FAILED = "failed",
    CANCELLED = "cancelled",
    // Add potential frontend-specific statuses if needed
    SUBMITTING = "submitting",
    POLLING_ERROR = "polling_error",
    FAILED_SUBMISSION = "failed_submission",
}
  
// Define the interface matching the backend TaskStatus Pydantic model
export interface TaskStatus {
    task_id: string; 
    status: TaskStatusEnum | string; // Allow string for flexibility if backend sends raw strings sometimes
    message?: string | null; // Match backend Optional[str]
    result?: Record<string, any> | null; // Match backend Optional[Dict[str, Any]]
    error?: string | null; // Match backend Optional[str]
    task_type?: TaskType | string | null; // Match backend Optional[TaskType]
    progress?: number | null; // Add progress if backend includes it (even if not in Pydantic model yet)
    details?: any | null; // Generic field for extra details backend might send
} 