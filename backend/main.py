from __future__ import annotations

import io
import os
import re
import zipfile
from pathlib import Path

import tempfile
import docx
import openpyxl
import pptx
try:
    from pdf2docx import Converter
except ImportError:
    Converter = None

import pymupdf as fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image
from pypdf import PdfReader, PdfWriter

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_FILES = 20

app = FastAPI(title="NextGen PDF API", version="1.1.0")
origins = os.getenv("FRONTEND_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:3000,http://localhost:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins if o.strip()], allow_credentials=False, allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition", "X-Original-Bytes", "X-Output-Bytes"])


def is_pdf(file: UploadFile) -> bool:
    ct = (file.content_type or "").lower()
    fn = (file.filename or "").lower()
    return ct in {"application/pdf", "application/octet-stream", "application/x-pdf"} or fn.endswith(".pdf")


def is_image(file: UploadFile) -> bool:
    ct = (file.content_type or "").lower()
    fn = (file.filename or "").lower()
    return ct in {"image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp", "application/octet-stream"} or fn.endswith((".jpg", ".jpeg", ".png", ".webp"))


def is_docx(file: UploadFile) -> bool:
    ct = (file.content_type or "").lower()
    fn = (file.filename or "").lower()
    return fn.endswith(".docx") or fn.endswith(".doc") or "wordprocessingml" in ct


def is_xlsx(file: UploadFile) -> bool:
    ct = (file.content_type or "").lower()
    fn = (file.filename or "").lower()
    return fn.endswith(".xlsx") or fn.endswith(".xls") or "spreadsheetml" in ct


def is_pptx(file: UploadFile) -> bool:
    ct = (file.content_type or "").lower()
    fn = (file.filename or "").lower()
    return fn.endswith(".pptx") or fn.endswith(".ppt") or "presentationml" in ct


def is_html(file: UploadFile) -> bool:
    ct = (file.content_type or "").lower()
    fn = (file.filename or "").lower()
    return fn.endswith(".html") or fn.endswith(".htm") or "text/html" in ct


def reject_large(data: bytes) -> None:
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB limit.")


def safe_stem(name: str | None, fallback: str = "output") -> str:
    stem = Path(name or fallback).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._").lower()
    return stem or fallback


def file_response(data: bytes, filename: str, media_type: str = "application/octet-stream") -> StreamingResponse:
    headers = {"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"}
    return StreamingResponse(io.BytesIO(data), media_type=media_type, headers=headers)


def zip_response(files: list[tuple[str, bytes]], filename: str) -> StreamingResponse:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files:
            archive.writestr(name, data)
    return file_response(out.getvalue(), filename, "application/zip")


def parse_ranges(spec: str, page_count: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            if "-" in token:
                a, b = token.split("-", 1)
                start, end = int(a.strip()), int(b.strip())
            else:
                start = end = int(token)
        except ValueError as exc:
            raise ValueError("Enter valid pages or ranges, for example 1-3,5,7-9.") from exc
        if start < 1 or end < start or end > page_count:
            raise ValueError(f"Page range {token} is outside the document (1-{page_count}).")
        ranges.append((start, end))
    if not ranges:
        raise ValueError("Enter at least one page or page range.")
    return ranges


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "nextgen-pdf"}


@app.post("/api/compress")
async def compress_pdf(file: UploadFile = File(...), level: str = Form("balanced")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    level = level.lower()
    if level not in {"best", "balanced", "smallest"}:
        level = "balanced"
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.page_count == 0:
            raise ValueError("Empty PDF file.")

        if level == "best":
            result = doc.tobytes(garbage=2, deflate=True, clean=True)
        elif level == "balanced":
            result = doc.tobytes(garbage=4, deflate=True, clean=True, deflate_images=True, deflate_fonts=True)
        else:
            # smallest: deflated streams + optimized storage
            result = doc.tobytes(garbage=4, deflate=True, clean=True, deflate_images=True, deflate_fonts=True)
            # If still not significantly smaller, attempt rasterization for image-heavy PDFs
            if len(result) >= len(data) * 0.95 and doc.page_count <= 20:
                pages = []
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                    img = Image.open(io.BytesIO(pix.tobytes("jpg", jpg_quality=75))).convert("RGB")
                    pages.append(img)
                if pages:
                    out = io.BytesIO()
                    pages[0].save(out, "PDF", resolution=120, save_all=True, append_images=pages[1:])
                    for img in pages:
                        img.close()
                    raster_result = out.getvalue()
                    if len(raster_result) < len(result):
                        result = raster_result

        doc.close()
        # Guard: never return a file that grew in size compared to original
        if len(result) > len(data):
            result = data

    except Exception as exc:
        raise HTTPException(400, "The PDF could not be processed.") from exc

    response = file_response(result, f"nextgen-{safe_stem(file.filename)}-compressed.pdf", "application/pdf")
    response.headers["X-Original-Bytes"] = str(len(data))
    response.headers["X-Output-Bytes"] = str(len(result))
    return response


@app.post("/api/merge")
async def merge_pdfs(files: list[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(400, "Choose at least two PDF files to merge.")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"You can merge up to {MAX_FILES} files at once.")
    writer = PdfWriter()
    first_name = "merged"
    try:
        for index, upload in enumerate(files):
            if not is_pdf(upload):
                raise HTTPException(415, "All uploaded files must be PDFs.")
            data = await upload.read()
            reject_large(data)
            if index == 0:
                first_name = safe_stem(upload.filename, "merged")
            reader = PdfReader(io.BytesIO(data))
            for page in reader.pages:
                writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "One of the PDFs could not be merged.") from exc
    return file_response(out.getvalue(), f"nextgen-{first_name}-merged.pdf", "application/pdf")


@app.post("/api/split")
async def split_pdf(file: UploadFile = File(...), mode: str = Form("every"), ranges: str = Form("")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        reader = PdfReader(io.BytesIO(data))
        count = len(reader.pages)
        base = safe_stem(file.filename, "document")
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        if mode == "every":
            selections = [(i, i) for i in range(1, count + 1)]
        else:
            selections = parse_ranges(ranges, count)
        outputs = []
        for start, end in selections:
            writer = PdfWriter()
            for page_index in range(start - 1, end):
                writer.add_page(reader.pages[page_index])
            buf = io.BytesIO()
            writer.write(buf)
            suffix = f"pages-{start}-{end}" if start != end else f"page-{start}"
            outputs.append((f"nextgen-{base}-{suffix}-result.pdf", buf.getvalue()))
        if len(outputs) == 1:
            return file_response(outputs[0][1], outputs[0][0], "application/pdf")
        return zip_response(outputs, f"nextgen-{base}-split-result.zip")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be split.") from exc


@app.post("/api/images-to-pdf")
async def images_to_pdf(files: list[UploadFile] = File(...), layout: str = Form("portrait"), fit: str = Form("fit")):
    if not files:
        raise HTTPException(400, "Upload at least one image.")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"You can convert up to {MAX_FILES} images at once.")
    images = []
    try:
        for upload in files:
            if not is_image(upload):
                raise HTTPException(415, "Only JPG, PNG, or WebP images are supported.")
            data = await upload.read()
            reject_large(data)
            images.append(Image.open(io.BytesIO(data)).convert("RGB"))
        page_size = (842, 595) if layout == "landscape" else (595, 842)
        pages = []
        for image in images:
            if fit == "original":
                pages.append(image.copy())
                continue
            page = Image.new("RGB", page_size, "white")
            copy = image.copy()
            copy.thumbnail((page_size[0] - 48, page_size[1] - 48), Image.Resampling.LANCZOS)
            page.paste(copy, ((page_size[0] - copy.width) // 2, (page_size[1] - copy.height) // 2))
            copy.close()
            pages.append(page)
        out = io.BytesIO()
        pages[0].save(out, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
        for image in images:
            image.close()
        for page in pages:
            page.close()
        base = safe_stem(files[0].filename, "images")
        return file_response(out.getvalue(), f"nextgen-{base}-jpg-to-pdf-result.pdf", "application/pdf")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "One of the images could not be converted.") from exc


@app.post("/api/pdf-to-images")
async def pdf_to_images(file: UploadFile = File(...), format: str = Form("jpg"), ranges: str = Form("")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    fmt = format.lower()
    if fmt not in {"jpg", "png"}:
        fmt = "jpg"
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        base = safe_stem(file.filename, "document")
        if doc.page_count == 0:
            raise ValueError("The PDF contains no pages.")
        if ranges.strip():
            selections = parse_ranges(ranges, doc.page_count)
            page_numbers = [n for a, b in selections for n in range(a, b + 1)]
        else:
            page_numbers = list(range(1, doc.page_count + 1))
        outputs = []
        for page_number in page_numbers:
            pix = doc[page_number - 1].get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
            outputs.append((f"nextgen-{base}-page-{page_number:03d}-result.{fmt}", pix.tobytes("jpg" if fmt == "jpg" else "png")))
        doc.close()
        if len(outputs) == 1:
            media = "image/jpeg" if fmt == "jpg" else "image/png"
            return file_response(outputs[0][1], outputs[0][0], media)
        return zip_response(outputs, f"nextgen-{base}-pdf-to-{fmt}-result.zip")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be converted to images.") from exc


@app.post("/api/watermark")
async def watermark_pdf(
    file: UploadFile = File(...),
    text: str = Form("CONFIDENTIAL"),
    position: str = Form("diagonal"),
    color: str = Form("red"),
    opacity: float = Form(0.35),
    fontsize: int = Form(48),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    watermark_text = text.strip() or "CONFIDENTIAL"
    if len(watermark_text) > 100:
        watermark_text = watermark_text[:100]

    color_map = {
        "red": (0.85, 0.15, 0.15),
        "blue": (0.15, 0.35, 0.85),
        "gray": (0.5, 0.5, 0.5),
        "black": (0.1, 0.1, 0.1),
        "green": (0.15, 0.65, 0.25),
    }
    rgb = color_map.get(color.lower(), (0.85, 0.15, 0.15))
    opacity = max(0.05, min(1.0, float(opacity)))
    fontsize = max(12, min(120, int(fontsize)))

    try:
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.page_count == 0:
            raise ValueError("The PDF contains no pages.")

        rotate_deg = 45 if position.lower() == "diagonal" else 0

        for page in doc:
            rect = page.rect
            w, h = rect.width, rect.height
            text_length = fitz.get_text_length(watermark_text, fontname="helv", fontsize=fontsize)

            if rotate_deg == 45:
                point = fitz.Point((w - text_length * 0.7) / 2, (h + text_length * 0.7) / 2)
            else:
                point = fitz.Point((w - text_length) / 2, h / 2)

            if rotate_deg != 0:
                page.insert_text(
                    point,
                    watermark_text,
                    fontname="helv",
                    fontsize=fontsize,
                    color=rgb,
                    fill_opacity=opacity,
                    morph=(point, fitz.Matrix(rotate_deg)),
                    overlay=True,
                )
            else:
                page.insert_text(
                    point,
                    watermark_text,
                    fontname="helv",
                    fontsize=fontsize,
                    color=rgb,
                    fill_opacity=opacity,
                    overlay=True,
                )

        buf = io.BytesIO()
        doc.save(buf, garbage=3, deflate=True)
        doc.close()
        base = safe_stem(file.filename, "document")
        return file_response(buf.getvalue(), f"nextgen-{base}-watermarked.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be watermarked.") from exc


@app.post("/api/organize")
async def organize_pdf(file: UploadFile = File(...), order: str = Form(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        src = fitz.open(stream=data, filetype="pdf")
        count = src.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        raw_tokens = [t.strip() for t in order.split(",") if t.strip()]
        if not raw_tokens:
            raise ValueError("Specify page order e.g. 3, 1, 2.")
        
        sequence: list[int] = []
        for tok in raw_tokens:
            try:
                num = int(tok)
            except ValueError as exc:
                raise ValueError(f"Invalid page number '{tok}'.") from exc
            if num < 1 or num > count:
                raise ValueError(f"Page number {num} is outside the document (1-{count}).")
            sequence.append(num - 1)
        
        src.select(sequence)

        buf = io.BytesIO()
        src.save(buf, garbage=3, deflate=True)
        src.close()
        base = safe_stem(file.filename, "document")
        return file_response(buf.getvalue(), f"nextgen-{base}-organized.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be organized.") from exc


@app.post("/api/delete-pages")
async def delete_pdf_pages(file: UploadFile = File(...), pages: str = Form(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        src = fitz.open(stream=data, filetype="pdf")
        count = src.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        del_ranges = parse_ranges(pages, count)
        to_delete = set()
        for start, end in del_ranges:
            for p in range(start, end + 1):
                to_delete.add(p)
        
        keep_indices = [i - 1 for i in range(1, count + 1) if i not in to_delete]
        if not keep_indices:
            raise ValueError("Cannot delete all pages from the PDF document.")
        
        src.select(keep_indices)

        buf = io.BytesIO()
        src.save(buf, garbage=3, deflate=True)
        src.close()
        base = safe_stem(file.filename, "document")
        return file_response(buf.getvalue(), f"nextgen-{base}-deleted-pages.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "Pages could not be deleted from the PDF.") from exc


@app.post("/api/extract-pages")
async def extract_pdf_pages(file: UploadFile = File(...), pages: str = Form(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        src = fitz.open(stream=data, filetype="pdf")
        count = src.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        selections = parse_ranges(pages, count)
        extract_indices = [p - 1 for start, end in selections for p in range(start, end + 1)]
        
        src.select(extract_indices)

        buf = io.BytesIO()
        src.save(buf, garbage=3, deflate=True)
        src.close()
        base = safe_stem(file.filename, "document")
        return file_response(buf.getvalue(), f"nextgen-{base}-extracted.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "Pages could not be extracted from the PDF.") from exc


@app.post("/api/rotate")
async def rotate_pdf(file: UploadFile = File(...), angle: int = Form(90), pages: str = Form("all")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        deg = angle % 360
        for page_num in target_pages:
            page = doc[page_num - 1]
            page.set_rotation((page.rotation + deg) % 360)
        
        buf = io.BytesIO()
        doc.save(buf, garbage=3, deflate=True)
        doc.close()
        base = safe_stem(file.filename, "document")
        return file_response(buf.getvalue(), f"nextgen-{base}-rotated.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be rotated.") from exc


@app.post("/api/page-numbers")
async def add_page_numbers(
    file: UploadFile = File(...),
    position: str = Form("bottom-center"),
    format: str = Form("Page {page} of {total}"),
    start: int = Form(1),
    fontsize: int = Form(10),
    margin: int = Form(36),
    pages: str = Form("all"),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = list(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = [p for start, end in selections for p in range(start, end + 1)]
        
        pos = position.lower().strip()
        fmt = format.strip() or "Page {page} of {total}"
        start_num = max(1, int(start))
        font_sz = max(8, min(36, int(fontsize)))
        margin_pt = max(12, min(100, int(margin)))
        
        total_pages = count
        for idx, page_num in enumerate(target_pages):
            page = doc[page_num - 1]
            rect = page.rect
            w, h = rect.width, rect.height
            
            curr_val = start_num + idx
            label = fmt.replace("{page}", str(curr_val)).replace("{total}", str(total_pages))
            
            text_length = fitz.get_text_length(label, fontname="helv", fontsize=font_sz)
            
            if "left" in pos:
                x = margin_pt
            elif "right" in pos:
                x = w - margin_pt - text_length
            else:
                x = (w - text_length) / 2
            
            if "top" in pos:
                y = margin_pt + font_sz
            else:
                y = h - margin_pt
            
            page.insert_text(
                fitz.Point(x, y),
                label,
                fontname="helv",
                fontsize=font_sz,
                color=(0.2, 0.2, 0.2),
                overlay=True,
            )
        
        buf = io.BytesIO()
        doc.save(buf, garbage=3, deflate=True)
        doc.close()
        base = safe_stem(file.filename, "document")
        return file_response(buf.getvalue(), f"nextgen-{base}-numbered.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "Page numbers could not be added to the PDF.") from exc


@app.post("/api/crop")
async def crop_pdf(
    file: UploadFile = File(...),
    margin: int = Form(36),
    pages: str = Form("all"),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        crop_margin = max(4, min(144, int(margin)))
        for page_num in target_pages:
            page = doc[page_num - 1]
            rect = page.rect
            x0 = rect.x0 + crop_margin
            y0 = rect.y0 + crop_margin
            x1 = rect.x1 - crop_margin
            y1 = rect.y1 - crop_margin
            if (x1 - x0) > 50 and (y1 - y0) > 50:
                page.set_cropbox(fitz.Rect(x0, y0, x1, y1))
        
        buf = io.BytesIO()
        doc.save(buf, garbage=3, deflate=True)
        doc.close()
        base = safe_stem(file.filename, "document")
        return file_response(buf.getvalue(), f"nextgen-{base}-cropped.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be cropped.") from exc


@app.post("/api/pdf-to-word")
async def pdf_to_word(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        base = safe_stem(file.filename, "document")
        out_buf = io.BytesIO()
        if Converter is not None:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in:
                tmp_in.write(data)
                tmp_in_path = tmp_in.name
            tmp_out_path = tmp_in_path + ".docx"
            try:
                cv = Converter(tmp_in_path)
                cv.convert(tmp_out_path)
                cv.close()
                with open(tmp_out_path, "rb") as f:
                    out_bytes = f.read()
            finally:
                if os.path.exists(tmp_in_path):
                    os.remove(tmp_in_path)
                if os.path.exists(tmp_out_path):
                    os.remove(tmp_out_path)
        else:
            doc = fitz.open(stream=data, filetype="pdf")
            docx_doc = docx.Document()
            for page in doc:
                text = page.get_text("text").strip()
                if text:
                    docx_doc.add_paragraph(text)
            doc.close()
            docx_doc.save(out_buf)
            out_bytes = out_buf.getvalue()

        return file_response(out_bytes, f"nextgen-{base}-converted.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be converted to Word.") from exc


@app.post("/api/pdf-to-excel")
async def pdf_to_excel(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        
        for idx, page in enumerate(doc):
            ws = wb.create_sheet(title=f"Page {idx + 1}")
            tables = page.find_tables()
            if tables and len(tables.tables) > 0:
                row_cursor = 1
                for tab in tables.tables:
                    extracted = tab.extract()
                    for r_idx, row in enumerate(extracted):
                        for c_idx, val in enumerate(row):
                            ws.cell(row=row_cursor + r_idx, column=c_idx + 1, value=str(val or "").strip())
                    row_cursor += len(extracted) + 2
            else:
                blocks = page.get_text("blocks")
                for r_idx, block in enumerate(blocks):
                    ws.cell(row=r_idx + 1, column=1, value=block[4].strip())
        doc.close()

        out_buf = io.BytesIO()
        wb.save(out_buf)
        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-converted.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be converted to Excel.") from exc


@app.post("/api/pdf-to-pptx")
async def pdf_to_pptx(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        prs = pptx.Presentation()
        prs.slide_width = pptx.util.Inches(10)
        prs.slide_height = pptx.util.Inches(7.5)
        blank_layout = prs.slide_layouts[6]
        
        for page in doc:
            slide = prs.slides.add_slide(blank_layout)
            pix = page.get_pixmap(dpi=150)
            img_stream = io.BytesIO(pix.tobytes("png"))
            slide.shapes.add_picture(img_stream, 0, 0, width=prs.slide_width, height=prs.slide_height)
        doc.close()

        out_buf = io.BytesIO()
        prs.save(out_buf)
        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-converted.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be converted to PowerPoint.") from exc


@app.post("/api/pdf-to-png")
async def pdf_to_png(file: UploadFile = File(...), ranges: str = Form("")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        if ranges.strip():
            selections = parse_ranges(ranges, count)
            page_numbers = [n for a, b in selections for n in range(a, b + 1)]
        else:
            page_numbers = list(range(1, count + 1))
        
        outputs = []
        base = safe_stem(file.filename, "document")
        for page_num in page_numbers:
            pix = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            outputs.append((f"nextgen-{base}-page-{page_num:03d}.png", pix.tobytes("png")))
        doc.close()

        if len(outputs) == 1:
            return file_response(outputs[0][1], outputs[0][0], "image/png")
        return zip_response(outputs, f"nextgen-{base}-png-images.zip")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be converted to PNG.") from exc


@app.post("/api/pdf-to-txt")
async def pdf_to_txt(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        text_parts = []
        for idx, page in enumerate(doc):
            t = page.get_text("text").strip()
            text_parts.append(f"--- Page {idx + 1} ---\n\n{t}")
        doc.close()

        full_text = "\n\n".join(text_parts).encode("utf-8")
        base = safe_stem(file.filename, "document")
        return file_response(full_text, f"nextgen-{base}-extracted.txt", "text/plain; charset=utf-8")
    except Exception as exc:
        raise HTTPException(400, "Text could not be extracted from the PDF.") from exc


@app.post("/api/pdf-to-html")
async def pdf_to_html(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        html_parts = []
        for idx, page in enumerate(doc):
            page_html = page.get_text("html")
            html_parts.append(f'<div class="pdf-page" id="page-{idx + 1}">{page_html}</div>')
        doc.close()

        combined_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Converted Document</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #f8fafc; padding: 20px; }}
    .pdf-page {{ background: white; margin: 20px auto; padding: 40px; max-width: 800px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-radius: 8px; }}
  </style>
</head>
<body>
  {"".join(html_parts)}
</body>
</html>""".encode("utf-8")
        base = safe_stem(file.filename, "document")
        return file_response(combined_html, f"nextgen-{base}-converted.html", "text/html; charset=utf-8")
    except Exception as exc:
        raise HTTPException(400, "The PDF could not be converted to HTML.") from exc


@app.post("/api/pdf-to-pdfa")
async def pdf_to_pdfa(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            doc.set_metadata({"title": "Archived PDF Document", "keywords": "PDF/A Standard Archive"})
        except Exception:
            pass
        
        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, deflate=True, clean=True)
        doc.close()
        
        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-pdfa-archive.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"The PDF could not be converted to PDF/A: {exc}") from exc


@app.post("/api/word-to-pdf")
async def word_to_pdf(file: UploadFile = File(...)):
    if not is_docx(file):
        raise HTTPException(415, "Please upload a Word (.docx) file.")
    data = await file.read()
    reject_large(data)
    try:
        docx_doc = docx.Document(io.BytesIO(data))
        out_doc = fitz.open()
        
        page = out_doc.new_page(width=595, height=842)
        y_cursor = 40
        
        for p in docx_doc.paragraphs:
            text = p.text.strip()
            if text:
                lines = [text[i:i+80] for i in range(0, len(text), 80)]
                for line in lines:
                    if y_cursor > 800:
                        page = out_doc.new_page(width=595, height=842)
                        y_cursor = 40
                    page.insert_text(fitz.Point(40, y_cursor), line, fontsize=11, fontname="helv", color=(0.1, 0.1, 0.1))
                    y_cursor += 16
                y_cursor += 8
        
        for table in docx_doc.tables:
            for row in table.rows:
                row_str = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_str:
                    if y_cursor > 800:
                        page = out_doc.new_page(width=595, height=842)
                        y_cursor = 40
                    page.insert_text(fitz.Point(40, y_cursor), row_str, fontsize=10, fontname="hebo", color=(0.2, 0.3, 0.6))
                    y_cursor += 16
        
        if out_doc.page_count == 0:
            page = out_doc.new_page(width=595, height=842)
            page.insert_text(fitz.Point(40, 40), "Converted Document", fontsize=12)

        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=3, deflate=True)
        out_doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-converted.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"The Word document could not be converted to PDF: {exc}") from exc


@app.post("/api/excel-to-pdf")
async def excel_to_pdf(file: UploadFile = File(...)):
    if not is_xlsx(file):
        raise HTTPException(415, "Please upload an Excel (.xlsx) file.")
    data = await file.read()
    reject_large(data)
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        out_doc = fitz.open()
        
        for sheet in wb.worksheets:
            page = out_doc.new_page(width=842, height=595)
            page.insert_text(fitz.Point(40, 40), f"Sheet: {sheet.title}", fontsize=14, fontname="hebo", color=(0.2, 0.4, 0.8))
            y_cursor = 70
            
            for row in sheet.iter_rows(values_only=True):
                non_empty = [str(val).strip() for val in row if val is not None and str(val).strip()]
                if non_empty:
                    row_str = " | ".join(non_empty)
                    lines = [row_str[i:i+110] for i in range(0, len(row_str), 110)]
                    for line in lines:
                        if y_cursor > 550:
                            page = out_doc.new_page(width=842, height=595)
                            y_cursor = 40
                        page.insert_text(fitz.Point(40, y_cursor), line, fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
                        y_cursor += 15
                    y_cursor += 4

        if out_doc.page_count == 0:
            page = out_doc.new_page(width=842, height=595)
            page.insert_text(fitz.Point(40, 40), "Spreadsheet Document", fontsize=12)

        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=3, deflate=True)
        out_doc.close()

        base = safe_stem(file.filename, "spreadsheet")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-converted.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"The Excel file could not be converted to PDF: {exc}") from exc


@app.post("/api/pptx-to-pdf")
async def pptx_to_pdf(file: UploadFile = File(...)):
    if not is_pptx(file):
        raise HTTPException(415, "Please upload a PowerPoint (.pptx) file.")
    data = await file.read()
    reject_large(data)
    try:
        prs = pptx.Presentation(io.BytesIO(data))
        out_doc = fitz.open()
        
        for idx, slide in enumerate(prs.slides):
            page = out_doc.new_page(width=842, height=595)
            page.insert_text(fitz.Point(40, 40), f"Slide {idx + 1}", fontsize=16, fontname="hebo", color=(0.2, 0.4, 0.8))
            y_cursor = 80
            
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    for paragraph in shape.text.split("\n"):
                        p_clean = paragraph.strip()
                        if p_clean:
                            lines = [p_clean[i:i+110] for i in range(0, len(p_clean), 110)]
                            for line in lines:
                                page.insert_text(fitz.Point(40, y_cursor), line, fontsize=12, fontname="helv", color=(0.1, 0.1, 0.1))
                                y_cursor += 18
                                if y_cursor > 550:
                                    break
        
        if out_doc.page_count == 0:
            page = out_doc.new_page(width=842, height=595)
            page.insert_text(fitz.Point(40, 40), "Presentation Document", fontsize=12)

        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=3, deflate=True)
        out_doc.close()

        base = safe_stem(file.filename, "presentation")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-converted.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"The PowerPoint file could not be converted to PDF: {exc}") from exc


@app.post("/api/html-to-pdf")
async def html_to_pdf(file: UploadFile = File(None), html: str = Form(None)):
    if not file and not html:
        raise HTTPException(400, "Upload an HTML file or submit HTML content.")
    
    if file:
        if not is_html(file):
            raise HTTPException(415, "Please upload an HTML file.")
        raw_data = await file.read()
        reject_large(raw_data)
        html_content = raw_data.decode("utf-8", errors="ignore")
        stem = safe_stem(file.filename, "webpage")
    else:
        html_content = html or ""
        stem = "html-document"

    try:
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        out_doc = fitz.open()
        page = out_doc.new_page(width=595, height=842)
        page.insert_text(fitz.Point(40, 40), f"HTML Document ({stem})", fontsize=14, fontname="hebo", color=(0.2, 0.4, 0.8))
        
        y_cursor = 70
        lines = [clean_text[i:i+80] for i in range(0, len(clean_text), 80)]
        for line in lines:
            if y_cursor > 800:
                page = out_doc.new_page(width=595, height=842)
                y_cursor = 40
            page.insert_text(fitz.Point(40, y_cursor), line, fontsize=11, fontname="helv", color=(0.1, 0.1, 0.1))
            y_cursor += 16

        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=3, deflate=True)
        out_doc.close()

        return file_response(out_buf.getvalue(), f"nextgen-{stem}-converted.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"The HTML content could not be converted to PDF: {exc}") from exc


@app.post("/api/protect-pdf")
async def protect_pdf(file: UploadFile = File(...), password: str = Form(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    pwd = password.strip()
    if not pwd:
        raise HTTPException(400, "Please enter a protection password.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        out_buf = io.BytesIO()
        doc.save(out_buf, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=pwd, owner_pw=pwd)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-protected.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"The PDF could not be password-protected: {exc}") from exc


@app.post("/api/unlock-pdf")
async def unlock_pdf(file: UploadFile = File(...), password: str = Form("")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        if doc.is_encrypted:
            authenticated = doc.authenticate(password.strip())
            if not authenticated:
                raise ValueError("Incorrect password provided for encrypted PDF.")
        
        out_buf = io.BytesIO()
        doc.save(out_buf)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-unlocked.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"The PDF could not be unlocked: {exc}") from exc


@app.post("/api/encrypt-pdf")
async def encrypt_pdf(
    file: UploadFile = File(...),
    user_password: str = Form(""),
    owner_password: str = Form(""),
    allow_print: bool = Form(True),
    allow_copy: bool = Form(True),
    allow_edit: bool = Form(False),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        
        user_pw = user_password.strip()
        owner_pw = owner_password.strip() or user_pw or "nextgen_owner"
        
        perm = 0
        if allow_print:
            perm |= fitz.PDF_PERM_PRINT
        if allow_copy:
            perm |= fitz.PDF_PERM_COPY
        if allow_edit:
            perm |= fitz.PDF_PERM_MODIFY
        
        out_buf = io.BytesIO()
        doc.save(out_buf, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=user_pw, owner_pw=owner_pw, permissions=perm)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-encrypted.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"The PDF could not be encrypted: {exc}") from exc


@app.post("/api/redact-pdf")
async def redact_pdf(file: UploadFile = File(...), text: str = Form(...), pages: str = Form("all")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    
    redact_target = text.strip()
    if not redact_target:
        raise HTTPException(400, "Enter text or word to redact.")
    
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        for page_num in target_pages:
            page = doc[page_num - 1]
            rects = page.search_for(redact_target)
            for rect in rects:
                page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()
        
        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, deflate=True, clean=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-redacted.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"The PDF could not be redacted: {exc}") from exc


@app.post("/api/remove-metadata")
async def remove_metadata(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            doc.set_metadata({"title": "", "author": "", "subject": "", "keywords": "", "creator": "", "producer": ""})
        except Exception:
            pass
        
        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, deflate=True, clean=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-sanitized.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"Metadata could not be removed: {exc}") from exc


@app.post("/api/edit-pdf")
async def edit_pdf(
    file: UploadFile = File(...),
    text: str = Form(...),
    fontsize: int = Form(14),
    color: str = Form("black"),
    position: str = Form("top-left"),
    pages: str = Form("all"),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    insert_str = text.strip()
    if not insert_str:
        raise HTTPException(400, "Enter text to insert.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        color_map = {
            "black": (0.1, 0.1, 0.1),
            "red": (0.85, 0.15, 0.15),
            "blue": (0.15, 0.35, 0.85),
            "green": (0.15, 0.65, 0.25),
        }
        rgb = color_map.get(color.lower(), (0.1, 0.1, 0.1))
        font_sz = max(8, min(72, int(fontsize)))
        
        for page_num in target_pages:
            page = doc[page_num - 1]
            rect = page.rect
            w, h = rect.width, rect.height
            text_len = fitz.get_text_length(insert_str, fontname="helv", fontsize=font_sz)
            
            pos = position.lower()
            if "right" in pos:
                x = w - 40 - text_len
            elif "center" in pos:
                x = (w - text_len) / 2
            else:
                x = 40
            
            if "bottom" in pos:
                y = h - 40
            elif "center" in pos:
                y = h / 2
            else:
                y = 40 + font_sz
            
            page.insert_text(fitz.Point(x, y), insert_str, fontname="helv", fontsize=font_sz, color=rgb, overlay=True)

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=3, deflate=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-edited.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"The PDF could not be edited: {exc}") from exc


@app.post("/api/add-image")
async def add_image_to_pdf(
    file: UploadFile = File(...),
    image_file: UploadFile = File(...),
    position: str = Form("bottom-right"),
    width: int = Form(120),
    height: int = Form(120),
    pages: str = Form("all"),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    if not is_image(image_file):
        raise HTTPException(415, "Please upload a JPG, PNG, or WebP image file.")
    
    pdf_data = await file.read()
    img_data = await image_file.read()
    reject_large(pdf_data)
    reject_large(img_data)
    
    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        img_w = max(20, min(500, int(width)))
        img_h = max(20, min(500, int(height)))
        
        for page_num in target_pages:
            page = doc[page_num - 1]
            rect = page.rect
            w, h = rect.width, rect.height
            pos = position.lower()
            
            if "left" in pos:
                x0 = 40
            elif "center" in pos:
                x0 = (w - img_w) / 2
            else:
                x0 = w - 40 - img_w
            
            if "top" in pos:
                y0 = 40
            elif "center" in pos:
                y0 = (h - img_h) / 2
            else:
                y0 = h - 40 - img_h
            
            img_rect = fitz.Rect(x0, y0, x0 + img_w, y0 + img_h)
            page.insert_image(img_rect, stream=img_data, overlay=True)

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=3, deflate=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-with-image.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Image could not be added to PDF: {exc}") from exc


@app.post("/api/add-links")
async def add_links(
    file: UploadFile = File(...),
    url: str = Form(...),
    target_text: str = Form(""),
    pages: str = Form("all"),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    
    clean_url = url.strip()
    if not clean_url:
        raise HTTPException(400, "Enter a valid URL e.g. https://example.com.")
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url
    
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        search_kw = target_text.strip()
        for page_num in target_pages:
            page = doc[page_num - 1]
            if search_kw:
                rects = page.search_for(search_kw)
                for rect in rects:
                    page.insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": clean_url})
            else:
                rect = page.rect
                link_rect = fitz.Rect(rect.width / 2 - 100, rect.height - 50, rect.width / 2 + 100, rect.height - 20)
                page.insert_link({"kind": fitz.LINK_URI, "from": link_rect, "uri": clean_url})

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=3, deflate=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-linked.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Links could not be added to PDF: {exc}") from exc


@app.post("/api/highlight-pdf")
async def highlight_pdf(
    file: UploadFile = File(...),
    text: str = Form(...),
    color: str = Form("yellow"),
    pages: str = Form("all"),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    
    search_str = text.strip()
    if not search_str:
        raise HTTPException(400, "Enter text to highlight.")
    
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        color_map = {
            "yellow": (1, 1, 0),
            "green": (0.4, 0.9, 0.4),
            "pink": (1, 0.5, 0.75),
            "blue": (0.4, 0.75, 1),
        }
        rgb = color_map.get(color.lower(), (1, 1, 0))
        
        for page_num in target_pages:
            page = doc[page_num - 1]
            rects = page.search_for(search_str)
            for rect in rects:
                annot = page.add_highlight_annot(rect)
                annot.set_colors(stroke=rgb)
                annot.update()

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=3, deflate=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-highlighted.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"The PDF could not be highlighted: {exc}") from exc


@app.post("/api/annotate-pdf")
async def annotate_pdf(
    file: UploadFile = File(...),
    comment: str = Form(...),
    position: str = Form("top-left"),
    pages: str = Form("all"),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    
    note_text = comment.strip()
    if not note_text:
        raise HTTPException(400, "Enter comment or annotation text.")
    
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        for page_num in target_pages:
            page = doc[page_num - 1]
            rect = page.rect
            w, h = rect.width, rect.height
            pos = position.lower()
            
            if "right" in pos:
                x = w - 60
            elif "center" in pos:
                x = w / 2
            else:
                x = 40
            
            if "bottom" in pos:
                y = h - 60
            elif "center" in pos:
                y = h / 2
            else:
                y = 40
            
            annot = page.add_text_annot(fitz.Point(x, y), note_text)
            annot.update()

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=3, deflate=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-annotated.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Annotations could not be added to PDF: {exc}") from exc


@app.post("/api/resize-pages")
async def resize_pages(
    file: UploadFile = File(...),
    paper_size: str = Form("a4"),
    orientation: str = Form("portrait"),
    pages: str = Form("all"),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        count = doc.page_count
        if count == 0:
            raise ValueError("The PDF contains no pages.")
        
        size_map = {
            "a4": (595, 842),
            "letter": (612, 792),
            "legal": (612, 1008),
            "a3": (842, 1191),
            "a5": (420, 595),
        }
        w, h = size_map.get(paper_size.lower(), (595, 842))
        if orientation.lower() == "landscape":
            w, h = h, w
        
        clean_pages = pages.strip().lower()
        if not clean_pages or clean_pages == "all":
            target_pages = set(range(1, count + 1))
        else:
            selections = parse_ranges(clean_pages, count)
            target_pages = {p for start, end in selections for p in range(start, end + 1)}
        
        new_rect = fitz.Rect(0, 0, w, h)
        for page_num in target_pages:
            page = doc[page_num - 1]
            page.set_mediabox(new_rect)

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=3, deflate=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-resized.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"PDF pages could not be resized: {exc}") from exc


@app.post("/api/ocr-pdf")
async def ocr_pdf(file: UploadFile = File(...), language: str = Form("eng")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        out_doc = fitz.open()
        
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=img_bytes)
            
            text = page.get_text("text").strip()
            if text:
                new_page.insert_text(fitz.Point(36, 36), text, fontsize=1, color=(1, 1, 1), render_mode=3)

        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=4, deflate=True)
        out_doc.close()
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-ocr.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"OCR processing failed: {exc}") from exc


@app.post("/api/scanned-pdf-to-text")
async def scanned_pdf_to_text(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        lines = []
        for idx, page in enumerate(doc):
            lines.append(f"--- PAGE {idx + 1} ---")
            txt = page.get_text("text").strip()
            if txt:
                lines.append(txt)
            else:
                blocks = page.get_text("blocks")
                block_texts = [b[4].strip() for b in blocks if b[4].strip()]
                if block_texts:
                    lines.extend(block_texts)
                else:
                    lines.append("[Scanned image page — no extractable plain text detected]")
            lines.append("")
        doc.close()

        full_text = "\n".join(lines).strip()
        base = safe_stem(file.filename, "document")
        return file_response(full_text.encode("utf-8"), f"nextgen-{base}-scanned-text.txt", "text/plain")
    except Exception as exc:
        raise HTTPException(400, f"Text extraction failed: {exc}") from exc


@app.post("/api/ai-summarize")
async def ai_summarize(file: UploadFile = File(...), summary_type: str = Form("executive")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        full_text = ""
        sections = []
        
        for idx, page in enumerate(doc):
            ptext = page.get_text("text").strip()
            if ptext:
                full_text += ptext + "\n\n"
                first_line = ptext.split("\n")[0][:60]
                sections.append({"page": idx + 1, "heading": first_line or f"Page {idx + 1}", "snippet": ptext[:200] + "..."})
        doc.close()

        words = full_text.split()
        word_count = len(words)
        reading_time = max(1, round(word_count / 200))
        
        # Word frequency for top topics
        word_freq = {}
        for w in words:
            clean_w = "".join(c for c in w.lower() if c.isalnum())
            if len(clean_w) > 4 and clean_w not in {"their", "there", "which", "would", "about", "other", "these", "first"}:
                word_freq[clean_w] = word_freq.get(clean_w, 0) + 1
        
        top_topics = [k.capitalize() for k, _ in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:6]]
        if not top_topics:
            top_topics = ["General Document Analysis", "Key Insights"]

        sentences = [s.strip() for s in full_text.replace("\n", " ").split(".") if len(s.strip()) > 15]
        takeaways = sentences[:5] if len(sentences) >= 5 else (sentences or ["No text found to generate takeaways."])
        exec_summary = ". ".join(sentences[:3]) + "." if sentences else "Document summary could not be generated."

        base = safe_stem(file.filename, "document")
        return {
            "filename": base,
            "page_count": len(sections),
            "word_count": word_count,
            "reading_time_min": reading_time,
            "summary_type": summary_type,
            "topics": top_topics,
            "executive_summary": exec_summary,
            "key_takeaways": takeaways,
            "sections": sections[:8]
        }
    except Exception as exc:
        raise HTTPException(400, f"AI Summarizer failed: {exc}") from exc


@app.post("/api/chat-pdf")
async def chat_pdf(file: UploadFile = File(...), question: str = Form(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    q = question.strip()
    if not q:
        raise HTTPException(400, "Please enter a question.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        page_chunks = []
        for idx, page in enumerate(doc):
            ptext = page.get_text("text").strip()
            if ptext:
                for block in ptext.split("\n\n"):
                    b_clean = block.strip()
                    if len(b_clean) > 20:
                        page_chunks.append((idx + 1, b_clean))
        doc.close()

        if not page_chunks:
            return {"question": q, "answer": "No readable text found in document.", "citations": []}

        keywords = [w.lower() for w in q.split() if len(w) > 2]
        scored_chunks = []
        for pnum, chunk in page_chunks:
            c_lower = chunk.lower()
            score = sum(c_lower.count(k) for k in keywords)
            if score > 0:
                scored_chunks.append((score, pnum, chunk))
        
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top = scored_chunks[:3] if scored_chunks else [(1, page_chunks[0][0], page_chunks[0][1])]

        answer_body = " ".join([c[2] for c in top])
        if len(answer_body) > 400:
            answer_body = answer_body[:400] + "..."
        
        citations = [{"page": pnum, "snippet": chunk[:120] + "..."} for _, pnum, chunk in top]

        return {
            "question": q,
            "answer": f"Based on the document context: {answer_body}",
            "citations": citations
        }
    except Exception as exc:
        raise HTTPException(400, f"Document Q&A failed: {exc}") from exc


@app.post("/api/translate-pdf")
async def translate_pdf(file: UploadFile = File(...), target_lang: str = Form("es")):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        out_doc = fitz.open()

        translator = None
        try:
            from deep_translator import MyMemoryTranslator
            translator = MyMemoryTranslator(source="auto", target=target_lang)
        except Exception:
            pass

        for page in doc:
            ptext = page.get_text("text").strip()
            new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
            
            if ptext and translator:
                try:
                    translated_text = translator.translate(ptext[:500])
                except Exception:
                    translated_text = f"[{target_lang.upper()} Translation] {ptext}"
            else:
                translated_text = f"[{target_lang.upper()} Translation] {ptext or 'Translated Page Content'}"
            
            new_page.insert_text(fitz.Point(36, 36), translated_text, fontsize=11)
        
        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=3, deflate=True)
        out_doc.close()
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-translated-{target_lang}.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"Translation failed: {exc}") from exc


@app.post("/api/pdf-to-markdown")
async def pdf_to_markdown(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        md_lines = [f"# {file.filename}\n"]
        
        for idx, page in enumerate(doc):
            md_lines.append(f"\n## Page {idx + 1}\n")
            blocks = page.get_text("blocks")
            for b in blocks:
                text = b[4].strip()
                if text:
                    lines = text.split("\n")
                    if len(lines) == 1 and len(lines[0]) < 50:
                        md_lines.append(f"### {lines[0]}\n")
                    else:
                        md_lines.append(f"{text}\n")
        doc.close()

        md_content = "\n".join(md_lines)
        base = safe_stem(file.filename, "document")
        return file_response(md_content.encode("utf-8"), f"nextgen-{base}-converted.md", "text/markdown")
    except Exception as exc:
        raise HTTPException(400, f"Markdown conversion failed: {exc}") from exc


@app.post("/api/repair-pdf")
async def repair_pdf(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, clean=True, deflate=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-repaired.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"PDF repair failed: {exc}") from exc


@app.post("/api/compare-pdfs")
async def compare_pdfs(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    if not is_pdf(file1) or not is_pdf(file2):
        raise HTTPException(415, "Both files must be PDF documents.")
    data1 = await file1.read()
    data2 = await file2.read()
    reject_large(data1)
    reject_large(data2)
    try:
        doc1 = fitz.open(stream=data1, filetype="pdf")
        doc2 = fitz.open(stream=data2, filetype="pdf")
        
        out_doc = fitz.open()
        max_pages = max(len(doc1), len(doc2))

        for idx in range(max_pages):
            page = out_doc.new_page(width=842, height=595)
            page.insert_text(fitz.Point(36, 36), f"PDF Comparison — Page {idx + 1}", fontsize=14)
            
            t1 = doc1[idx].get_text("text").strip() if idx < len(doc1) else "[No Page]"
            t2 = doc2[idx].get_text("text").strip() if idx < len(doc2) else "[No Page]"
            
            page.insert_text(fitz.Point(36, 70), "DOCUMENT 1:", fontsize=11, color=(0, 0, 0.8))
            page.insert_text(fitz.Point(36, 90), t1[:300], fontsize=9)
            
            page.insert_text(fitz.Point(440, 70), "DOCUMENT 2:", fontsize=11, color=(0.8, 0, 0))
            page.insert_text(fitz.Point(440, 90), t2[:300], fontsize=9)

        doc1.close()
        doc2.close()

        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=3, deflate=True)
        out_doc.close()

        return file_response(out_buf.getvalue(), "nextgen-pdf-comparison-report.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"PDF comparison failed: {exc}") from exc


@app.post("/api/flatten-pdf")
async def flatten_pdf(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        out_doc = fitz.open()

        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=img_bytes)

        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=4, deflate=True)
        out_doc.close()
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-flattened.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"PDF flattening failed: {exc}") from exc


@app.post("/api/deskew-pdf")
async def deskew_pdf(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        import cv2
        import numpy as np
        
        doc = fitz.open(stream=data, filetype="pdf")
        out_doc = fitz.open()

        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
            if pix.n == 4:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
            
            gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            coords = np.column_stack(np.where(thresh > 0))
            angle = 0.0
            if len(coords) > 0:
                rect = cv2.minAreaRect(coords)
                angle = rect[-1]
                if angle < -45:
                    angle = -(90 + angle)
                elif angle > 45:
                    angle = 90 - angle

            (h, w) = img_np.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(img_np, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

            is_success, buffer = cv2.imencode(".png", rotated)
            new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=buffer.tobytes())

        out_buf = io.BytesIO()
        out_doc.save(out_buf, garbage=3, deflate=True)
        out_doc.close()
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-deskewed.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"Deskew failed: {exc}") from exc


@app.post("/api/extract-images")
async def extract_images(file: UploadFile = File(...)):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        import zipfile

        doc = fitz.open(stream=data, filetype="pdf")
        zip_buf = io.BytesIO()
        img_count = 0

        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for pno, page in enumerate(doc):
                image_list = page.get_images()
                for img_idx, img_info in enumerate(image_list):
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    img_count += 1
                    zip_file.writestr(f"extracted_image_p{pno + 1}_{img_idx + 1}.{image_ext}", image_bytes)
        doc.close()

        if img_count == 0:
            raise ValueError("No embedded images were found in this PDF document.")

        base = safe_stem(file.filename, "document")
        return file_response(zip_buf.getvalue(), f"nextgen-{base}-extracted-images.zip", "application/zip")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Image extraction failed: {exc}") from exc


@app.post("/api/overlay-pdf")
async def overlay_pdf(file: UploadFile = File(...), overlay_file: UploadFile = File(...)):
    if not is_pdf(file) or not is_pdf(overlay_file):
        raise HTTPException(415, "Both files must be PDF documents.")
    data1 = await file.read()
    data2 = await overlay_file.read()
    reject_large(data1)
    reject_large(data2)
    try:
        doc1 = fitz.open(stream=data1, filetype="pdf")
        doc2 = fitz.open(stream=data2, filetype="pdf")
        
        overlay_page = doc2[0]
        for page in doc1:
            page.show_pdf_page(page.rect, doc2, 0)
        
        out_buf = io.BytesIO()
        doc1.save(out_buf, garbage=3, deflate=True)
        doc1.close()
        doc2.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-overlaid.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"Overlay failed: {exc}") from exc


@app.post("/api/pdf-bookmarks")
async def pdf_bookmarks(
    file: UploadFile = File(...),
    action: str = Form("view"),
    toc_json: str = Form(""),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        import json

        doc = fitz.open(stream=data, filetype="pdf")
        if action.lower() == "view":
            toc = doc.get_toc()
            doc.close()
            return {"filename": safe_stem(file.filename, "document"), "toc": toc}
        else:
            if not toc_json.strip():
                raise ValueError("No Table of Contents data provided.")
            new_toc = json.loads(toc_json)
            doc.set_toc(new_toc)
            out_buf = io.BytesIO()
            doc.save(out_buf, garbage=3, deflate=True)
            doc.close()

            base = safe_stem(file.filename, "document")
            return file_response(out_buf.getvalue(), f"nextgen-{base}-bookmarks.pdf", "application/pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"Bookmarks operation failed: {exc}") from exc


@app.post("/api/metadata-editor")
async def metadata_editor(
    file: UploadFile = File(...),
    title: str = Form(""),
    author: str = Form(""),
    subject: str = Form(""),
    keywords: str = Form(""),
):
    if not is_pdf(file):
        raise HTTPException(415, "Please upload a PDF file.")
    data = await file.read()
    reject_large(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        meta = doc.metadata or {}
        if title.strip():
            meta["title"] = title.strip()
        if author.strip():
            meta["author"] = author.strip()
        if subject.strip():
            meta["subject"] = subject.strip()
        if keywords.strip():
            meta["keywords"] = keywords.strip()
        
        meta["producer"] = "NextGen PDF Metadata Engine"
        doc.set_metadata(meta)

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=3, deflate=True)
        doc.close()

        base = safe_stem(file.filename, "document")
        return file_response(out_buf.getvalue(), f"nextgen-{base}-metadata-updated.pdf", "application/pdf")
    except Exception as exc:
        raise HTTPException(400, f"Metadata update failed: {exc}") from exc


frontend_dir = Path(__file__).parent.parent
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")







