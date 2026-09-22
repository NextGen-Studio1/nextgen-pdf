from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.config import settings

router = APIRouter()

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "connected",
        "storage": {
            "max_file_size_mb": settings.MAX_FILE_SIZE // (1024 * 1024),
            "file_ttl_hours": settings.FILE_TTL_SECONDS // 3600
        }
    }
