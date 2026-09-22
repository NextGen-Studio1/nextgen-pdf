from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User
from app.core.firebase_auth import verify_firebase_token

security = HTTPBearer(auto_error=False)


def is_anonymous_claims(claims: dict | None) -> bool:
    """Check if claims dictionary represents a Firebase Anonymous user session."""
    if not claims:
        return True
    return claims.get("firebase", {}).get("sign_in_provider") == "anonymous"


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security)
    ]
) -> dict:
    """
    Strict authentication requirement. Expects: Authorization: Bearer <firebase-id-token>
    Raises 401 if token is missing or invalid.
    """
    if credentials is None or not credentials.credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_firebase_token(credentials.credentials)


def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security)
    ]
) -> dict | None:
    """
    Optional authentication guard:
    - Returns None if NO Authorization header is supplied (legitimate guest request).
    - If an Authorization header IS supplied, validates token and returns claims.
    - If an Authorization header IS supplied but invalid/expired, RAISES 401 (never downgrades invalid credentials to guest).
    """
    if credentials is None or not credentials.credentials:
        return None

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme. Expected Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Let verify_firebase_token raise HTTPException(401) directly if token is invalid/expired
    return verify_firebase_token(credentials.credentials)


def get_or_create_sql_user(db: Session, claims: dict) -> User:
    """
    Ensure a SQL User record exists matching the Firebase UID and verify active account status.
    If account is disabled (is_active=False), raises HTTP 403.
    """
    uid = claims["uid"]
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        is_anon = is_anonymous_claims(claims)
        user = User(
            id=uid,
            email=claims.get("email"),
            full_name=claims.get("name"),
            plan_tier="guest" if is_anon else "free",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is administratively disabled."
        )
    return user
