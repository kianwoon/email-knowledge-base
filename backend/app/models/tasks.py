from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class TaskType(str, Enum):
    """Enum for different types of background tasks."""
    PROCESS_EMAIL = "process_email"
    GENERATE_TAGS = "generate_tags"
    PROCESS_ATTACHMENT = "process_attachment"
    PROCESS_SHAREPOINT_FILE = "process_sharepoint_file"
    # Add other task types as needed

class TaskStatusEnum(str, Enum):
    """Enum for the status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # Add frontend-specific statuses if needed
    SUBMITTING = "submitting"
    POLLING_ERROR = "polling_error"
    FAILED_SUBMISSION = "failed_submission"

class TaskStatus(BaseModel):
    """Model representing the status of a background task."""
    task_id: str = Field(..., description="Unique identifier for the task.")
    status: TaskStatusEnum = Field(..., description="Current status of the task.")
    message: Optional[str] = Field(None, description="Optional message providing more details about the status.")
    result: Optional[Dict[str, Any]] = Field(None, description="Optional dictionary containing the task result upon completion.")
    error: Optional[str] = Field(None, description="Optional error message if the task failed.")
    task_type: Optional[TaskType] = Field(None, description="The type of task being executed.")
    progress: Optional[float] = Field(None, description="Optional progress percentage (0.0 to 100.0).")
    details: Optional[Dict[str, Any]] = Field(None, description="Optional dictionary for additional task-specific details.") 