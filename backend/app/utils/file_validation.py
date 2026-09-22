import fitz
from fastapi import UploadFile
from app.core.config import settings
from app.core.exceptions import InvalidFileException, FileTooLargeException

# Magic byte signatures
MAGIC_BYTES = {
    "pdf": b"%PDF-",
    "jpg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
    "zip": b"PK\x03\x04"  # Also used for docx, xlsx, pptx
}

MAX_PAGE_COUNT = 500  # Hard limit on PDF pages per operation to prevent resource exhaustion

async def read_file_bounded(file: UploadFile, max_bytes: int = settings.MAX_FILE_SIZE, chunk_size: int = 1024 * 1024) -> bytes:
    """
    Read upload file stream in 1MB chunks. Aborts immediately if stream exceeds max_bytes,
    preventing RAM exhaustion from large uploaded payloads.
    """
    chunks = []
    total_size = 0
    while chunk := await file.read(chunk_size):
        total_size += len(chunk)
        if total_size > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise FileTooLargeException(f"File size exceeds the {max_mb} MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)

def validate_file_size(content: bytes):
    if len(content) > settings.MAX_FILE_SIZE:
        max_mb = settings.MAX_FILE_SIZE // (1024 * 1024)
        raise FileTooLargeException(f"File size exceeds the {max_mb} MB limit.")

def validate_pdf_magic_bytes(content: bytes) -> bool:
    if not content.startswith(MAGIC_BYTES["pdf"]):
        raise InvalidFileException("Uploaded file is not a valid PDF document (magic bytes header mismatch).")
    return True

def validate_pdf_structure(content: bytes, max_pages: int = MAX_PAGE_COUNT) -> bool:
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        if doc.page_count < 1:
            doc.close()
            raise InvalidFileException("PDF file contains no readable pages.")
        if doc.page_count > max_pages:
            pages_num = doc.page_count
            doc.close()
            raise InvalidFileException(f"PDF exceeds the maximum page limit of {max_pages} pages (file contains {pages_num} pages).")
        doc.close()
        return True
    except InvalidFileException:
        raise
    except Exception as e:
        raise InvalidFileException(f"Corrupted PDF document: {str(e)}")

def validate_image_magic_bytes(content: bytes) -> bool:
    is_valid = any(content.startswith(header) for header in [MAGIC_BYTES["jpg"], MAGIC_BYTES["png"]])
    if not is_valid:
        raise InvalidFileException("Uploaded file is not a supported image format (JPG or PNG required).")
    return True
