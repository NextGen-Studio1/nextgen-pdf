import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models import JobRecord, FileRecord
from app.utils.storage import get_file_path
from app.schemas.job_schema import JobResponse

class JobService:
    @staticmethod
    def create_job(db: Session, tool_name: str, user_id: str = None) -> JobRecord:
        job = JobRecord(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            status="processing",
            progress=10,
            user_id=user_id,
            created_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def update_progress(db: Session, job_id: str, progress: int, status: str = "processing"):
        job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if job:
            job.progress = progress
            job.status = status
            db.commit()

    @staticmethod
    def complete_job(db: Session, job_id: str, result_file_id: str, filename: str = "result.pdf", file_size: int = 0):
        job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if job:
            job.status = "completed"
            job.progress = 100
            job.result_file_id = result_file_id

            # Create FileRecord for owner tracking
            existing_file = db.query(FileRecord).filter(FileRecord.id == result_file_id).first()
            if not existing_file:
                file_path = get_file_path(result_file_id)
                path_str = str(file_path) if file_path else ""
                size = file_size or (file_path.stat().st_size if file_path and file_path.exists() else 0)

                file_rec = FileRecord(
                    id=result_file_id,
                    filename=filename,
                    file_path=path_str,
                    file_size=size,
                    mime_type="application/pdf",
                    is_temp=True,
                    owner_id=job.user_id,
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(seconds=settings.FILE_TTL_SECONDS)
                )
                db.add(file_rec)

            db.commit()

    @staticmethod
    def fail_job(db: Session, job_id: str, error_message: str):
        job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = error_message
            db.commit()

    @staticmethod
    def get_job(db: Session, job_id: str) -> JobRecord | None:
        return db.query(JobRecord).filter(JobRecord.id == job_id).first()
