from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, JobRecord, FileRecord, DailyUsageRecord
from app.core.dependencies import get_current_user, get_or_create_sql_user
from app.services.rate_limit_service import PLAN_QUOTAS
from app.utils.storage import get_file_path
from app.schemas.dashboard_schema import (
    DashboardOverviewResponse,
    FileListResponse,
    FileItem,
    HistoryListResponse,
    JobHistoryItem,
    DashboardUsageResponse,
    FileDeleteResponse,
)

router = APIRouter()

@router.get("/overview", response_model=DashboardOverviewResponse)
def get_overview(
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user)
):
    user = get_or_create_sql_user(db, claims)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    plan_name = (user.plan_tier or "free").lower()
    daily_limit = PLAN_QUOTAS.get(plan_name, PLAN_QUOTAS["free"])

    daily_rec = db.query(DailyUsageRecord).filter(
        DailyUsageRecord.identifier == user.id,
        DailyUsageRecord.date_str == today_str
    ).first()

    usage_today = daily_rec.operations_count if daily_rec else 0
    remaining_today = max(0, daily_limit - usage_today)

    jobs_query = db.query(JobRecord).filter(JobRecord.user_id == user.id)
    files_processed = jobs_query.count()
    successful_jobs = jobs_query.filter(JobRecord.status == "completed").count()
    failed_jobs = jobs_query.filter(JobRecord.status == "failed").count()

    all_usage = db.query(DailyUsageRecord).filter(DailyUsageRecord.identifier == user.id).all()
    total_bytes_processed = sum(u.bytes_processed for u in all_usage)

    recent_job_records = jobs_query.order_by(JobRecord.created_at.desc()).limit(5).all()
    recent_jobs = [
        JobHistoryItem(
            job_id=j.id,
            tool_name=j.tool_name,
            status=j.status,
            progress=j.progress,
            created_at=j.created_at,
            updated_at=j.updated_at or j.created_at,
            result_file_id=j.result_file_id,
            download_url=f"/api/v1/files/{j.result_file_id}" if j.result_file_id else None,
            error_message=j.error_message if j.status == "failed" else None
        )
        for j in recent_job_records
    ]

    return DashboardOverviewResponse(
        plan=plan_name,
        usage_today=usage_today,
        daily_limit=daily_limit,
        remaining_today=remaining_today,
        files_processed=files_processed,
        successful_jobs=successful_jobs,
        failed_jobs=failed_jobs,
        total_bytes_processed=total_bytes_processed,
        recent_jobs=recent_jobs
    )

@router.get("/files", response_model=FileListResponse)
def get_user_files(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user)
):
    user = get_or_create_sql_user(db, claims)
    query = db.query(FileRecord).filter(FileRecord.owner_id == user.id)
    total = query.count()

    files = query.order_by(FileRecord.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    file_items = [
        FileItem(
            id=f.id,
            filename=f.filename,
            size=f.file_size,
            mime_type=f.mime_type or "application/pdf",
            created_at=f.created_at,
            download_url=f"/api/v1/files/{f.id}"
        )
        for f in files
    ]

    return FileListResponse(
        files=file_items,
        total=total,
        page=page,
        limit=limit
    )

@router.get("/history", response_model=HistoryListResponse)
def get_user_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user)
):
    user = get_or_create_sql_user(db, claims)
    query = db.query(JobRecord).filter(JobRecord.user_id == user.id)
    total = query.count()

    jobs = query.order_by(JobRecord.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    history_items = [
        JobHistoryItem(
            job_id=j.id,
            tool_name=j.tool_name,
            status=j.status,
            progress=j.progress,
            created_at=j.created_at,
            updated_at=j.updated_at or j.created_at,
            result_file_id=j.result_file_id,
            download_url=f"/api/v1/files/{j.result_file_id}" if j.result_file_id else None,
            error_message=j.error_message if j.status == "failed" else None
        )
        for j in jobs
    ]

    return HistoryListResponse(
        history=history_items,
        total=total,
        page=page,
        limit=limit
    )

@router.get("/usage", response_model=DashboardUsageResponse)
def get_user_usage(
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user)
):
    user = get_or_create_sql_user(db, claims)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    plan_name = (user.plan_tier or "free").lower()
    daily_limit = PLAN_QUOTAS.get(plan_name, PLAN_QUOTAS["free"])

    daily_rec = db.query(DailyUsageRecord).filter(
        DailyUsageRecord.identifier == user.id,
        DailyUsageRecord.date_str == today_str
    ).first()

    today_ops = daily_rec.operations_count if daily_rec else 0
    today_bytes = daily_rec.bytes_processed if daily_rec else 0
    remaining_today = max(0, daily_limit - today_ops)

    all_usage = db.query(DailyUsageRecord).filter(DailyUsageRecord.identifier == user.id).all()
    total_ops_all_time = sum(u.operations_count for u in all_usage)
    total_bytes_all_time = sum(u.bytes_processed for u in all_usage)

    jobs_query = db.query(JobRecord).filter(JobRecord.user_id == user.id)
    successful_jobs = jobs_query.filter(JobRecord.status == "completed").count()
    failed_jobs = jobs_query.filter(JobRecord.status == "failed").count()

    return DashboardUsageResponse(
        plan=plan_name,
        today_operations=today_ops,
        daily_limit=daily_limit,
        remaining_today=remaining_today,
        bytes_processed_today=today_bytes,
        successful_jobs=successful_jobs,
        failed_jobs=failed_jobs,
        total_operations_all_time=total_ops_all_time,
        total_bytes_all_time=total_bytes_all_time
    )

@router.delete("/files/{file_id}", response_model=FileDeleteResponse)
def delete_user_file(
    file_id: str,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_user)
):
    user = get_or_create_sql_user(db, claims)
    file_rec = db.query(FileRecord).filter(FileRecord.id == file_id).first()

    if not file_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File record not found."
        )

    if file_rec.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this file."
        )

    file_path = get_file_path(file_id)
    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            pass

    db.delete(file_rec)
    db.commit()

    return FileDeleteResponse(
        message="File deleted successfully.",
        file_id=file_id
    )

