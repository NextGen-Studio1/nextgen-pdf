import io
import sys
from pathlib import Path
import pymupdf as fitz
from fastapi.testclient import TestClient
from PIL import Image

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from main import app

def create_sample_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(100, 100), "NextGen PDF Advanced Document Engine Test", fontsize=16)
    page.insert_text(fitz.Point(100, 140), "This report contains statistical metrics and budget details.", fontsize=12)
    
    # Add an embedded image
    img = Image.new("RGB", (80, 80), color="red")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    page.insert_image(fitz.Rect(100, 200, 180, 280), stream=img_buf.getvalue())

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def test_advanced_tools():
    client = TestClient(app)
    pdf_bytes = create_sample_pdf()

    print("Testing /api/ocr-pdf...")
    res = client.post("/api/ocr-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    print("  [OK] /api/ocr-pdf OK")

    print("Testing /api/scanned-pdf-to-text...")
    res = client.post("/api/scanned-pdf-to-text", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    assert "NextGen PDF" in res.text
    print("  [OK] /api/scanned-pdf-to-text OK")

    print("Testing /api/ai-summarize...")
    res = client.post("/api/ai-summarize", files={"file": ("test.pdf", pdf_bytes, "application/pdf")}, data={"summary_type": "executive"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "word_count" in data
    assert "executive_summary" in data
    print("  [OK] /api/ai-summarize OK")

    print("Testing /api/chat-pdf...")
    res = client.post("/api/chat-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")}, data={"question": "What is in the report?"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "answer" in data
    print("  [OK] /api/chat-pdf OK")

    print("Testing /api/translate-pdf...")
    res = client.post("/api/translate-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")}, data={"target_lang": "es"})
    assert res.status_code == 200, res.text
    print("  [OK] /api/translate-pdf OK")

    print("Testing /api/pdf-to-markdown...")
    res = client.post("/api/pdf-to-markdown", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    assert "#" in res.text
    print("  [OK] /api/pdf-to-markdown OK")

    print("Testing /api/repair-pdf...")
    res = client.post("/api/repair-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    print("  [OK] /api/repair-pdf OK")

    print("Testing /api/compare-pdfs...")
    res = client.post("/api/compare-pdfs", files={"file1": ("doc1.pdf", pdf_bytes, "application/pdf"), "file2": ("doc2.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    print("  [OK] /api/compare-pdfs OK")

    print("Testing /api/flatten-pdf...")
    res = client.post("/api/flatten-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    print("  [OK] /api/flatten-pdf OK")

    print("Testing /api/deskew-pdf...")
    res = client.post("/api/deskew-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    print("  [OK] /api/deskew-pdf OK")

    print("Testing /api/extract-images...")
    res = client.post("/api/extract-images", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    assert len(res.content) > 100
    print("  [OK] /api/extract-images OK")

    print("Testing /api/overlay-pdf...")
    res = client.post("/api/overlay-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf"), "overlay_file": ("bg.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    print("  [OK] /api/overlay-pdf OK")

    print("Testing /api/pdf-bookmarks...")
    res = client.post("/api/pdf-bookmarks", files={"file": ("test.pdf", pdf_bytes, "application/pdf")}, data={"action": "view"})
    assert res.status_code == 200, res.text
    print("  [OK] /api/pdf-bookmarks OK")

    print("Testing /api/metadata-editor...")
    res = client.post("/api/metadata-editor", files={"file": ("test.pdf", pdf_bytes, "application/pdf")}, data={"title": "New Title", "author": "New Author"})
    assert res.status_code == 200, res.text
    doc = fitz.open(stream=res.content, filetype="pdf")
    assert doc.metadata["title"] == "New Title"
    doc.close()
    print("  [OK] /api/metadata-editor OK")

    print("\nALL ADVANCED TOOLS TESTS PASSED 100%!")

if __name__ == "__main__":
    test_advanced_tools()
