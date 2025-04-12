import logging
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict

from app.celery_app import celery_app
from celery.result import AsyncResult

# Import user dependency if needed for authorization (e.g., only allow user to check their own tasks)
from app.dependencies.auth import get_current_active_user
from app.models.user import User, UserDB # Import UserDB
# Import DB Session Dependency
from app.db.session import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[float] = None
    details: Optional[Any] = None # Can be str or dict

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status of a Celery task by its ID."""
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        
        status = task_result.state
        details = None
        progress = None

        if task_result.info:
            if isinstance(task_result.info, dict):
                details = task_result.info.get('status', 'Processing...') 
                progress = task_result.info.get('progress')
                # If the result is stored in info upon success/failure
                if status in ['SUCCESS', 'FAILURE'] and 'result' in task_result.info:
                    details = task_result.info['result']
            elif isinstance(task_result.info, Exception):
                details = str(task_result.info)
                status = 'FAILURE' # Ensure status reflects failure
            else:
                details = str(task_result.info) # Fallback for other types

        # If task failed but info wasn't an Exception dict, result might hold exception
        if status == 'FAILURE' and details is None and task_result.result:
             details = f"Task failed: {str(task_result.result)}" # Include failure context
        elif status == 'SUCCESS' and details is None:
             # Don't return the raw result, just confirm success.
             # If specific result info is needed, extract serializable parts carefully.
             details = "Task completed successfully." # Simple success message
             # Example if counts were needed (assuming result is a tuple like (succeeded, failed, ...)):
             # try:
             #     result_data = task_result.result
             #     if isinstance(result_data, tuple) and len(result_data) >= 2:
             #         details = f"Completed. Processed: {result_data[0]}, Failed: {result_data[1]}"
             #     else:
             #        details = "Task completed successfully."
             # except Exception as e:
             #     logger.warning(f"Could not parse successful task result for {task_id}: {e}")
             #     details = "Task completed successfully."

        return {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "details": details
        }
    except Exception as e:
        # Log the exception
        # Consider specific exceptions if needed
        raise HTTPException(status_code=500, detail=f"Error fetching task status: {str(e)}")

# +++ New Endpoint to get latest active KB task +++
@router.get("/my_latest_kb_task", response_model=Optional[TaskStatusResponse], status_code=status.HTTP_200_OK)
async def get_my_latest_kb_task_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Gets the status of the most recently dispatched knowledge base task for the current user, if active."""
    try:
        # Fetch only the last_kb_task_id field for the user
        task_id_result = db.query(UserDB.last_kb_task_id).filter(UserDB.email == current_user.email).first()
        
        if not task_id_result or not task_id_result[0]:
            # No task ID stored, so no active task to report
            return None # FastAPI handles Optional[Model] by returning null with 200 OK

        task_id = task_id_result[0]
        
        try:
            task_result = AsyncResult(task_id, app=celery_app)
            status = task_result.state
        except Exception as task_error:
            logger.error(f"Error retrieving task result for task_id {task_id}: {str(task_error)}")
            # If we can't get the task status, assume it's no longer active
            return None

        # Define active states (adjust as needed)
        active_states = {'PENDING', 'RECEIVED', 'STARTED', 'RETRY', 'PROGRESS'}

        if status in active_states:
            # Task is active, return its status using the same logic as /status/{task_id}
            details = None
            progress = None
            
            try:
                if task_result.info:
                    if isinstance(task_result.info, dict):
                        details = task_result.info.get('status', 'Processing...') 
                        progress = task_result.info.get('progress')
                    else:
                        details = str(task_result.info) # Fallback
            except Exception as info_error:
                logger.warning(f"Error retrieving task info for task_id {task_id}: {str(info_error)}")
                details = "Processing..."
                
            return {
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "details": details
            }
        else:
            # Task exists but is finished (SUCCESS, FAILURE, REVOKED)
            return None # Return null as it's not active
            
    except Exception as e:
        logger.error(f"Error in get_my_latest_kb_task_status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve latest task status.")
# --- End New Endpoint --- 