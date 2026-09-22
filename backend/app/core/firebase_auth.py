import firebase_admin
from firebase_admin import credentials, auth, exceptions as firebase_exceptions
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.logging import logger


def initialize_firebase():
    """Initialize Firebase Admin SDK once."""
    if firebase_admin._apps:
        return firebase_admin.get_app()

    if not all([
        settings.FIREBASE_PROJECT_ID,
        settings.FIREBASE_CLIENT_EMAIL,
        settings.FIREBASE_PRIVATE_KEY,
    ]):
        raise RuntimeError(
            "Firebase Admin credentials are not configured in environment settings."
        )

    private_key = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")

    credential = credentials.Certificate({
        "type": "service_account",
        "project_id": settings.FIREBASE_PROJECT_ID,
        "private_key": private_key,
        "client_email": settings.FIREBASE_CLIENT_EMAIL,
        "token_uri": "https://oauth2.googleapis.com/token",
    })

    return firebase_admin.initialize_app(credential)


def verify_firebase_token(id_token: str) -> dict:
    """
    Verify a Firebase ID token and return its decoded claims.
    Distinguishes server initialization errors (500) from invalid credentials (401).
    """
    try:
        initialize_firebase()
    except RuntimeError as config_err:
        logger.error(f"[Firebase Admin Config Error]: {config_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service is currently unconfigured."
        )
    except Exception as init_err:
        logger.error(f"[Firebase Admin Init Failure]: {init_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service initialization error."
        )

    try:
        return auth.verify_id_token(id_token)
    except (ValueError, firebase_exceptions.FirebaseError) as token_err:
        logger.warning(f"[Firebase Auth] Token verification rejected: {token_err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as general_err:
        logger.error(f"[Firebase Auth] Unexpected verification error: {general_err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
