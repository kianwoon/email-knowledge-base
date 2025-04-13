from typing import Optional, Any
from pydantic import BaseModel, Field

class TaskStatusResponse(BaseModel):
    # Allow task_id to be None for cases where no task is submitted
    task_id: Optional[str] = Field(None, description="The unique ID of the background task, or null if no task was started.")
    status: str = Field(..., description="The current status of the task (e.g., PENDING, STARTED, PROGRESS, SUCCESS, FAILURE, NO_OP).")
    message: Optional[str] = Field(None, description="An optional message providing more details about the status.")
    progress: Optional[float] = Field(None, ge=0, le=100, description="Optional progress percentage (0-100).")
    result: Optional[Any] = Field(None, description="Optional result of the task if completed successfully.")

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