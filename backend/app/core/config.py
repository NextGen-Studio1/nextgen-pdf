import os
from pathlib import Path

class Settings:
    PROJECT_NAME: str = "NextGen PDF API"
    VERSION: str = "3.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Base Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    TEMP_DIR: Path = BASE_DIR / "tmp_storage"
    UPLOAD_DIR: Path = TEMP_DIR / "uploads"
    RESULT_DIR: Path = TEMP_DIR / "results"
    
    # File Limits
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50 MB
    MAX_FILES: int = 20
    FILE_TTL_SECONDS: int = 3600  # 1 Hour auto cleanup
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/nextgen.db")
    
    # Firebase Credentials
    FIREBASE_PROJECT_ID: str | None = os.getenv("FIREBASE_PROJECT_ID")
    FIREBASE_CLIENT_EMAIL: str | None = os.getenv("FIREBASE_CLIENT_EMAIL")
    FIREBASE_PRIVATE_KEY: str | None = os.getenv("FIREBASE_PRIVATE_KEY")
    
    # CORS Origins
    FRONTEND_ORIGINS: list[str] = [
        "https://nextgen-pdf.web.app",
        "https://nextgen-pdf.firebaseapp.com",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

settings = Settings()

# Ensure storage directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.RESULT_DIR.mkdir(parents=True, exist_ok=True)
