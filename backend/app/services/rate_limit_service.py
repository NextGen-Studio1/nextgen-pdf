from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.models import DailyUsageRecord

PLAN_QUOTAS = {
    "guest": 5,
    "free": 10,
    "pro": 100,
    "business": 500
}

class RateLimitService:
    @staticmethod
    def check_and_increment_quota(db: Session, identifier: str, plan_tier: str = "guest", bytes_count: int = 0):
        """
        Thread & process-safe quota check & increment using pessimistic row locking (with_for_update)
        and unique constraint collision recovery against concurrent requests.
        """
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        limit = PLAN_QUOTAS.get(plan_tier.lower(), PLAN_QUOTAS["guest"])

        # Fetch existing record with row-level update lock
        record = db.query(DailyUsageRecord).filter(
            DailyUsageRecord.identifier == identifier,
            DailyUsageRecord.date_str == today_str
        ).with_for_update().first()

        if record:
            if record.operations_count >= limit:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Daily quota limit reached for your '{plan_tier}' plan ({limit} tasks/day). Upgrade your subscription for higher daily limits."
                )
            record.operations_count += 1
            record.bytes_processed += bytes_count
            db.commit()
        else:
            try:
                new_record = DailyUsageRecord(
                    identifier=identifier,
                    date_str=today_str,
                    operations_count=1,
                    bytes_processed=bytes_count
                )
                db.add(new_record)
                db.commit()
            except IntegrityError:
                # Concurrent request created the record first; rollback and lock/update
                db.rollback()
                record = db.query(DailyUsageRecord).filter(
                    DailyUsageRecord.identifier == identifier,
                    DailyUsageRecord.date_str == today_str
                ).with_for_update().first()

                if record:
                    if record.operations_count >= limit:
                        db.rollback()
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Daily quota limit reached for your '{plan_tier}' plan ({limit} tasks/day). Upgrade your subscription for higher daily limits."
                        )
                    record.operations_count += 1
                    record.bytes_processed += bytes_count
                    db.commit()
