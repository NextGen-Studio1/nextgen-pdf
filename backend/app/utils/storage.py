import uuid
from pathlib import Path
from datetime import datetime, timedelta
from app.core.config import settings

def save_upload_buffer(content: bytes, filename: str) -> tuple[str, Path]:
    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}_{filename}"
    file_path = settings.UPLOAD_DIR / safe_name
    
    with open(file_path, "wb") as f:
        f.write(content)
        
    return file_id, file_path

def save_result_buffer(content: bytes, filename: str) -> tuple[str, Path]:
    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}_{filename}"
    file_path = settings.RESULT_DIR / safe_name
    
    with open(file_path, "wb") as f:
        f.write(content)
        
    return file_id, file_path

def get_file_path(file_id: str) -> Path | None:
    for folder in [settings.RESULT_DIR, settings.UPLOAD_DIR]:
        matches = list(folder.glob(f"{file_id}_*"))
        if matches:
            return matches[0]
    return None
