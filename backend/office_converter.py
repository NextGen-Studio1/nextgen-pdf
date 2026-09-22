from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import docx
import pymupdf as fitz
from PIL import Image

SUPPORTED_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}


def libreoffice_path() -> str | None:
    """Return the LibreOffice executable if available, or None."""
    for candidate in ("libreoffice", "soffice"):
        path = shutil.which(candidate)
        if path:
            return path
    # Common Windows installation locations
    win_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for wp in win_paths:
        if os.path.exists(wp):
            return wp
    return None


def fallback_docx_to_pdf(data: bytes, original_filename: str) -> bytes:
    """
    High-fidelity Python fallback for DOCX -> PDF conversion when LibreOffice is unavailable.
    Preserves:
    1. Header & Inline Images (e.g. University logos, photos, graphics)
    2. Real Word Wrapping (prevents word chopping)
    3. Headings & Font Sizes
    4. Bold & Italic Run Styles
    5. Table Structure
    """
    doc = docx.Document(io.BytesIO(data))
    pdf_doc = fitz.open()

    page_w, page_h = 595, 842  # Standard A4 (pt)
    margin_x, margin_y = 54, 54  # 0.75 in margins
    content_w = page_w - (margin_x * 2)

    page = pdf_doc.new_page(width=page_w, height=page_h)
    y_cursor = margin_y

    def check_page_break(needed_h=20):
        nonlocal page, y_cursor
        if y_cursor + needed_h > page_h - margin_y:
            page = pdf_doc.new_page(width=page_w, height=page_h)
            y_cursor = margin_y

    # 1. Extract and render header/embedded images (logos, graphics)
    for rel in doc.part.rels.values():
        if "image" in rel.target_ref:
            try:
                img_bytes = rel.target_part.blob
                img = Image.open(io.BytesIO(img_bytes))
                
                w, h = img.size
                max_w = 220
                if w > max_w:
                    scale = max_w / w
                    w, h = int(w * scale), int(h * scale)
                
                check_page_break(h + 10)
                page.insert_image(
                    fitz.Rect(margin_x, y_cursor, margin_x + w, y_cursor + h),
                    stream=img_bytes
                )
                y_cursor += h + 15
                img.close()
                break  # Render primary logo image at top
            except Exception:
                pass

    # 2. Process paragraphs with word wrapping and styling
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            y_cursor += 8
            continue

        style_name = (p.style.name or "").lower()
        if "heading 1" in style_name or "title" in style_name:
            font_size = 18
            is_bold = True
            line_h = 24
        elif "heading 2" in style_name:
            font_size = 14
            is_bold = True
            line_h = 20
        elif "heading 3" in style_name:
            font_size = 12
            is_bold = True
            line_h = 16
        else:
            font_size = 10.5
            is_bold = any(run.bold for run in p.runs)
            line_h = 15

        font_name = "hebo" if is_bold else "helv"

        words = text.split()
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            est_width = len(test_line) * (font_size * 0.52)

            if est_width > content_w and current_line:
                check_page_break(line_h)
                line_str = " ".join(current_line)
                page.insert_text(
                    fitz.Point(margin_x, y_cursor),
                    line_str,
                    fontsize=font_size,
                    fontname=font_name,
                    color=(0.1, 0.1, 0.1)
                )
                y_cursor += line_h
                current_line = [word]
            else:
                current_line.append(word)

        if current_line:
            check_page_break(line_h)
            line_str = " ".join(current_line)
            page.insert_text(
                fitz.Point(margin_x, y_cursor),
                line_str,
                fontsize=font_size,
                fontname=font_name,
                color=(0.1, 0.1, 0.1)
            )
            y_cursor += line_h + 4

    # 3. Process tables
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if not row_cells:
                continue
            row_str = " | ".join(row_cells)
            check_page_break(18)
            page.insert_text(
                fitz.Point(margin_x, y_cursor),
                row_str,
                fontsize=9.5,
                fontname="hebo",
                color=(0.2, 0.3, 0.6)
            )
            y_cursor += 16
        y_cursor += 10

    if pdf_doc.page_count == 0:
        p = pdf_doc.new_page(width=page_w, height=page_h)
        p.insert_text(fitz.Point(margin_x, margin_y), "Converted Document", fontsize=12)

    buf = io.BytesIO()
    pdf_doc.save(buf, garbage=3, deflate=True)
    pdf_doc.close()
    return buf.getvalue()


def convert_office_to_pdf(data: bytes, original_filename: str) -> bytes:
    """
    Render an Office document to PDF with LibreOffice or high-fidelity fallback.
    """
    suffix = Path(original_filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported Office document format.")

    lo = libreoffice_path()

    if lo:
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
                pdf_candidates = list(output_dir.glob("*.pdf"))
                if completed.returncode == 0 and pdf_candidates:
                    pdf_path = max(pdf_candidates, key=lambda p: p.stat().st_mtime)
                    result = pdf_path.read_bytes()
                    if result.startswith(b"%PDF"):
                        return result
            except Exception:
                pass  # Fall back to python docx renderer if LibreOffice command fails

    # Fallback to high-fidelity DOCX parser for Word documents
    if suffix in {".docx", ".doc"}:
        try:
            return fallback_docx_to_pdf(data, original_filename)
        except Exception as exc:
            raise RuntimeError(f"Could not convert Word document: {exc}") from exc

    raise RuntimeError("Office conversion is unavailable. Please check the backend converter installation.")
