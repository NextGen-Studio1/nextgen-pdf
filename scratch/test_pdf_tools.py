import io
import sys
from pathlib import Path
import pymupdf as fitz
from fastapi.testclient import TestClient

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from main import app

def create_sample_pdf(page_count: int = 5) -> bytes:
    doc = fitz.open()
    for i in range(1, page_count + 1):
        page = doc.new_page(width=595, height=842)
        page.insert_text(fitz.Point(100, 100), f"Sample Document - Page {i}", fontsize=24)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def test_all_tools():
    client = TestClient(app)
    sample_pdf = create_sample_pdf(5)
    
    print("Testing /api/health...")
    res = client.get("/api/health")
    assert res.status_code == 200, res.text
    print("  [OK] /api/health OK")

    print("Testing /api/watermark...")
    res = client.post(
        "/api/watermark",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        data={"text": "TEST WATERMARK", "position": "diagonal", "color": "red", "opacity": "0.4", "fontsize": "48"}
    )
    assert res.status_code == 200, res.text
    out_doc = fitz.open(stream=res.content, filetype="pdf")
    assert out_doc.page_count == 5
    out_doc.close()
    print("  [OK] /api/watermark OK")

    print("Testing /api/organize...")
    res = client.post(
        "/api/organize",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        data={"order": "3,1,2,5,4"}
    )
    assert res.status_code == 200, res.text
    out_doc = fitz.open(stream=res.content, filetype="pdf")
    assert out_doc.page_count == 5
    page1_text = out_doc[0].get_text()
    assert "Page 3" in page1_text
    out_doc.close()
    print("  [OK] /api/organize OK (reordered 3,1,2,5,4)")

    print("Testing /api/delete-pages...")
    res = client.post(
        "/api/delete-pages",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        data={"pages": "2, 4"}
    )
    assert res.status_code == 200, res.text
    out_doc = fitz.open(stream=res.content, filetype="pdf")
    assert out_doc.page_count == 3
    out_doc.close()
    print("  [OK] /api/delete-pages OK (deleted pages 2,4 -> 3 pages remaining)")

    print("Testing /api/extract-pages...")
    res = client.post(
        "/api/extract-pages",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        data={"pages": "1, 3-4"}
    )
    assert res.status_code == 200, res.text
    out_doc = fitz.open(stream=res.content, filetype="pdf")
    assert out_doc.page_count == 3
    out_doc.close()
    print("  [OK] /api/extract-pages OK (extracted 1, 3-4 -> 3 pages)")

    print("Testing /api/rotate...")
    res = client.post(
        "/api/rotate",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        data={"angle": "90", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    out_doc = fitz.open(stream=res.content, filetype="pdf")
    assert out_doc[0].rotation == 90
    out_doc.close()
    print("  [OK] /api/rotate OK (rotated 90 deg)")

    print("Testing /api/page-numbers...")
    res = client.post(
        "/api/page-numbers",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        data={"position": "bottom-center", "format": "Page {page} of {total}", "start": "1", "fontsize": "10", "margin": "36", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    out_doc = fitz.open(stream=res.content, filetype="pdf")
    assert out_doc.page_count == 5
    page_text = out_doc[0].get_text()
    assert "Page 1 of 5" in page_text
    out_doc.close()
    print("  [OK] /api/page-numbers OK (Page 1 of 5 added)")

    print("Testing /api/crop...")
    res = client.post(
        "/api/crop",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")},
        data={"margin": "36", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    out_doc = fitz.open(stream=res.content, filetype="pdf")
    assert out_doc.page_count == 5
    rect = out_doc[0].cropbox
    assert rect.width == 595 - 72
    assert rect.height == 842 - 72
    out_doc.close()
    print("  [OK] /api/crop OK (cropped 36pt margins)")

    print("\nALL PDF TOOL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all_tools()
