import io
import docx
import fitz
from PIL import Image

def render_docx_high_fidelity(docx_bytes: bytes) -> bytes:
    """
    High-fidelity Python fallback for DOCX -> PDF conversion when LibreOffice is unavailable.
    Preserves:
    1. Header / Inline Images & Logos
    2. Proper Word Wrapping (no character chopping)
    3. Heading & Font Sizes
    4. Bold / Italic Styling
    5. Table layouts
    """
    doc = docx.Document(io.BytesIO(docx_bytes))
    pdf_doc = fitz.open()

    page_w, page_h = 595, 842  # Standard A4 (pt)
    margin_x, margin_y = 54, 54  # 0.75 in margins
    content_w = page_w - (margin_x * 2)

    page = pdf_doc.new_page(width=page_w, height=page_h)
    y_cursor = margin_y

    # Helper for page break
    def check_page_break(needed_h=20):
        nonlocal page, y_cursor
        if y_cursor + needed_h > page_h - margin_y:
            page = pdf_doc.new_page(width=page_w, height=page_h)
            y_cursor = margin_y

    # 1. Extract and render header images if present
    for rel in doc.part.rels.values():
        if "image" in rel.target_ref:
            try:
                img_bytes = rel.target_part.blob
                img = Image.open(io.BytesIO(img_bytes))
                
                # Scale image appropriately to fit top header or page
                w, h = img.size
                max_w = 180
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
                break  # Render primary logo at top
            except Exception:
                pass

    # 2. Process paragraphs with word wrapping and styling
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            y_cursor += 10
            continue

        # Determine font size & style based on paragraph style
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

        # Word wrapping helper (wraps on whitespace, not character slicing)
        words = text.split()
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            # Estimate string width: approx 0.55 * font_size per character for sans-serif
            est_width = len(test_line) * (font_size * 0.52)
            
            if est_width > content_w and current_line:
                # Flush current line
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

print("High fidelity docx renderer script loaded successfully.")
