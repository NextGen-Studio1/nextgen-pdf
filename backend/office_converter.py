from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


SUPPORTED_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}


def libreoffice_path() -> str:
    """Return the LibreOffice executable or raise a clear runtime error."""
    for candidate in ("libreoffice", "soffice"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError(
        "Office conversion is unavailable because LibreOffice is not installed on the PDF conversion server."
    )


def convert_office_to_pdf(data: bytes, original_filename: str) -> bytes:
    """
    Render an Office document to PDF with LibreOffice.

    Unlike text extraction/reconstruction, LibreOffice opens the real document
    and renders its layout. This preserves document-level formatting such as
    images, fonts, paragraph alignment, tables, margins, headers/footers,
    page breaks, and spacing much more faithfully.
    """
    suffix = Path(original_filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported Office document format.")

    lo = libreoffice_path()

    with tempfile.TemporaryDirectory(prefix="nextgen-office-") as tmp:
        root = Path(tmp)
        source_dir = root / "source"
        output_dir = root / "output"
        profile_dir = root / "profile"
        source_dir.mkdir()
        output_dir.mkdir()
        profile_dir.mkdir()

        source = source_dir / Path(original_filename or "document").name
        source.write_bytes(data)

        # A unique user profile avoids profile-lock collisions between
        # concurrent requests.
        profile_uri = profile_dir.as_uri()

        cmd = [
            lo,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--norestore",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(source),
        ]

        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Office conversion timed out after 120 seconds.") from exc

        pdf_candidates = list(output_dir.glob("*.pdf"))
        if completed.returncode != 0 or not pdf_candidates:
            detail = (completed.stderr or completed.stdout or "").strip()
            if len(detail) > 500:
                detail = detail[-500:]
            raise RuntimeError(
                "LibreOffice could not render this document to PDF."
                + (f" Details: {detail}" if detail else "")
            )

        # There should normally be exactly one PDF. Use the newest result if
        # LibreOffice produced more than one for an unusual document.
        pdf_path = max(pdf_candidates, key=lambda p: p.stat().st_mtime)
        result = pdf_path.read_bytes()
        if not result.startswith(b"%PDF"):
            raise RuntimeError("The Office conversion produced an invalid PDF.")

        return result
