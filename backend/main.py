from __future__ import annotations

import io
import os
import re
import zipfile
from pathlib import Path

import pymupdf as fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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

