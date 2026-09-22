from datetime import datetime
from fastapi import Request, status
from fastapi.responses import JSONResponse

class NextGenException(Exception):
    def __init__(self, code: str, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.detail = detail
        self.status_code = status_code

class InvalidFileException(NextGenException):
    def __init__(self, detail: str = "Invalid file structure or magic bytes check failed."):
        super().__init__(code="INVALID_FILE", detail=detail, status_code=status.HTTP_400_BAD_REQUEST)

class FileTooLargeException(NextGenException):
    def __init__(self, detail: str = "File size exceeds the allowable limit."):
        super().__init__(code="FILE_TOO_LARGE", detail=detail, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

class ProcessingFailedException(NextGenException):
    def __init__(self, detail: str = "PDF processing operation failed."):
        super().__init__(code="PROCESSING_FAILED", detail=detail, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PasswordRequiredException(NextGenException):
    def __init__(self, detail: str = "Password required to unlock document."):
        super().__init__(code="PASSWORD_REQUIRED", detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)

async def nextgen_exception_handler(request: Request, exc: NextGenException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.code,
            "detail": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path
        }
    )
