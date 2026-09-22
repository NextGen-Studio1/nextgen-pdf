import os
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db
from app.db.models import User, FileRecord, JobRecord, DailyUsageRecord
from app.core.config import settings

try:
    from conftest import TestingSessionLocal
except ImportError:
    from backend.tests.conftest import TestingSessionLocal

client = TestClient(app)

def mock_verify_firebase_token(token: str) -> dict:
    if token == "token_user_a":
        return {
            "uid": "user_a_uid",
            "email": "usera@example.com",
            "name": "User A",
            "firebase": {"sign_in_provider": "password"}
        }
    elif token == "token_user_b":
        return {
            "uid": "user_b_uid",
            "email": "userb@example.com",
            "name": "User B",
            "firebase": {"sign_in_provider": "password"}
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase ID token."
        )

@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSessionLocal()
    try:
        db.query(FileRecord).delete()
        db.query(JobRecord).delete()
        db.query(DailyUsageRecord).delete()
        db.query(User).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield

@patch("app.core.dependencies.verify_firebase_token", side_effect=mock_verify_firebase_token)
def test_missing_token_returns_401(mock_auth):
    endpoints = [
        "/api/v1/dashboard/overview",
        "/api/v1/dashboard/files",
        "/api/v1/dashboard/history",
        "/api/v1/dashboard/usage",
    ]
    for ep in endpoints:
        response = client.get(ep)
        assert response.status_code == 401, f"Expected 401 for {ep} without token, got {response.status_code}"

    del_response = client.delete("/api/v1/dashboard/files/test-file-id")
    assert del_response.status_code == 401

@patch("app.core.dependencies.verify_firebase_token", side_effect=mock_verify_firebase_token)
def test_invalid_token_returns_401(mock_auth):
    headers = {"Authorization": "Bearer invalid_garbage_token"}
    endpoints = [
        "/api/v1/dashboard/overview",
        "/api/v1/dashboard/files",
        "/api/v1/dashboard/history",
        "/api/v1/dashboard/usage",
    ]
    for ep in endpoints:
        response = client.get(ep, headers=headers)
        assert response.status_code == 401, f"Expected 401 for {ep} with invalid token, got {response.status_code}"

@patch("app.core.dependencies.verify_firebase_token", side_effect=mock_verify_firebase_token)
def test_authenticated_user_access_own_dashboard(mock_auth):
    headers_a = {"Authorization": "Bearer token_user_a"}
    
    # 1. Overview
    res_ov = client.get("/api/v1/dashboard/overview", headers=headers_a)
    assert res_ov.status_code == 200
    data_ov = res_ov.json()
    assert data_ov["plan"] == "free"
    assert data_ov["daily_limit"] == 10
    assert data_ov["usage_today"] == 0

    # 2. Files
    res_files = client.get("/api/v1/dashboard/files", headers=headers_a)
    assert res_files.status_code == 200
    assert res_files.json()["total"] == 0

    # 3. History
    res_hist = client.get("/api/v1/dashboard/history", headers=headers_a)
    assert res_hist.status_code == 200
    assert res_hist.json()["total"] == 0

    # 4. Usage
    res_usage = client.get("/api/v1/dashboard/usage", headers=headers_a)
    assert res_usage.status_code == 200
    assert res_usage.json()["plan"] == "free"

@patch("app.core.dependencies.verify_firebase_token", side_effect=mock_verify_firebase_token)
def test_user_cannot_see_another_users_files(mock_auth):
    db = TestingSessionLocal()
    # Create FileRecord for User A
    file_a = FileRecord(
        id="file_user_a_001",
        filename="usera_document.pdf",
        file_path=str(settings.RESULT_DIR / "file_user_a_001_usera_document.pdf"),
        file_size=5000,
        mime_type="application/pdf",
        is_temp=True,
        owner_id="user_a_uid",
        created_at=datetime.utcnow()
    )
    db.add(file_a)
    db.commit()
    db.close()

    headers_a = {"Authorization": "Bearer token_user_a"}
    headers_b = {"Authorization": "Bearer token_user_b"}

    # User A sees 1 file
    res_a = client.get("/api/v1/dashboard/files", headers=headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["total"] == 1
    assert res_a.json()["files"][0]["id"] == "file_user_a_001"

    # User B sees 0 files
    res_b = client.get("/api/v1/dashboard/files", headers=headers_b)
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 0
    assert len(res_b.json()["files"]) == 0

@patch("app.core.dependencies.verify_firebase_token", side_effect=mock_verify_firebase_token)
def test_user_cannot_see_another_users_jobs(mock_auth):
    db = TestingSessionLocal()
    # Create JobRecord for User A
    job_a = JobRecord(
        id="job_user_a_001",
        tool_name="compress",
        status="completed",
        progress=100,
        user_id="user_a_uid",
        result_file_id="file_user_a_001",
        created_at=datetime.utcnow()
    )
    db.add(job_a)
    db.commit()
    db.close()

    headers_a = {"Authorization": "Bearer token_user_a"}
    headers_b = {"Authorization": "Bearer token_user_b"}

    # User A sees 1 job
    res_a = client.get("/api/v1/dashboard/history", headers=headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["total"] == 1

    # User B sees 0 jobs
    res_b = client.get("/api/v1/dashboard/history", headers=headers_b)
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 0

@patch("app.core.dependencies.verify_firebase_token", side_effect=mock_verify_firebase_token)
@patch("app.core.dependencies.get_optional_user", side_effect=lambda credentials=None: mock_verify_firebase_token(credentials.credentials) if credentials else None)
def test_user_cannot_download_another_users_file(mock_optional_auth, mock_auth):
    db = TestingSessionLocal()
    # Create dummy physical file matching storage glob format (file_id_filename)
    test_path = settings.RESULT_DIR / "file_user_a_secret_secret.pdf"
    with open(test_path, "wb") as f:
        f.write(b"%PDF-1.4 dummy content for test")

    file_a = FileRecord(
        id="file_user_a_secret",
        filename="secret.pdf",
        file_path=str(test_path),
        file_size=30,
        mime_type="application/pdf",
        is_temp=True,
        owner_id="user_a_uid",
        created_at=datetime.utcnow()
    )
    db.add(file_a)
    db.commit()
    db.close()

    try:
        headers_b = {"Authorization": "Bearer token_user_b"}
        # User B trying to download User A's file -> 403 Forbidden
        res_b = client.get("/api/v1/files/file_user_a_secret", headers=headers_b)
        assert res_b.status_code == 403, f"Expected 403 for unauthorized download, got {res_b.status_code}"

        # User A downloading own file -> 200 OK
        headers_a = {"Authorization": "Bearer token_user_a"}
        res_a = client.get("/api/v1/files/file_user_a_secret", headers=headers_a)
        assert res_a.status_code == 200
        assert res_a.content == b"%PDF-1.4 dummy content for test"
    finally:
        if test_path.exists():
            test_path.unlink()

@patch("app.core.dependencies.verify_firebase_token", side_effect=mock_verify_firebase_token)
def test_user_cannot_delete_another_users_file(mock_auth):
    db = TestingSessionLocal()
    # Create physical file & record for User A
    test_path = settings.RESULT_DIR / "file_user_a_del_usera_del.pdf"
    with open(test_path, "wb") as f:
        f.write(b"dummy content")

    file_a = FileRecord(
        id="file_user_a_del",
        filename="usera_del.pdf",
        file_path=str(test_path),
        file_size=13,
        mime_type="application/pdf",
        is_temp=True,
        owner_id="user_a_uid",
        created_at=datetime.utcnow()
    )
    db.add(file_a)
    db.commit()
    db.close()

    try:
        headers_b = {"Authorization": "Bearer token_user_b"}
        # User B trying to delete User A's file -> 403 Forbidden
        res_b = client.delete("/api/v1/dashboard/files/file_user_a_del", headers=headers_b)
        assert res_b.status_code == 403, f"Expected 403 when User B deletes User A's file, got {res_b.status_code}"

        # User A deleting own file -> 200 OK
        headers_a = {"Authorization": "Bearer token_user_a"}
        res_a = client.delete("/api/v1/dashboard/files/file_user_a_del", headers=headers_a)
        assert res_a.status_code == 200
        assert res_a.json()["file_id"] == "file_user_a_del"
    finally:
        if test_path.exists():
            test_path.unlink()

