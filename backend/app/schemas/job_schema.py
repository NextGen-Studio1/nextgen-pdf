from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class JobResponse(BaseModel):
    job_id: str
    tool_name: str
    status: str  # pending, processing, completed, failed
    progress: int
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
