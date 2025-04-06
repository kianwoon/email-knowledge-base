from pydantic import BaseModel
from typing import List, Optional

class SubjectAnalysisResultItem(BaseModel):
    """Represents a single analyzed subject result."""
    tag: str
    cluster: str
    subject: str
    # Add confidence score if it's part of the webhook payload
    # confidence: Optional[float] = None 

class WebhookPayload(BaseModel):
    """Represents the full payload received by the webhook."""
    job_id: str
    # Make status optional as it might not always be sent (based on sample)
    status: Optional[str] = None 
    # Rename field to match sample payload ('results')
    results: Optional[List[SubjectAnalysisResultItem]] = None 
    # Add owner field (optional, in case external service doesn't return it)
    owner: Optional[str] = None 
    # Add error details if the API sends them on failure
    # error: Optional[str] = None 