from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class FileItem(BaseModel):
    id: str
    filename: str
    size: int
    mime_type: str
    created_at: datetime
    download_url: str

    class Config:
        from_attributes = True

class FileListResponse(BaseModel):
    files: List[FileItem]
    total: int
    page: int = 1
    limit: int = 20

class JobHistoryItem(BaseModel):
    job_id: str
    tool_name: str
    status: str
    progress: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    result_file_id: Optional[str] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class HistoryListResponse(BaseModel):
    history: List[JobHistoryItem]
    total: int
    page: int = 1
    limit: int = 20

class DashboardOverviewResponse(BaseModel):
    plan: str
    usage_today: int
    daily_limit: int
    remaining_today: int
    files_processed: int
    successful_jobs: int
    failed_jobs: int
    total_bytes_processed: int
    recent_jobs: List[JobHistoryItem]

class DashboardUsageResponse(BaseModel):
    plan: str
    today_operations: int
    daily_limit: int
    remaining_today: int
    bytes_processed_today: int
    successful_jobs: int
    failed_jobs: int
    total_operations_all_time: int
    total_bytes_all_time: int

class FileDeleteResponse(BaseModel):
    message: str
    file_id: str

