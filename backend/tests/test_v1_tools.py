import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def create_dummy_pdf(pages_count=1):
    import pymupdf as fitz
    doc = fitz.open()
    for p in range(pages_count):
        page = doc.new_page()
        page.insert_text((72, 72), f"NextGen PDF Test Document Page {p+1}", fontsize=18)
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

def create_dummy_img():
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='blue')
    out = io.BytesIO()
    img.save(out, format='JPEG')
    return out.getvalue()

def test_v1_routes_registration():
    routes = [r.path for r in app.routes]
    assert "/api/v1/compress" in routes
    assert "/api/v1/merge" in routes
    assert "/api/v1/rotate" in routes
    assert "/api/v1/protect" in routes
    assert "/api/v1/images-to-pdf" in routes
    assert "/api/v1/split" in routes

def test_v1_compress_endpoint():
    pdf = create_dummy_pdf(1)
    res = client.post("/api/v1/compress", files={"file": ("test.pdf", pdf, "application/pdf")}, data={"level": "balanced"}, headers={"X-Forwarded-For": "192.168.20.1"})
    assert res.status_code == 200
    assert len(res.content) > 0

def test_v1_merge_endpoint():
    pdf = create_dummy_pdf(1)
    res = client.post("/api/v1/merge", files=[("files", ("test1.pdf", pdf, "application/pdf")), ("files", ("test2.pdf", pdf, "application/pdf"))], headers={"X-Forwarded-For": "192.168.20.2"})
    assert res.status_code == 200
    assert len(res.content) > 0

def test_v1_rotate_endpoint():
    pdf = create_dummy_pdf(1)
    res = client.post("/api/v1/rotate", files={"file": ("test.pdf", pdf, "application/pdf")}, data={"angle": "90"}, headers={"X-Forwarded-For": "192.168.20.3"})
    assert res.status_code == 200
    assert len(res.content) > 0

def test_v1_images_to_pdf_endpoint():
    img = create_dummy_img()
    res = client.post("/api/v1/images-to-pdf", files=[("files", ("img1.jpg", img, "image/jpeg"))], headers={"X-Forwarded-For": "192.168.20.4"})
    assert res.status_code == 200
    assert len(res.content) > 0
