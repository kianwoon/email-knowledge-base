from datetime import datetime
from typing import Dict, Any, List, Optional

# In-memory storage for audit logs (replace with database in production)
audit_logs = []


async def log_action(
    action_type: str,
    user_id: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Log an action performed by a user
    
    Parameters:
    - action_type: Type of action (e.g., "login", "approve_email", "reject_email")
    - user_id: ID of the user performing the action
    - resource_id: Optional ID of the resource being acted upon
    - details: Optional additional details about the action
    """
    log_entry = {
        "id": f"log_{len(audit_logs) + 1}",
        "timestamp": datetime.now().isoformat(),
        "action_type": action_type,
        "user_id": user_id,
        "resource_id": resource_id,
        "details": details or {}
    }
    
    # Store log entry
    audit_logs.append(log_entry)
    
    return log_entry


async def get_logs(
    user_id: Optional[str] = None,
    action_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get audit logs with optional filtering
    """
    filtered_logs = audit_logs
    
    # Apply filters
    if user_id:
        filtered_logs = [log for log in filtered_logs if log["user_id"] == user_id]
    
    if action_type:
        filtered_logs = [log for log in filtered_logs if log["action_type"] == action_type]
    
    if resource_id:
        filtered_logs = [log for log in filtered_logs if log["resource_id"] == resource_id]
    
    if start_time:
        start_time_str = start_time.isoformat()
        filtered_logs = [log for log in filtered_logs if log["timestamp"] >= start_time_str]
    
    if end_time:
        end_time_str = end_time.isoformat()
        filtered_logs = [log for log in filtered_logs if log["timestamp"] <= end_time_str]
    
    # Sort by timestamp (newest first) and limit results
    sorted_logs = sorted(filtered_logs, key=lambda x: x["timestamp"], reverse=True)
    limited_logs = sorted_logs[:limit]
    
    return limited_logs
