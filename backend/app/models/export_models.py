from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import enum

class ExportDataSource(str, enum.Enum):
    ICEBERG_EMAIL_FACTS = "iceberg_email_facts"
    # Add other sources later, e.g., SHAREPOINT_FILES, S3_OBJECTS

class ExportFormat(str, enum.Enum):
    CSV = "csv"
    JSON = "json"
    # Add other formats later

class ExportRequest(BaseModel):
    source: ExportDataSource = Field(..., description="The data source to export from.")
    format: ExportFormat = Field(ExportFormat.CSV, description="The desired output format.")
    # Token whose rules govern this export. If omitted, the API authentication token's rules are used.
    token_id: Optional[int] = Field(None, description="ID of the token whose rules apply to this export. Defaults to the authentication token.")
    # Source-specific filters
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Source-specific filters (e.g., keywords, date range for emails).")
    # Example for iceberg_email_facts: {"keywords": ["urgent"], "start_date": "2024-01-01", "end_date": "2024-03-31"}

class ExportJobResponse(BaseModel):
    job_id: int = Field(..., description="The unique ID of the created export job.")
    task_id: Optional[str] = Field(None, description="The Celery task ID handling the background export process.")
    status: str = Field(..., description="The initial status of the job (e.g., pending).")

    model_config = {
        "from_attributes": True # Allow creating from ORM model
    } 