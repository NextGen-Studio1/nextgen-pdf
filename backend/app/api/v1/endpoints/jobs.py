from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import JobRecord, FileRecord
from app.services.job_service import JobService
from app.utils.storage import get_file_path
from app.schemas.job_schema import JobResponse
from app.core.dependencies import get_optional_user

router = APIRouter()

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    # Enforce job ownership if job has an associated user_id
    if job.user_id:
        if not current_user or current_user.get("uid") != job.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view this job status."
            )

    result_url = f"/api/v1/files/{job.result_file_id}" if job.result_file_id else None

    return JobResponse(
        job_id=job.id,
        tool_name=job.tool_name,
        status=job.status,
        progress=job.progress,
        result_url=result_url,
        error_message=job.error_message,
        created_at=job.created_at
    )

@router.get("/files/{file_id}")
def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    # Check FileRecord ownership first
    file_rec = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    owner_id = file_rec.owner_id if file_rec else None

    # Fallback to JobRecord if FileRecord doesn't specify owner
    if not owner_id:
        job = db.query(JobRecord).filter(JobRecord.result_file_id == file_id).first()
        if job:
            owner_id = job.user_id

    if owner_id:
        if not current_user or current_user.get("uid") != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to download this file."
            )

    file_path = get_file_path(file_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File expired or not found.")

    original_name = file_rec.filename if (file_rec and file_rec.filename) else (file_path.name.split("_", 1)[-1] if "_" in file_path.name else file_path.name)
    headers = {"Content-Disposition": f'attachment; filename="{original_name}"'}
    return FileResponse(file_path, headers=headers)
