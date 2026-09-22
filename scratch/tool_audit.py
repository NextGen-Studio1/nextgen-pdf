import os
import glob
import re
import sys

root_dir = os.getcwd()
sys.path.insert(0, os.path.join(root_dir, "backend"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

pages_dir = os.path.join(root_dir, "pages")
tool_pages = []

for f in sorted(os.listdir(pages_dir)):
    if f.endswith(".html"):
        path = os.path.join(pages_dir, f)
        with open(path, "r", encoding="utf-8", errors="ignore") as file_obj:
            content = file_obj.read()
        
        # Check if it has file upload or tool interface
        has_upload = 'type="file"' in content or 'drop-zone' in content or 'file-input' in content or 'upload-box' in content
        
        # Extract js file scripts
        scripts = re.findall(r'<script\s+[^>]*src=["\']([^"\']+)["\']', content)
        
        # Extract fetch or api calls from referenced js files
        api_endpoints = []
        for s in scripts:
            js_path = os.path.normpath(os.path.join(pages_dir, s)).replace("\\", "/")
            if os.path.exists(js_path):
                with open(js_path, "r", encoding="utf-8", errors="ignore") as jsf:
                    js_content = jsf.read()
                    matches = re.findall(r'["\'](/api/v1/[^"\'\?]+)["\']', js_content)
                    api_endpoints.extend(matches)
        
        tool_pages.append({
            "filename": f,
            "has_upload": has_upload,
            "scripts": scripts,
            "api_endpoints": list(set(api_endpoints))
        })

print(f"Total HTML files in pages/: {len(tool_pages)}")

# Now test health endpoint and tool endpoints
print("\n--- Health Check ---")
res = client.get("/api/v1/health")
print(f"Health check status: {res.status_code}, body: {res.json()}")

# Create a small dummy PDF file bytes for testing
dummy_pdf_header = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"

print("\n--- Smoke Testing Key Tool Endpoints ---")
test_endpoints = [
    ("/api/v1/compress", {"file": ("test.pdf", dummy_pdf_header, "application/pdf")}, {"compression_level": "recommended"}),
    ("/api/v1/rotate", {"file": ("test.pdf", dummy_pdf_header, "application/pdf")}, {"angle": "90"}),
    ("/api/v1/extract-pages", {"file": ("test.pdf", dummy_pdf_header, "application/pdf")}, {"pages": "1"}),
    ("/api/v1/delete-pages", {"file": ("test.pdf", dummy_pdf_header, "application/pdf")}, {"pages": "1"}),
    ("/api/v1/metadata-editor", {"file": ("test.pdf", dummy_pdf_header, "application/pdf")}, {"title": "Test Title"}),
    ("/api/v1/protect-pdf", {"file": ("test.pdf", dummy_pdf_header, "application/pdf")}, {"password": "123"}),
    ("/api/v1/unlock-pdf", {"file": ("test.pdf", dummy_pdf_header, "application/pdf")}, {"password": "123"}),
]

for ep, files, data in test_endpoints:
    try:
        r = client.post(ep, files=files, data=data)
        print(f"{ep:<30} -> Status: {r.status_code}, Json: {r.json() if r.status_code==200 else r.text[:100]}")
    except Exception as e:
        print(f"{ep:<30} -> EXCEPTION: {e}")
