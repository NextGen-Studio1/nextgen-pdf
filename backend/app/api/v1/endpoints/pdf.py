import os
from fastapi import APIRouter, File, UploadFile, Form, Depends, Request
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import FileRecord
from app.utils.file_validation import (
    read_file_bounded,
    validate_file_size,
    validate_pdf_magic_bytes,
    validate_pdf_structure,
    validate_image_magic_bytes
)
from app.utils.storage import save_result_buffer
from app.services.pdf_service import PDFService
from app.services.job_service import JobService
from app.services.rate_limit_service import RateLimitService
from app.core.dependencies import get_optional_user

router = APIRouter()

def get_client_identity(request: Request, current_user: dict | None) -> tuple[str, str]:
    if current_user and "uid" in current_user:
        is_anonymous = current_user.get("firebase", {}).get("sign_in_provider") == "anonymous"
        return current_user["uid"], "guest" if is_anonymous else "free"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "unknown_client"
    return client_ip, "guest"

def record_file_in_db(db: Session, file_id: str, filename: str, file_path: str, file_size: int, owner_id: str | None, mime_type: str = "application/pdf"):
    if owner_id:
        try:
            f_rec = FileRecord(
                id=file_id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                owner_id=owner_id
            )
            db.add(f_rec)
            db.commit()
        except Exception:
            db.rollback()

# --- 1. COMPRESS ---
@router.post("/compress")
async def compress_pdf(
    request: Request,
    file: UploadFile = File(...),
    level: str = Form("balanced"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "compress", user_id=user_id)

    try:
        compressed = PDFService.compress_pdf(content, level=level)
        out_name = f"compressed_{file.filename}"
        result_id, fpath = save_result_buffer(compressed, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(compressed), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=compressed, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 2. MERGE ---
@router.post("/merge")
async def merge_pdfs(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    pdf_contents = []
    total_bytes = 0
    for f in files:
        c = await read_file_bounded(f)
        validate_pdf_magic_bytes(c)
        pdf_contents.append(c)
        total_bytes += len(c)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, total_bytes)
    job = JobService.create_job(db, "merge", user_id=user_id)

    try:
        merged = PDFService.merge_pdfs(pdf_contents)
        out_name = "merged_document.pdf"
        result_id, fpath = save_result_buffer(merged, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(merged), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=merged, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 3. SPLIT ---
@router.post("/split")
async def split_pdf(
    request: Request,
    file: UploadFile = File(...),
    mode: str = Form("every"),
    ranges: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "split", user_id=user_id)

    try:
        out_bytes, mime, out_name = PDFService.split_pdf(content, mode=mode, ranges=ranges)
        result_id, fpath = save_result_buffer(out_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(out_bytes), user_id, mime_type=mime)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=out_bytes, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 4. IMAGES TO PDF (jpg-to-pdf / images-to-pdf) ---
@router.post("/images-to-pdf")
@router.post("/jpg-to-pdf")
async def images_to_pdf(
    request: Request,
    files: list[UploadFile] = File(...),
    layout: str = Form("portrait"),
    fit: str = Form("fit"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    img_contents = []
    total_bytes = 0
    for f in files:
        c = await read_file_bounded(f)
        validate_image_magic_bytes(c)
        img_contents.append(c)
        total_bytes += len(c)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, total_bytes)
    job = JobService.create_job(db, "images-to-pdf", user_id=user_id)

    try:
        converted = PDFService.images_to_pdf(img_contents, layout=layout, fit=fit)
        out_name = "images_converted.pdf"
        result_id, fpath = save_result_buffer(converted, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(converted), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=converted, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 5. PDF TO IMAGES (pdf-to-images / pdf-to-jpg) ---
@router.post("/pdf-to-images")
@router.post("/pdf-to-jpg")
async def pdf_to_images(
    request: Request,
    file: UploadFile = File(...),
    format: str = Form("jpg"),
    ranges: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-images", user_id=user_id)

    try:
        out_bytes, mime, out_name = PDFService.pdf_to_images(content, fmt=format, ranges=ranges)
        result_id, fpath = save_result_buffer(out_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(out_bytes), user_id, mime_type=mime)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=out_bytes, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 6. WATERMARK ---
@router.post("/watermark")
async def watermark_pdf(
    request: Request,
    file: UploadFile = File(...),
    text: str = Form("CONFIDENTIAL"),
    position: str = Form("diagonal"),
    color: str = Form("red"),
    opacity: float = Form(0.35),
    fontsize: int = Form(48),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "watermark", user_id=user_id)

    try:
        watermarked = PDFService.watermark_pdf(content, text=text, position=position, color=color, opacity=opacity, fontsize=fontsize)
        out_name = f"watermarked_{file.filename}"
        result_id, fpath = save_result_buffer(watermarked, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(watermarked), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=watermarked, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 7. ORGANIZE ---
@router.post("/organize")
async def organize_pdf(
    request: Request,
    file: UploadFile = File(...),
    order: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "organize", user_id=user_id)

    try:
        organized = PDFService.organize_pdf(content, order=order)
        out_name = f"organized_{file.filename}"
        result_id, fpath = save_result_buffer(organized, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(organized), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=organized, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 8. DELETE PAGES ---
@router.post("/delete-pages")
async def delete_pdf_pages(
    request: Request,
    file: UploadFile = File(...),
    pages: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "delete-pages", user_id=user_id)

    try:
        modified = PDFService.delete_pdf_pages(content, pages=pages)
        out_name = f"deleted_pages_{file.filename}"
        result_id, fpath = save_result_buffer(modified, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(modified), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=modified, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 9. EXTRACT PAGES ---
@router.post("/extract-pages")
async def extract_pdf_pages(
    request: Request,
    file: UploadFile = File(...),
    pages: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "extract-pages", user_id=user_id)

    try:
        extracted = PDFService.extract_pdf_pages(content, pages=pages)
        out_name = f"extracted_{file.filename}"
        result_id, fpath = save_result_buffer(extracted, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(extracted), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=extracted, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 10. ROTATE ---
@router.post("/rotate")
async def rotate_pdf(
    request: Request,
    file: UploadFile = File(...),
    angle: int = Form(90),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "rotate", user_id=user_id)

    try:
        rotated = PDFService.rotate_pdf(content, angle=angle, pages=pages)
        out_name = f"rotated_{file.filename}"
        result_id, fpath = save_result_buffer(rotated, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(rotated), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=rotated, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 11. PAGE NUMBERS ---
@router.post("/page-numbers")
async def add_page_numbers(
    request: Request,
    file: UploadFile = File(...),
    position: str = Form("bottom-center"),
    format: str = Form("Page {page} of {total}"),
    start: int = Form(1),
    fontsize: int = Form(10),
    margin: int = Form(36),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "page-numbers", user_id=user_id)

    try:
        numbered = PDFService.add_page_numbers(content, position=position, format_str=format, start=start, fontsize=fontsize, margin=margin, pages=pages)
        out_name = f"numbered_{file.filename}"
        result_id, fpath = save_result_buffer(numbered, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(numbered), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=numbered, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 12. CROP ---
@router.post("/crop")
async def crop_pdf(
    request: Request,
    file: UploadFile = File(...),
    margin: int = Form(36),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "crop", user_id=user_id)

    try:
        cropped = PDFService.crop_pdf(content, margin=margin, pages=pages)
        out_name = f"cropped_{file.filename}"
        result_id, fpath = save_result_buffer(cropped, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(cropped), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=cropped, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 13. PDF TO WORD ---
@router.post("/pdf-to-word")
async def pdf_to_word(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-word", user_id=user_id)

    try:
        docx_bytes = PDFService.pdf_to_word(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.docx"
        result_id, fpath = save_result_buffer(docx_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(docx_bytes), user_id, mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        JobService.complete_job(db, job.id, result_id)
        return Response(content=docx_bytes, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 14. PDF TO EXCEL ---
@router.post("/pdf-to-excel")
async def pdf_to_excel(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-excel", user_id=user_id)

    try:
        xlsx_bytes = PDFService.pdf_to_excel(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.xlsx"
        result_id, fpath = save_result_buffer(xlsx_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(xlsx_bytes), user_id, mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        JobService.complete_job(db, job.id, result_id)
        return Response(content=xlsx_bytes, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 15. PDF TO PPTX ---
@router.post("/pdf-to-pptx")
async def pdf_to_pptx(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-pptx", user_id=user_id)

    try:
        pptx_bytes = PDFService.pdf_to_pptx(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.pptx"
        result_id, fpath = save_result_buffer(pptx_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(pptx_bytes), user_id, mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        JobService.complete_job(db, job.id, result_id)
        return Response(content=pptx_bytes, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 16. PDF TO PNG ---
@router.post("/pdf-to-png")
async def pdf_to_png(
    request: Request,
    file: UploadFile = File(...),
    ranges: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-png", user_id=user_id)

    try:
        out_bytes, mime, out_name = PDFService.pdf_to_png(content, ranges=ranges)
        result_id, fpath = save_result_buffer(out_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(out_bytes), user_id, mime_type=mime)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=out_bytes, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 17. PDF TO TXT ---
@router.post("/pdf-to-txt")
async def pdf_to_txt(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-txt", user_id=user_id)

    try:
        txt_bytes = PDFService.pdf_to_txt(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.txt"
        result_id, fpath = save_result_buffer(txt_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(txt_bytes), user_id, mime_type="text/plain")
        JobService.complete_job(db, job.id, result_id)
        return Response(content=txt_bytes, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 18. PDF TO HTML ---
@router.post("/pdf-to-html")
async def pdf_to_html(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-html", user_id=user_id)

    try:
        html_bytes = PDFService.pdf_to_html(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.html"
        result_id, fpath = save_result_buffer(html_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(html_bytes), user_id, mime_type="text/html")
        JobService.complete_job(db, job.id, result_id)
        return Response(content=html_bytes, media_type="text/html; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 19. PDF TO PDF/A ---
@router.post("/pdf-to-pdfa")
async def pdf_to_pdfa(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-pdfa", user_id=user_id)

    try:
        pdfa_bytes = PDFService.pdf_to_pdfa(content)
        out_name = f"pdfa_{file.filename}"
        result_id, fpath = save_result_buffer(pdfa_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(pdfa_bytes), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=pdfa_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 20. WORD TO PDF ---
@router.post("/word-to-pdf")
async def word_to_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "word-to-pdf", user_id=user_id)

    try:
        pdf_bytes = PDFService.word_to_pdf(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.pdf"
        result_id, fpath = save_result_buffer(pdf_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(pdf_bytes), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 21. EXCEL TO PDF ---
@router.post("/excel-to-pdf")
async def excel_to_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "excel-to-pdf", user_id=user_id)

    try:
        pdf_bytes = PDFService.excel_to_pdf(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.pdf"
        result_id, fpath = save_result_buffer(pdf_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(pdf_bytes), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 22. PPTX TO PDF ---
@router.post("/pptx-to-pdf")
async def pptx_to_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pptx-to-pdf", user_id=user_id)

    try:
        pdf_bytes = PDFService.pptx_to_pdf(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.pdf"
        result_id, fpath = save_result_buffer(pdf_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(pdf_bytes), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 23. HTML TO PDF ---
@router.post("/html-to-pdf")
async def html_to_pdf(
    request: Request,
    file: UploadFile = File(None),
    html: str = Form(None),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file) if file else None
    input_size = len(content) if content else len(html.encode()) if html else 100
    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, input_size)
    job = JobService.create_job(db, "html-to-pdf", user_id=user_id)

    try:
        pdf_bytes = PDFService.html_to_pdf(content, html_str=html)
        out_name = "converted_html.pdf"
        result_id, fpath = save_result_buffer(pdf_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(pdf_bytes), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 24. PROTECT (protect / protect-pdf) ---
@router.post("/protect")
@router.post("/protect-pdf")
async def protect_pdf(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "protect", user_id=user_id)

    try:
        protected = PDFService.protect_pdf(content, password)
        out_name = f"protected_{file.filename}"
        result_id, fpath = save_result_buffer(protected, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(protected), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=protected, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 25. UNLOCK ---
@router.post("/unlock-pdf")
async def unlock_pdf(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "unlock-pdf", user_id=user_id)

    try:
        unlocked = PDFService.unlock_pdf(content, password=password)
        out_name = f"unlocked_{file.filename}"
        result_id, fpath = save_result_buffer(unlocked, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(unlocked), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=unlocked, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 26. ENCRYPT ---
@router.post("/encrypt-pdf")
async def encrypt_pdf(
    request: Request,
    file: UploadFile = File(...),
    user_password: str = Form(""),
    owner_password: str = Form(""),
    allow_print: bool = Form(True),
    allow_copy: bool = Form(True),
    allow_edit: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "encrypt-pdf", user_id=user_id)

    try:
        encrypted = PDFService.encrypt_pdf(content, user_password=user_password, owner_password=owner_password, allow_print=allow_print, allow_copy=allow_copy, allow_edit=allow_edit)
        out_name = f"encrypted_{file.filename}"
        result_id, fpath = save_result_buffer(encrypted, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(encrypted), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=encrypted, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 27. REDACT ---
@router.post("/redact-pdf")
async def redact_pdf(
    request: Request,
    file: UploadFile = File(...),
    text: str = Form(...),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "redact-pdf", user_id=user_id)

    try:
        redacted = PDFService.redact_pdf(content, text=text, pages=pages)
        out_name = f"redacted_{file.filename}"
        result_id, fpath = save_result_buffer(redacted, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(redacted), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=redacted, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 28. REMOVE METADATA ---
@router.post("/remove-metadata")
async def remove_metadata(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "remove-metadata", user_id=user_id)

    try:
        cleaned = PDFService.remove_metadata(content)
        out_name = f"clean_meta_{file.filename}"
        result_id, fpath = save_result_buffer(cleaned, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(cleaned), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=cleaned, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 29. EDIT PDF ---
@router.post("/edit-pdf")
async def edit_pdf(
    request: Request,
    file: UploadFile = File(...),
    text: str = Form(...),
    fontsize: int = Form(14),
    color: str = Form("black"),
    position: str = Form("top-left"),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "edit-pdf", user_id=user_id)

    try:
        edited = PDFService.edit_pdf(content, text=text, fontsize=fontsize, color=color, position=position, pages=pages)
        out_name = f"edited_{file.filename}"
        result_id, fpath = save_result_buffer(edited, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(edited), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=edited, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 30. ADD IMAGE ---
@router.post("/add-image")
async def add_image_to_pdf(
    request: Request,
    file: UploadFile = File(...),
    image_file: UploadFile = File(...),
    position: str = Form("bottom-right"),
    width: int = Form(120),
    height: int = Form(120),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    img_content = await read_file_bounded(image_file)
    validate_image_magic_bytes(img_content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content) + len(img_content))
    job = JobService.create_job(db, "add-image", user_id=user_id)

    try:
        stamped = PDFService.add_image_to_pdf(content, img_content, position=position, width=width, height=height, pages=pages)
        out_name = f"stamped_{file.filename}"
        result_id, fpath = save_result_buffer(stamped, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(stamped), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=stamped, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 31. ADD LINKS ---
@router.post("/add-links")
async def add_links(
    request: Request,
    file: UploadFile = File(...),
    url: str = Form(...),
    target_text: str = Form(""),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "add-links", user_id=user_id)

    try:
        linked = PDFService.add_links(content, url=url, target_text=target_text, pages=pages)
        out_name = f"linked_{file.filename}"
        result_id, fpath = save_result_buffer(linked, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(linked), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=linked, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 32. HIGHLIGHT ---
@router.post("/highlight-pdf")
async def highlight_pdf(
    request: Request,
    file: UploadFile = File(...),
    text: str = Form(...),
    color: str = Form("yellow"),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "highlight-pdf", user_id=user_id)

    try:
        highlighted = PDFService.highlight_pdf(content, text=text, color=color, pages=pages)
        out_name = f"highlighted_{file.filename}"
        result_id, fpath = save_result_buffer(highlighted, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(highlighted), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=highlighted, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 33. ANNOTATE ---
@router.post("/annotate-pdf")
async def annotate_pdf(
    request: Request,
    file: UploadFile = File(...),
    comment: str = Form(...),
    position: str = Form("top-left"),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "annotate-pdf", user_id=user_id)

    try:
        annotated = PDFService.annotate_pdf(content, comment=comment, position=position, pages=pages)
        out_name = f"annotated_{file.filename}"
        result_id, fpath = save_result_buffer(annotated, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(annotated), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=annotated, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 34. RESIZE PAGES ---
@router.post("/resize-pages")
async def resize_pages(
    request: Request,
    file: UploadFile = File(...),
    paper_size: str = Form("a4"),
    orientation: str = Form("portrait"),
    pages: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "resize-pages", user_id=user_id)

    try:
        resized = PDFService.resize_pages(content, paper_size=paper_size, orientation=orientation, pages=pages)
        out_name = f"resized_{file.filename}"
        result_id, fpath = save_result_buffer(resized, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(resized), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=resized, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 35. OCR ---
@router.post("/ocr-pdf")
async def ocr_pdf(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("eng"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "ocr-pdf", user_id=user_id)

    try:
        ocr_bytes = PDFService.ocr_pdf(content, language=language)
        out_name = f"ocr_{file.filename}"
        result_id, fpath = save_result_buffer(ocr_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(ocr_bytes), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=ocr_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 36. SCANNED PDF TO TEXT ---
@router.post("/scanned-pdf-to-text")
async def scanned_pdf_to_text(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "scanned-pdf-to-text", user_id=user_id)

    try:
        txt_bytes = PDFService.scanned_pdf_to_text(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.txt"
        result_id, fpath = save_result_buffer(txt_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(txt_bytes), user_id, mime_type="text/plain")
        JobService.complete_job(db, job.id, result_id)
        return Response(content=txt_bytes, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 37. AI SUMMARIZE ---
@router.post("/ai-summarize")
async def ai_summarize(
    request: Request,
    file: UploadFile = File(...),
    summary_type: str = Form("executive"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "ai-summarize", user_id=user_id)

    try:
        summary_dict = PDFService.ai_summarize(content, summary_type=summary_type)
        JobService.complete_job(db, job.id, "ai_summary_result")
        return JSONResponse(content=summary_dict)
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 38. CHAT PDF ---
@router.post("/chat-pdf")
async def chat_pdf(
    request: Request,
    file: UploadFile = File(...),
    question: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "chat-pdf", user_id=user_id)

    try:
        chat_dict = PDFService.chat_pdf(content, question=question)
        JobService.complete_job(db, job.id, "chat_pdf_result")
        return JSONResponse(content=chat_dict)
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 39. TRANSLATE PDF ---
@router.post("/translate-pdf")
async def translate_pdf(
    request: Request,
    file: UploadFile = File(...),
    target_lang: str = Form("es"),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "translate-pdf", user_id=user_id)

    try:
        trans_dict = PDFService.translate_pdf(content, target_lang=target_lang)
        JobService.complete_job(db, job.id, "translate_pdf_result")
        return JSONResponse(content=trans_dict)
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 40. PDF TO MARKDOWN ---
@router.post("/pdf-to-markdown")
async def pdf_to_markdown(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-to-markdown", user_id=user_id)

    try:
        md_bytes = PDFService.pdf_to_markdown(content)
        out_name = f"{os.path.splitext(file.filename)[0]}.md"
        result_id, fpath = save_result_buffer(md_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(md_bytes), user_id, mime_type="text/markdown")
        JobService.complete_job(db, job.id, result_id)
        return Response(content=md_bytes, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 41. REPAIR PDF ---
@router.post("/repair-pdf")
async def repair_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "repair-pdf", user_id=user_id)

    try:
        repaired = PDFService.repair_pdf(content)
        out_name = f"repaired_{file.filename}"
        result_id, fpath = save_result_buffer(repaired, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(repaired), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=repaired, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 42. COMPARE PDFS ---
@router.post("/compare-pdfs")
async def compare_pdfs(
    request: Request,
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    c1 = await read_file_bounded(file1)
    c2 = await read_file_bounded(file2)
    validate_pdf_magic_bytes(c1)
    validate_pdf_magic_bytes(c2)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(c1) + len(c2))
    job = JobService.create_job(db, "compare-pdfs", user_id=user_id)

    try:
        compared = PDFService.compare_pdfs(c1, c2)
        out_name = "comparison_result.pdf"
        result_id, fpath = save_result_buffer(compared, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(compared), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=compared, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 43. FLATTEN PDF ---
@router.post("/flatten-pdf")
async def flatten_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "flatten-pdf", user_id=user_id)

    try:
        flattened = PDFService.flatten_pdf(content)
        out_name = f"flattened_{file.filename}"
        result_id, fpath = save_result_buffer(flattened, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(flattened), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=flattened, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 44. DESKEW PDF ---
@router.post("/deskew-pdf")
async def deskew_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "deskew-pdf", user_id=user_id)

    try:
        deskewed = PDFService.deskew_pdf(content)
        out_name = f"deskewed_{file.filename}"
        result_id, fpath = save_result_buffer(deskewed, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(deskewed), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=deskewed, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 45. EXTRACT IMAGES ---
@router.post("/extract-images")
async def extract_images(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "extract-images", user_id=user_id)

    try:
        zip_bytes = PDFService.extract_images(content)
        out_name = "extracted_images.zip"
        result_id, fpath = save_result_buffer(zip_bytes, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(zip_bytes), user_id, mime_type="application/zip")
        JobService.complete_job(db, job.id, result_id)
        return Response(content=zip_bytes, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 46. OVERLAY PDF ---
@router.post("/overlay-pdf")
async def overlay_pdf(
    request: Request,
    file: UploadFile = File(...),
    overlay_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    c1 = await read_file_bounded(file)
    c2 = await read_file_bounded(overlay_file)
    validate_pdf_magic_bytes(c1)
    validate_pdf_magic_bytes(c2)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(c1) + len(c2))
    job = JobService.create_job(db, "overlay-pdf", user_id=user_id)

    try:
        overlaid = PDFService.overlay_pdf(c1, c2)
        out_name = f"overlaid_{file.filename}"
        result_id, fpath = save_result_buffer(overlaid, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(overlaid), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=overlaid, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 47. PDF BOOKMARKS ---
@router.post("/pdf-bookmarks")
async def pdf_bookmarks(
    request: Request,
    file: UploadFile = File(...),
    action: str = Form("view"),
    toc_json: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "pdf-bookmarks", user_id=user_id)

    try:
        result = PDFService.pdf_bookmarks(content, action=action, toc_json=toc_json)
        if isinstance(result, dict):
            JobService.complete_job(db, job.id, "pdf_bookmarks_result")
            return JSONResponse(content=result)

        out_name = f"bookmarked_{file.filename}"
        result_id, fpath = save_result_buffer(result, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(result), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=result, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e

# --- 48. METADATA EDITOR ---
@router.post("/metadata-editor")
async def metadata_editor(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    author: str = Form(""),
    subject: str = Form(""),
    keywords: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_user)
):
    identifier, plan_tier = get_client_identity(request, current_user)
    user_id = current_user.get("uid") if current_user else None

    content = await read_file_bounded(file)
    validate_pdf_magic_bytes(content)

    RateLimitService.check_and_increment_quota(db, identifier, plan_tier, len(content))
    job = JobService.create_job(db, "metadata-editor", user_id=user_id)

    try:
        updated = PDFService.metadata_editor(content, title=title, author=author, subject=subject, keywords=keywords)
        out_name = f"metadata_{file.filename}"
        result_id, fpath = save_result_buffer(updated, out_name)
        record_file_in_db(db, result_id, out_name, str(fpath), len(updated), user_id)
        JobService.complete_job(db, job.id, result_id)
        return Response(content=updated, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{out_name}"'})
    except Exception as e:
        JobService.fail_job(db, job.id, str(e))
        raise e
