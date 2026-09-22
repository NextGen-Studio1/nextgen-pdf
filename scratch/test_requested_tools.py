import sys
import os
import io
from PIL import Image

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch
from app.services.rate_limit_service import RateLimitService

client = TestClient(app)

# Helper valid assets
dummy_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 2/Kids[3 0 R 4 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj 4 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000115 00000 n\n0000000185 00000 n\ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n255\n%%EOF"

img = Image.new('RGB', (100, 100), color='red')
img_buf = io.BytesIO()
img.save(img_buf, format='PNG')
valid_png = img_buf.getvalue()

docx_dummy = b"PK\x03\x04\x14\x00\x00\x00\x08\x00"  # Dummy zip/docx header

tools_test_cases = [
    ("Add Image", "/api/v1/add-image", {"file": ("test.pdf", dummy_pdf, "application/pdf"), "image_file": ("stamp.png", valid_png, "image/png")}, {"position": "bottom-right", "width": "120", "height": "120", "pages": "all"}),
    ("Organize PDF", "/api/v1/organize", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"order": "2,1"}),
    ("Merge PDF", "/api/v1/merge", {"files": [("t1.pdf", dummy_pdf, "application/pdf"), ("t2.pdf", dummy_pdf, "application/pdf")]}, {}),
    ("Compress PDF", "/api/v1/compress", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"level": "balanced"}),
    ("Split PDF", "/api/v1/split", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"mode": "every", "ranges": ""}),
    ("Rotate PDF", "/api/v1/rotate", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"angle": "90", "pages": "all"}),
    ("JPG to PDF", "/api/v1/jpg-to-pdf", {"files": [("test.png", valid_png, "image/png")]}, {"layout": "portrait", "fit": "fit"}),
    ("PDF to JPG", "/api/v1/pdf-to-jpg", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"format": "jpg", "ranges": ""}),
    ("PDF to Word", "/api/v1/pdf-to-word", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("Word to PDF", "/api/v1/word-to-pdf", {"file": ("test.docx", docx_dummy, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}, {}),
    ("OCR PDF", "/api/v1/ocr-pdf", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"language": "eng"}),
    ("AI Summarize", "/api/v1/ai-summarize", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"summary_type": "executive"}),
    ("Chat PDF", "/api/v1/chat-pdf", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"question": "What is in this document?"})
]

print("=== RETESTING ALL 13 SPECIFIED TOOLS ===")
results = []
with patch.object(RateLimitService, 'check_and_increment_quota', return_value=None):
    for name, ep, files, data in tools_test_cases:
        try:
            res = client.post(ep, files=files, data=data)
            status = res.status_code
            content_type = res.headers.get("content-type", "")
            out_len = len(res.content)
            status_str = "PASS" if status == 200 and out_len > 0 else f"FAIL ({status})"
            results.append((name, ep, status, out_len, content_type, status_str))
            print(f"{name:<15} | Endpoint: {ep:<25} | Status: {status} | Size: {out_len:>6} bytes | {status_str}")
        except Exception as e:
            results.append((name, ep, 500, 0, "", f"FAIL (EXC: {e})"))
            print(f"{name:<15} | Endpoint: {ep:<25} | FAIL: {e}")

all_pass = all(r[5] == "PASS" for r in results)
print(f"\nAll 13 specified tools test result: {'ALL PASS' if all_pass else 'SOME FAILED'}")
