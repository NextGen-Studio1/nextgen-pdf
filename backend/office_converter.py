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
    """Return the LibreOffice executable path if available, or None."""
    for candidate in ("libreoffice", "soffice"):
        path = shutil.which(candidate)
        if path:
            return path
    win_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for wp in win_paths:
        if os.path.exists(wp):
            return wp
    return None


def convert_docx_to_pdf_complete(docx_bytes: bytes) -> bytes:
    """
    High-fidelity Python DOCX -> PDF converter with Times-Roman Serif typography,
    run-level bold/italic parsing, header image extraction, bullet lists, and tables.
    """
    doc = docx.Document(io.BytesIO(docx_bytes))
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

    def extract_and_render_images(part):
        nonlocal page, y_cursor
        if not hasattr(part, "rels"):
            return
        for rel in part.rels.values():
            if "image" in rel.target_ref:
                try:
                    img_bytes = rel.target_part.blob
                    img = Image.open(io.BytesIO(img_bytes))
                    w, h = img.size
                    max_w = 260
                    if w > max_w:
                        scale = max_w / w
                        w, h = int(w * scale), int(h * scale)

                    check_page_break(h + 10)
                    page.insert_image(
                        fitz.Rect(margin_x, y_cursor, margin_x + w, y_cursor + h),
                        stream=img_bytes
                    )
                    y_cursor += h + 12
                    img.close()
                except Exception:
                    pass

    # A. Section Header & Logo Extraction
    for section in doc.sections:
        if section.header:
            extract_and_render_images(section.header.part)
            for hp in section.header.paragraphs:
                text = hp.text.strip()
                if text:
                    check_page_break(14)
                    page.insert_text(fitz.Point(margin_x, y_cursor), text, fontsize=9, fontname="times-roman", color=(0.2, 0.2, 0.2))
                    y_cursor += 12
            if section.header.paragraphs or hasattr(section.header.part, "rels"):
                y_cursor += 10
            break

    # B. Main Body Images
    extract_and_render_images(doc.part)

    # C. Main Body Paragraphs with Run-Level Styling (Times-Roman / Times-Bold)
    for p in doc.paragraphs:
        full_text = p.text.strip()
        if not full_text:
            y_cursor += 6
            continue

        style_name = (p.style.name or "").lower()
        align = str(p.alignment or "").lower()

        if "heading 1" in style_name or "title" in style_name:
            base_size = 15
            is_heading = True
            line_h = 22
        elif "heading 2" in style_name:
            base_size = 13
            is_heading = True
            line_h = 18
        else:
            base_size = 10.5
            is_heading = False
            line_h = 15

        prefix = "• " if ("list" in style_name or "bullet" in style_name) else ""

        runs_data = []
        if prefix:
            runs_data.append((prefix, True, False, base_size))

        if p.runs:
            for run in p.runs:
                if not run.text:
                    continue
                r_size = base_size
                if run.font and run.font.size:
                    r_size = run.font.size.pt
                is_b = is_heading or bool(run.bold)
                is_i = bool(run.italic)
                runs_data.append((run.text, is_b, is_i, r_size))
        else:
            runs_data.append((full_text, is_heading, False, base_size))

        styled_words = []
        for text_chunk, b_flag, i_flag, sz in runs_data:
            words = text_chunk.split()
            for w in words:
                styled_words.append((w, b_flag, i_flag, sz))

        if not styled_words:
            continue

        lines = []
        current_line = []
        current_w = 0.0

        for w_text, b_flag, i_flag, sz in styled_words:
            w_font = "times-bolditalic" if (b_flag and i_flag) else ("times-bold" if b_flag else ("times-italic" if i_flag else "times-roman"))
            w_width = len(w_text + " ") * (sz * 0.48)

            if current_w + w_width > content_w and current_line:
                lines.append(current_line)
                current_line = [(w_text, b_flag, i_flag, sz, w_font)]
                current_w = w_width
            else:
                current_line.append((w_text, b_flag, i_flag, sz, w_font))
                current_w += w_width

        if current_line:
            lines.append(current_line)

        for line in lines:
            check_page_break(line_h)
            
            line_est_w = sum(len(w_t + " ") * (sz * 0.48) for w_t, _, _, sz, _ in line)
            x_cursor = margin_x
            if "center" in align:
                x_cursor = margin_x + max(0, (content_w - line_est_w) / 2)
            elif "right" in align:
                x_cursor = margin_x + max(0, content_w - line_est_w)

            for w_t, b_flag, i_flag, sz, w_font in line:
                page.insert_text(
                    fitz.Point(x_cursor, y_cursor),
                    w_t + " ",
                    fontsize=sz,
                    fontname=w_font,
                    color=(0.1, 0.1, 0.1)
                )
                x_cursor += len(w_t + " ") * (sz * 0.48)

            y_cursor += line_h

        y_cursor += 3

    # D. Tables
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if not row_cells:
                continue
            row_str = "  |  ".join(row_cells)
            check_page_break(18)
            page.insert_text(
                fitz.Point(margin_x, y_cursor),
                row_str,
                fontsize=9.5,
                fontname="times-bold",
                color=(0.1, 0.1, 0.1)
            )
            y_cursor += 16
        y_cursor += 8

    # E. Section Footers
    for section in doc.sections:
        if section.footer:
            for fp in section.footer.paragraphs:
                text = fp.text.strip()
                if text:
                    check_page_break(14)
                    page.insert_text(fitz.Point(margin_x, y_cursor), text, fontsize=9, fontname="times-roman", color=(0.4, 0.4, 0.4))
                    y_cursor += 12
            break

    if pdf_doc.page_count == 0:
        p = pdf_doc.new_page(width=page_w, height=page_h)
        p.insert_text(fitz.Point(margin_x, margin_y), "Converted Document", fontsize=12, fontname="times-roman")

    buf = io.BytesIO()
    pdf_doc.save(buf, garbage=3, deflate=True)
    pdf_doc.close()
    return buf.getvalue()


def convert_xlsx_to_pdf_complete(xlsx_bytes: bytes) -> bytes:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    pdf_doc = fitz.open()
    page_w, page_h = 595, 842
    margin_x, margin_y = 54, 54
    page = pdf_doc.new_page(width=page_w, height=page_h)
    y_cursor = margin_y
    page.insert_text(fitz.Point(margin_x, y_cursor), "Spreadsheet Document", fontsize=14, fontname="times-bold")
    y_cursor += 24

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        page.insert_text(fitz.Point(margin_x, y_cursor), f"Sheet: {sheet_name}", fontsize=11, fontname="times-bold")
        y_cursor += 16
        for row in sheet.iter_rows(values_only=True):
            vals = [str(v) for v in row if v is not None]
            if not vals:
                continue
            row_str = " | ".join(vals[:6])
            if y_cursor > page_h - margin_y:
                page = pdf_doc.new_page(width=page_w, height=page_h)
                y_cursor = margin_y
            page.insert_text(fitz.Point(margin_x, y_cursor), row_str[:80], fontsize=9, fontname="times-roman")
            y_cursor += 14
        y_cursor += 10

    buf = io.BytesIO()
    pdf_doc.save(buf, garbage=3, deflate=True)
    pdf_doc.close()
    return buf.getvalue()


def convert_pptx_to_pdf_complete(pptx_bytes: bytes) -> bytes:
    from pptx import Presentation
    prs = Presentation(io.BytesIO(pptx_bytes))
    pdf_doc = fitz.open()
    page_w, page_h = 792, 612
    margin_x, margin_y = 54, 54

    for idx, slide in enumerate(prs.slides, 1):
        page = pdf_doc.new_page(width=page_w, height=page_h)
        y_cursor = margin_y
        page.insert_text(fitz.Point(margin_x, y_cursor), f"Slide {idx}", fontsize=14, fontname="times-bold")
        y_cursor += 24
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text.strip():
                for paragraph in shape.text_frame.paragraphs:
                    txt = paragraph.text.strip()
                    if txt:
                        if y_cursor > page_h - margin_y:
                            break
                        page.insert_text(fitz.Point(margin_x, y_cursor), txt[:100], fontsize=10, fontname="times-roman")
                        y_cursor += 16

    if pdf_doc.page_count == 0:
        p = pdf_doc.new_page(width=page_w, height=page_h)
        p.insert_text(fitz.Point(margin_x, margin_y), "Presentation Slide", fontsize=14, fontname="times-bold")

    buf = io.BytesIO()
    pdf_doc.save(buf, garbage=3, deflate=True)
    pdf_doc.close()
    return buf.getvalue()


def convert_office_to_pdf(data: bytes, original_filename: str) -> bytes:
    """
    Render an Office document to PDF with LibreOffice or high-fidelity Times-Roman fallback.
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
                pass  # Fall back to python docx renderer if LibreOffice fails

    # High-fidelity fallback parsers when LibreOffice is unavailable
    if suffix in {".docx", ".doc"}:
        try:
            return convert_docx_to_pdf_complete(data)
        except Exception as exc:
            raise RuntimeError(f"Could not convert Word document: {exc}") from exc
    elif suffix in {".xlsx", ".xls"}:
        try:
            return convert_xlsx_to_pdf_complete(data)
        except Exception as exc:
            raise RuntimeError(f"Could not convert Excel document: {exc}") from exc
    elif suffix in {".pptx", ".ppt"}:
        try:
            return convert_pptx_to_pdf_complete(data)
        except Exception as exc:
            raise RuntimeError(f"Could not convert PowerPoint document: {exc}") from exc

    raise RuntimeError("Office conversion is unavailable. Please check the backend converter installation.")

