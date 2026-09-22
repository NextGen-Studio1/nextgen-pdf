import time
import asyncio
from datetime import datetime, timedelta
from app.core.config import settings
from app.core.logging import logger

class CleanupService:
    @staticmethod
    def cleanup_old_files():
        now = time.time()
        cutoff = now - settings.FILE_TTL_SECONDS  # 1 hour ago
        purged_count = 0

        for folder in [settings.UPLOAD_DIR, settings.RESULT_DIR]:
            if not folder.exists():
                continue
            for file_path in folder.iterdir():
                if file_path.is_file():
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < cutoff:
                        try:
                            file_path.unlink()
                            purged_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete {file_path}: {e}")

        if purged_count > 0:
            logger.info(f"CleanupService purged {purged_count} temporary files older than {settings.FILE_TTL_SECONDS // 3600}h.")

    @classmethod
    async def start_periodic_cleanup(cls, interval_seconds: int = 1800):
        while True:
            try:
                cls.cleanup_old_files()
            except Exception as e:
                logger.error(f"Error during periodic cleanup: {e}")
            await asyncio.sleep(interval_seconds)
