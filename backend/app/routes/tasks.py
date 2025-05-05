import logging
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict

from app.celery_app import celery_app
from celery.result import AsyncResult
from celery.backends.base import KeyValueStoreBackend  # Import for type checking

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
        # Ensure task_id is a string
        task_id_str = str(task_id)
        logger.debug(f"Getting status for task: {task_id_str}")
        
        task_result = AsyncResult(task_id_str, app=celery_app)
        
        # Safely get the state without accessing properties that might fail
        try:
            status = task_result.state
        except (ValueError, KeyError) as e:
            # This can happen with the "Exception information must include the exception type" error or missing key
            logger.warning(f"Error getting task state for {task_id_str}: {str(e)}")
            status = "UNKNOWN"
            
        details = None
        progress = None

        # Safely try to get task info
        try:
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
        except ValueError as e:
            # Handle the "Exception information must include the exception type" error
            if "Exception information must include the exception type" in str(e):
                logger.warning(f"Task {task_id_str} has invalid exception format: {str(e)}")
                details = f"Task failed with invalid exception format. The task may need to be re-run."
                status = "FAILURE"  # Mark as failed
            elif "returned an object instead of string" in str(e):
                # Handle internationalized error messages returning objects instead of strings
                logger.warning(f"Task {task_id_str} has invalid error format: {str(e)}")
                details = f"Task failed with localized error format issue. The task may need to be re-run."
                status = "FAILURE"  # Mark as failed
            else:
                # Re-raise unexpected ValueError
                raise

        # Handle corrupted task results that don't fit the expected structure
        if status == "FAILURE" and details is None:
            try:
                # Try to get the result, but handle ValueErrors from backend.exception_to_python
                result = task_result.result
                details = f"Task failed: {str(result)}"
            except ValueError as ve:
                if "Exception information must include the exception type" in str(ve):
                    # This is the specific error we're handling
                    details = "Task failed with corrupted exception data. The task may need to be re-run."
                else:
                    # Other ValueError, still provide a message
                    details = f"Task failed with error: {str(ve)}"
        elif status == 'SUCCESS' and details is None:
             # Don't return the raw result, just confirm success.
             # If specific result info is needed, extract serializable parts carefully.
             details = "Task completed successfully." # Simple success message

        return {
            "task_id": task_id_str,
            "status": status,
            "progress": progress,
            "details": details
        }
    except Exception as e:
        # Log the exception
        logger.error(f"Error fetching task status for task_id {task_id}: {str(e)}", exc_info=True)
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

        # Get the task ID and ensure it's a string
        task_id_raw = task_id_result[0]
        task_id = str(task_id_raw)  # Convert UUID or any other type to string
        logger.debug(f"Retrieved task_id for user {current_user.email}: {task_id} (type: {type(task_id_raw).__name__})")
        
        try:
            task_result = AsyncResult(task_id, app=celery_app)
            try:
                status = task_result.state
            except (ValueError, KeyError) as e:
                # Handle the "Exception information must include the exception type" error or missing key
                logger.warning(f"Error getting task state for {task_id}: {str(e)}")
                return None  # If we can't get the state, assume it's not active
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
            except ValueError as ve:
                # Handle the specific error we're seeing
                if "Exception information must include the exception type" in str(ve):
                    logger.warning(f"Task {task_id} has invalid exception format: {str(ve)}")
                    details = "Processing with invalid exception format"
                elif "returned an object instead of string" in str(ve):
                    logger.warning(f"Task {task_id} has invalid error format: {str(ve)}")
                    details = "Processing with localized error format issue"
                else:
                    logger.warning(f"Error retrieving task info for task_id {task_id}: {str(ve)}")
                    details = "Processing..."
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