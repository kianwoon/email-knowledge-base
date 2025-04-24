from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from enum import Enum

class TaskStatusEnum(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    FAILURE = "FAILURE"
    SUCCESS = "SUCCESS"
    PROGRESS = "PROGRESS"
    # Custom / derived statuses
    PARTIAL_FAILURE = "PARTIAL_FAILURE" # Added for jobs with mixed results
    UNKNOWN = "UNKNOWN"

class TaskStatus(BaseModel):
    task_id: str
    status: TaskStatusEnum = TaskStatusEnum.UNKNOWN
    progress: Optional[int] = None  # Optional progress percentage
    message: Optional[str] = None # Optional status message
    result: Optional[Any] = None    # Result of the task if completed
    meta: Optional[Dict[str, Any]] = None # Additional metadata from task state

# Generic response model for endpoints that just return a task ID
class TaskSubmissionResponse(BaseModel):
    task_id: str

# --- NEW: Response schema for triggering SharePoint sync --- 
# Matches the structure expected by the frontend (frontend/src/api/apiClient.ts > processSyncList)
# Contains only the task_id
class ProcessSyncResponse(BaseModel):
    task_id: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "abc-123-xyz-789",
                }
            ]
        }
    }
# -----------------------------------------------------------

class TaskStatusResponse(BaseModel): # Used by S3 /ingest originally
    task_id: str
    status: str
    message: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "d8f8f8f8-f8f8-f8f8-f8f8-f8f8f8f8f8f8",
                    "status": "PROGRESS",
                    "message": "Processing file 3/10...",
                    "progress": 30.0
                },
                {
                    "task_id": None,
                    "status": "NO_OP",
                    "message": "No pending items found to process."
                },
                 {
                    "task_id": "e9g9g9g9-g9g9-g9g9-g9g9-g9g9g9g9g9g9",
                    "status": "COMPLETED",
                    "message": "Ingestion complete. Processed: 10, Failed: 0.",
                    "progress": 100.0,
                    "result": {"processed": 10, "failed": 0}
                }
            ]
        }
    } 