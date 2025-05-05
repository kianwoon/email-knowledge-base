import logging
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, Union
import json
import re

from app.celery_app import celery_app
from celery.result import AsyncResult
from celery.backends.base import KeyValueStoreBackend  # Import for type checking
from celery.exceptions import TimeoutError as CeleryTimeoutError

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
    details: Optional[Any] = None # Can be str or dict (potentially containing translated messages)

# Helper function to safely convert i18n objects to strings
def safe_i18n_convert(value: Any) -> Union[str, Dict, Any]:
    """Safely convert potential i18n objects to strings for API responses."""
    if isinstance(value, dict):
        # Check if this looks like a simple i18n object (e.g., {'en': '...', 'cn': '...'}) 
        # or Celery's typical status/meta structure.
        lang_keys = [k for k in value.keys() if isinstance(k, str) and (len(k) == 2 or k.endswith((' (en)', ' (cn)')))]
        
        if lang_keys and len(lang_keys) == len(value): # All keys look like lang codes
            # Prioritize 'en', then 'cn', then first key
            if 'en' in value:
                return str(value['en'])
            if 'cn' in value:
                 return str(value['cn'])
            first_key = next(iter(value))
            return str(value[first_key])
        elif 'status' in value or 'progress' in value or 'result' in value: # Looks like Celery meta
             # Process known Celery meta fields recursively
            processed_dict = {}
            for k, v in value.items():
                processed_dict[k] = safe_i18n_convert(v)
            return processed_dict
        else:
            # Unknown dict structure, try converting values but keep structure
             return {k: safe_i18n_convert(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [safe_i18n_convert(item) for item in value]
    
    # For exceptions or other non-dict/list types, convert directly to string
    elif isinstance(value, Exception):
         return f"Error: {str(value)}"
    
    # Fallback for anything else
    try:
        return str(value)
    except Exception:
         return "[Unrepresentable Value]"

# Add a function to handle specific translation keys
def get_translated_status(status: str) -> str:
    """Get a properly translated status string for display (Simplified Chinese)."""
    status_map = {
        "PENDING": "待处理",  # Pending
        "RECEIVED": "已接收",  # Received
        "STARTED": "运行中",  # Started / Running
        "PROGRESS": "进行中", # Progress
        "SUCCESS": "成功",    # Success
        "FAILURE": "失败",    # Failed
        "RETRY": "重试中",    # Retrying
        "REVOKED": "已取消",  # Cancelled
        "UNKNOWN": "未知"     # Unknown
    }
    return status_map.get(status, status) # Default to original if no translation

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status of a Celery task by its ID."""
    try:
        task_id_str = str(task_id)
        logger.debug(f"Getting status for task: {task_id_str}")
        task_result = AsyncResult(task_id_str, app=celery_app)

        # --- Get Raw Status --- 
        try:
            status = task_result.state
            logger.info(f"Raw task state for {task_id_str}: {status}")
        except Exception as state_err:
            logger.warning(f"Error getting raw task state for {task_id_str}: {state_err}")
            status = "UNKNOWN"

        details: Any = None
        progress: Optional[float] = None
        processed_info: Any = None
        processed_result: Any = None

        # --- Process Task Info (Meta) --- 
        try:
            if task_result.info:
                processed_info = safe_i18n_convert(task_result.info)
                if isinstance(processed_info, dict):
                    # Extract details and progress from potentially processed dict
                    details = processed_info.get('status', 'Processing...') # Default details
                    raw_progress = processed_info.get('progress')
                    if isinstance(raw_progress, (int, float)): 
                        progress = float(raw_progress) 
                    elif isinstance(raw_progress, str) and raw_progress.replace('.', '', 1).isdigit():
                         try:
                            progress = float(raw_progress)
                         except ValueError:
                            progress = None # Ignore non-numeric progress strings
                    
                    # If successful/failed, the 'result' inside 'info' might be the final detail
                    if status in ['SUCCESS', 'FAILURE'] and 'result' in processed_info:
                         details = processed_info['result'] # Overwrite details with final result/error within info
                else:
                     # If conversion returned a simple string
                     details = processed_info 
        except ValueError as e:
            # Handle potential errors during info processing/conversion
            logger.warning(f"ValueError processing task info for {task_id_str}: {e}")
            # If this specific error occurs, override details completely
            if "returned an object instead of string" in str(e):
                 logger.warning(f"Overriding details due to i18n object error.")
                 details = get_translated_status(status) # Use translated status as detail
            elif "invalid exception format" in str(e):
                 logger.warning(f"Overriding details due to invalid exception format.")
                 details = "任务处理中 (格式错误)" # Chinese: Task processing (format error)
            elif details is None: # For other ValueErrors, set a generic error if details are still None
                details = f"Processing error: {str(e)[:100]}"
            
            # Don't automatically mark as FAILURE here for read errors
            # Let subsequent checks determine the final status
        except Exception as info_err:
             logger.error(f"Unexpected error processing task info for {task_id_str}: {info_err}", exc_info=True)
             if details is None:
                 details = "Error retrieving task details."

        # --- Check Task Result on Failure --- 
        if status == "FAILURE" and details is None:
            try:
                result_data = task_result.result # This might raise the ValueError itself
                processed_result = safe_i18n_convert(result_data)
                details = f"Task failed: {processed_result}" # Combine message with processed result/error
            except ValueError as ve:
                 logger.warning(f"ValueError reading task result for {task_id_str}: {ve}")
                 if "invalid exception format" in str(ve) or "returned an object" in str(ve):
                     details = "Task failed with internal error."
                 else:
                     details = f"Task failed: {str(ve)[:100]}"
            except Exception as res_err:
                 logger.error(f"Unexpected error reading task result for {task_id_str}: {res_err}", exc_info=True)
                 details = "Task failed: Error retrieving result."
        
        # --- Final Status Check & Cleanup --- 
        
        # Check if task.get() confirms completion without blocking indefinitely
        try:
             if status not in ['PENDING', 'STARTED', 'RETRY', 'PROGRESS']:
                task_result.get(timeout=0.1) # Raises exception if not ready/failed, confirms success if returns
                logger.info(f"Task {task_id_str} confirmed complete via get(). Setting status to SUCCESS.")
                status = "SUCCESS" # Force SUCCESS if get() returns without error
        except CeleryTimeoutError:
             logger.debug(f"Task {task_id_str} get() timed out, status remains {status}")
        except Exception as get_err:
             # If get() fails, it implies task failed or state is inconsistent
             logger.warning(f"Task {task_id_str} get() failed ({type(get_err).__name__}). Setting status to FAILURE.")
             status = "FAILURE"
             if details is None:
                 details = f"Task failed: {str(get_err)[:100]}"

        # If status is SUCCESS but details are missing, provide a default message
        if status == 'SUCCESS' and details is None:
             details = "Task completed successfully."
             if progress is None: # Ensure progress is 100% on success if not set
                 progress = 1.0 
        elif status == 'FAILURE' and details is None:
             details = "Task failed with unknown error."

        # Ensure progress is represented as 0.0 to 1.0 or null
        if progress is not None:
            try:
                progress_float = float(progress)
                if progress_float > 1.0: # Assume it might be 0-100 scale
                     progress_float = progress_float / 100.0
                progress = max(0.0, min(1.0, progress_float)) # Clamp between 0 and 1
            except (ValueError, TypeError):
                 logger.warning(f"Invalid progress value found for {task_id_str}: {progress}. Setting to null.")
                 progress = None

        # Final cleanup of details field just before returning
        if isinstance(details, str) and ("returned an object instead of string" in details or "common.status" in details):
            logger.warning(f"Cleaning known i18n error string from details for task {task_id_str}. Original: '{details}'")
            # ALWAYS replace details with the simple translated status if the error string is found
            details = get_translated_status(status)
            logger.info(f"Cleaned details for task {task_id_str}: '{details}'")
        
        # Ensure details are stringified if they are complex objects at this point (shouldn't happen often)
        if not isinstance(details, (str, type(None))):
             try:
                 details = json.dumps(details)
             except Exception:
                 details = str(details)

        logger.info(f"Task {task_id_str} final status response before return: state={status}, details='{details}'")

        # Prepare the final response dictionary
        response_data = {
            "task_id": task_id_str,
            "status": status, 
            "progress": progress,
            "details": details
        }
        
        # Log the exact response being sent
        logger.info(f"[RETURN_PAYLOAD] Task {task_id_str}: {json.dumps(response_data)}")

        # Return UNTRANSLATED status for frontend logic
        return response_data
    except Exception as e:
        logger.error(f"General error fetching task status for task_id {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error fetching task status: {str(e)[:100]}")

# +++ New Endpoint to get latest active KB task +++
@router.get("/my_latest_kb_task", response_model=Optional[TaskStatusResponse], status_code=status.HTTP_200_OK)
async def get_my_latest_kb_task_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Gets the status of the most recently dispatched knowledge base task for the current user, if active."""
    try:
        task_id_result = db.query(UserDB.last_kb_task_id).filter(UserDB.email == current_user.email).first()
        
        if not task_id_result or not task_id_result[0]:
            return None

        task_id = str(task_id_result[0])
        logger.debug(f"Checking latest task {task_id} for user {current_user.email}")

        # Fetch full status using the other endpoint's logic to ensure consistency
        task_status_response = await get_task_status(task_id)

        # Check if the task is in a final state
        if task_status_response["status"] in ['SUCCESS', 'FAILURE', 'REVOKED']:
            logger.debug(f"Latest task {task_id} for user {current_user.email} is in final state: {task_status_response['status']}. Not returning.")
            return None # Task is finished, not active
        else:
            logger.debug(f"Latest task {task_id} for user {current_user.email} is active. Status: {task_status_response['status']}. Returning details.")
            # Task is active, return its current status
            return task_status_response
            
    except HTTPException as http_err:
        # If get_task_status raised an HTTP exception, log it but return None (task likely invalid)
        logger.error(f"HTTP error checking latest task {task_id if 'task_id' in locals() else 'N/A'} for user {current_user.email}: {http_err.detail}")
        return None
    except Exception as e:
        logger.error(f"Error in get_my_latest_kb_task_status for user {current_user.email}: {e}", exc_info=True)
        # Don't expose internal errors, just indicate no active task found
        return None
# --- End New Endpoint --- 