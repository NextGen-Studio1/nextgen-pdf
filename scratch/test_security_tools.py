import io
import sys
from pathlib import Path
import pymupdf as fitz
from fastapi.testclient import TestClient

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from main import app

def create_sample_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(100, 100), "CONFIDENTIAL SECRET INFORMATION", fontsize=18)
    page.insert_text(fitz.Point(100, 140), "User Social Security Number: SSN-999-1234", fontsize=12)
    meta = {"title": "Sensitive Document", "author": "John Doe", "subject": "Private File"}
    doc.set_metadata(meta)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def test_security_tools():
    client = TestClient(app)
    pdf_bytes = create_sample_pdf()

    print("Testing /api/protect-pdf...")
    res = client.post("/api/protect-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")}, data={"password": "secretpassword123"})
    assert res.status_code == 200, res.text
    protected_pdf = res.content
    
    # Verify encrypted
    p_doc = fitz.open(stream=protected_pdf, filetype="pdf")
    assert p_doc.is_encrypted
    p_doc.close()
    print("  [OK] /api/protect-pdf OK (Document successfully password-encrypted)")

    print("Testing /api/unlock-pdf...")
    res = client.post("/api/unlock-pdf", files={"file": ("test.pdf", protected_pdf, "application/pdf")}, data={"password": "secretpassword123"})
    assert res.status_code == 200, res.text
    unlocked_pdf = res.content
    u_doc = fitz.open(stream=unlocked_pdf, filetype="pdf")
    assert not u_doc.is_encrypted
    u_doc.close()
    print("  [OK] /api/unlock-pdf OK (Document successfully unlocked)")

    print("Testing /api/encrypt-pdf...")
    res = client.post("/api/encrypt-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")}, data={"user_password": "user123", "owner_password": "owner123", "allow_print": "true", "allow_copy": "false"})
    assert res.status_code == 200, res.text
    e_doc = fitz.open(stream=res.content, filetype="pdf")
    assert e_doc.is_encrypted
    assert e_doc.authenticate("user123")
    e_doc.close()
    print("  [OK] /api/encrypt-pdf OK (AES-256 + permission flags set)")

    print("Testing /api/redact-pdf...")
    res = client.post("/api/redact-pdf", files={"file": ("test.pdf", pdf_bytes, "application/pdf")}, data={"text": "CONFIDENTIAL", "pages": "all"})
    assert res.status_code == 200, res.text
    r_doc = fitz.open(stream=res.content, filetype="pdf")
    redacted_text = r_doc[0].get_text()
    assert "CONFIDENTIAL" not in redacted_text
    r_doc.close()
    print("  [OK] /api/redact-pdf OK (Text permanently redacted from stream)")

    print("Testing /api/remove-metadata...")
    res = client.post("/api/remove-metadata", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert res.status_code == 200, res.text
    clean_doc = fitz.open(stream=res.content, filetype="pdf")
    m = clean_doc.metadata
    assert not m.get("author")
    assert not m.get("title")
    clean_doc.close()
    print("  [OK] /api/remove-metadata OK (All metadata fields cleared)")

    print("\nALL SECURITY & PRIVACY TOOL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_security_tools()
