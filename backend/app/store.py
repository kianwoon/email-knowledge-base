# Simple in-memory storage for analysis results
# Note: This is temporary and will be lost if the server restarts.
# Consider using a database or cache for persistent storage in production.

from typing import Dict, Any

analysis_results_store: Dict[str, Any] = {} 