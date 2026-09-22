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
    page.insert_text(fitz.Point(100, 100), "Hello NextGen PDF", fontsize=18)
    page.insert_text(fitz.Point(100, 150), "Important note inside document", fontsize=12)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def create_sample_image() -> bytes:
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def test_editing_tools():
    client = TestClient(app)
    pdf_bytes = create_sample_pdf()
    img_bytes = create_sample_image()

    print("Testing /api/edit-pdf...")
    res = client.post(
        "/api/edit-pdf",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"text": "APPROVED", "fontsize": "18", "color": "red", "position": "top-right", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    doc = fitz.open(stream=res.content, filetype="pdf")
    text = doc[0].get_text()
    assert "APPROVED" in text
    doc.close()
    print("  [OK] /api/edit-pdf OK (Text inserted into PDF)")

    print("Testing /api/add-image...")
    res = client.post(
        "/api/add-image",
        files={
            "file": ("test.pdf", pdf_bytes, "application/pdf"),
            "image_file": ("stamp.png", img_bytes, "image/png")
        },
        data={"position": "bottom-right", "width": "100", "height": "100", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    doc = fitz.open(stream=res.content, filetype="pdf")
    img_list = doc[0].get_images()
    assert len(img_list) > 0
    doc.close()
    print("  [OK] /api/add-image OK (Image inserted onto page)")

    print("Testing /api/add-links...")
    res = client.post(
        "/api/add-links",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"url": "https://example.com", "target_text": "NextGen", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    doc = fitz.open(stream=res.content, filetype="pdf")
    links = list(doc[0].links())
    assert len(links) > 0
    assert links[0]["uri"] == "https://example.com"
    doc.close()
    print("  [OK] /api/add-links OK (URI Hyperlink embedded on target text)")

    print("Testing /api/highlight-pdf...")
    res = client.post(
        "/api/highlight-pdf",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"text": "Important", "color": "yellow", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    doc = fitz.open(stream=res.content, filetype="pdf")
    annots = list(doc[0].annots())
    assert len(annots) > 0
    doc.close()
    print("  [OK] /api/highlight-pdf OK (Highlight annotation added)")

    print("Testing /api/annotate-pdf...")
    res = client.post(
        "/api/annotate-pdf",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"comment": "Review required before signature", "position": "top-left", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    doc = fitz.open(stream=res.content, filetype="pdf")
    annots = list(doc[0].annots())
    assert len(annots) > 0
    doc.close()
    print("  [OK] /api/annotate-pdf OK (Sticky comment annotation added)")

    print("Testing /api/resize-pages...")
    res = client.post(
        "/api/resize-pages",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"paper_size": "a4", "orientation": "landscape", "pages": "all"}
    )
    assert res.status_code == 200, res.text
    doc = fitz.open(stream=res.content, filetype="pdf")
    rect = doc[0].rect
    # A4 landscape is 842 x 595
    assert int(rect.width) == 842 and int(rect.height) == 595
    doc.close()
    print("  [OK] /api/resize-pages OK (Pages resized to A4 landscape)")

    print("\nALL BATCH 4 EDITING & GEOMETRY TOOL TESTS PASSED 100%!")

if __name__ == "__main__":
    test_editing_tools()
