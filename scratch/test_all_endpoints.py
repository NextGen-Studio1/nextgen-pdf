import os
import sys
import unittest
from unittest.mock import patch

root_dir = os.getcwd()
sys.path.insert(0, os.path.join(root_dir, "backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.services.rate_limit_service import RateLimitService

client = TestClient(app)

# Dummy PDF bytes
dummy_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xdc\xcc\x59\xe7\x00\x00\x00\x00IEND\xaeB`\x82"

endpoints_to_test = [
    ("/api/v1/compress", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"compression_level": "recommended"}),
    ("/api/v1/merge", {"files": [("test1.pdf", dummy_pdf, "application/pdf"), ("test2.pdf", dummy_pdf, "application/pdf")]}, {}),
    ("/api/v1/split", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"split_mode": "all"}),
    ("/api/v1/rotate", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"angle": "90"}),
    ("/api/v1/images-to-pdf", {"files": [("test.png", dummy_img, "image/png")]}, {}),
    ("/api/v1/jpg-to-pdf", {"files": [("test.png", dummy_img, "image/png")]}, {}),
    ("/api/v1/extract-pages", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"pages": "1"}),
    ("/api/v1/delete-pages", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"pages": "1"}),
    ("/api/v1/metadata-editor", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"title": "New Title"}),
    ("/api/v1/remove-metadata", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/protect-pdf", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"password": "123"}),
    ("/api/v1/protect", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"password": "123"}),
    ("/api/v1/unlock-pdf", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"password": "123"}),
    ("/api/v1/organize", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"page_order": "1"}),
    ("/api/v1/pdf-to-txt", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/pdf-to-images", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/pdf-to-png", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/pdf-to-jpg", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/flatten-pdf", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/add-image", {"file": ("test.pdf", dummy_pdf, "application/pdf"), "image": ("img.png", dummy_img, "image/png")}, {"x": "10", "y": "10", "page": "1"}),
    ("/api/v1/crop", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"x": "0", "y": "0", "width": "100", "height": "100"}),
    ("/api/v1/watermark", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"text": "WATERMARK"}),
    ("/api/v1/page-numbers", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"position": "bottom-right"}),
    ("/api/v1/pdf-bookmarks", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/repair-pdf", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/extract-images", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/ai-summarize", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {}),
    ("/api/v1/chat-pdf", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"question": "Summarize"}),
    ("/api/v1/translate-pdf", {"file": ("test.pdf", dummy_pdf, "application/pdf")}, {"target_lang": "es"}),
]

print("=== SMOKE TESTING ALL ENDPOINTS WITH RATE LIMIT BYPASS ===")
results = []

with patch.object(RateLimitService, 'check_and_increment_quota', return_value=None):
    for ep, files, data in endpoints_to_test:
        try:
            r = client.post(ep, files=files, data=data)
            status = r.status_code
            body = r.json() if status in [200, 400, 422, 500] and r.headers.get("content-type") == "application/json" else r.text[:80]
            results.append((ep, status, body))
            print(f"{ep:<30} | HTTP {status} | {body}")
        except Exception as e:
            results.append((ep, "EXC", str(e)))
            print(f"{ep:<30} | EXC | {e}")
