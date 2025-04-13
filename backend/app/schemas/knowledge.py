from typing import Optional, datetime
from pydantic import BaseModel

class KnowledgeSummaryResponse(BaseModel):
    raw_data_count: Optional[int] = None
    sharepoint_raw_data_count: Optional[int] = None
    vector_data_count: Optional[int] = None
    last_updated: Optional[datetime] = None 