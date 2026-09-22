import io
import docx
import pymupdf as fitz
from PIL import Image

def convert_docx_to_pdf_serif_runs(docx_bytes: bytes) -> bytes:
    """
    High-fidelity Python DOCX -> PDF converter.
    Parses run-level formatting:
    - Uses Times-Roman ("time") and Times-Bold ("tiro") for Word serif typography
    - Renders bold runs (e.g. **Breadth First Search (BFS)**) in bold Times
    - Renders header logos and section headers with proper margins
    - Renders tables, bullets, and line spacing
    """
    doc = docx.Document(io.BytesIO(docx_bytes))
    pdf_doc = fitz.open()

    page_w, page_h = 595, 842  # A4 pt
    margin_x, margin_y = 54, 54
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

    # A. Section Header & Logo
    for section in doc.sections:
        if section.header:
            extract_and_render_images(section.header.part)
            for hp in section.header.paragraphs:
                text = hp.text.strip()
                if text:
                    check_page_break(14)
                    page.insert_text(fitz.Point(margin_x, y_cursor), text, fontsize=9, fontname="time", color=(0.2, 0.2, 0.2))
                    y_cursor += 12
            if section.header.paragraphs or hasattr(section.header.part, "rels"):
                y_cursor += 10
            break

    # B. Main Body Images
    extract_and_render_images(doc.part)

    # C. Main Body Paragraphs with Run-Level Styling
    for p in doc.paragraphs:
        full_text = p.text.strip()
        if not full_text:
            y_cursor += 6
            continue

        style_name = (p.style.name or "").lower()
        align = str(p.alignment or "").lower()

        # Base font size for paragraph
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

        # Collect runs or fallback to paragraph
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

        # Flatten runs into styled words for wrapping
        styled_words = []
        for text_chunk, b_flag, i_flag, sz in runs_data:
            words = text_chunk.split()
            for w in words:
                styled_words.append((w, b_flag, i_flag, sz))

        if not styled_words:
            continue

        # Wrap styled words into lines
        lines = []
        current_line = []
        current_w = 0.0

        for w_text, b_flag, i_flag, sz in styled_words:
            w_font = "tiro" if b_flag else ("tiit" if i_flag else "time")
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

        # Render lines with run-level font switching (Times-Bold vs Times-Roman)
        for line in lines:
            check_page_break(line_h)
            
            # Calculate alignment
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
                fontname="tiro",
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
                    page.insert_text(fitz.Point(margin_x, y_cursor), text, fontsize=9, fontname="time", color=(0.4, 0.4, 0.4))
                    y_cursor += 12
            break

    if pdf_doc.page_count == 0:
        p = pdf_doc.new_page(width=page_w, height=page_h)
        p.insert_text(fitz.Point(margin_x, margin_y), "Converted Document", fontsize=12, fontname="time")

    buf = io.BytesIO()
    pdf_doc.save(buf, garbage=3, deflate=True)
    pdf_doc.close()
    return buf.getvalue()

print("Serif runs docx converter loaded")
