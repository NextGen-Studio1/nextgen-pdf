import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    plan_tier = Column(String, default="guest")  # guest, free, pro, business
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    files = relationship("FileRecord", back_populates="owner")
    jobs = relationship("JobRecord", back_populates="user")

class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, default="application/pdf")
    is_temp = Column(Boolean, default=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="files")

class JobRecord(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    tool_name = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    result_file_id = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="jobs")

class DailyUsageRecord(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint("identifier", "date_str", name="uix_identifier_date"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    identifier = Column(String, index=True, nullable=False)  # Firebase UID or Client IP
    date_str = Column(String, index=True, nullable=False)  # YYYY-MM-DD
    operations_count = Column(Integer, default=1)
    bytes_processed = Column(Integer, default=0)
