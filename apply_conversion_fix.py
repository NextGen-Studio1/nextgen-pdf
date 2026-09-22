from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "backend" / "main.py"

IMPORT_LINE = "from office_converter import convert_office_to_pdf\n"

ENDPOINTS = {
    "word-to-pdf": """@app.post("/api/word-to-pdf")
async def word_to_pdf(file: UploadFile = File(...)):
    if not is_docx(file):
        raise HTTPException(415, "Please upload a Word document (.doc/.docx).")
    data = await file.read()
    reject_large(data)
    try:
        result = convert_office_to_pdf(data, file.filename or "document.docx")
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The Word document could not be converted to PDF.") from exc

    base = safe_stem(file.filename, "document")
    return file_response(result, f"nextgen-{base}-word-to-pdf-result.pdf", "application/pdf")


""",
    "excel-to-pdf": """@app.post("/api/excel-to-pdf")
async def excel_to_pdf(file: UploadFile = File(...)):
    if not is_xlsx(file):
        raise HTTPException(415, "Please upload an Excel document (.xls/.xlsx).")
    data = await file.read()
    reject_large(data)
    try:
        result = convert_office_to_pdf(data, file.filename or "document.xlsx")
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The Excel document could not be converted to PDF.") from exc

    base = safe_stem(file.filename, "document")
    return file_response(result, f"nextgen-{base}-excel-to-pdf-result.pdf", "application/pdf")


""",
    "pptx-to-pdf": """@app.post("/api/pptx-to-pdf")
async def pptx_to_pdf(file: UploadFile = File(...)):
    if not is_pptx(file):
        raise HTTPException(415, "Please upload a PowerPoint document (.ppt/.pptx).")
    data = await file.read()
    reject_large(data)
    try:
        result = convert_office_to_pdf(data, file.filename or "presentation.pptx")
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "The PowerPoint document could not be converted to PDF.") from exc

    base = safe_stem(file.filename, "presentation")
    return file_response(result, f"nextgen-{base}-pptx-to-pdf-result.pdf", "application/pdf")


""",
}


def add_import(text: str) -> str:
    if "from office_converter import convert_office_to_pdf" in text:
        return text
    # Insert after the local/import block. A simple insertion after the
    # pypdf import is stable for the current project.
    marker = "from pypdf import PdfReader, PdfWriter\n"
    if marker in text:
        return text.replace(marker, marker + IMPORT_LINE, 1)
    return IMPORT_LINE + text


def replace_endpoint(text: str, endpoint: str, replacement: str) -> str:
    # Replace from this decorator up to the next top-level @app decorator.
    pattern = rf'@app\.post\("/api/{re.escape(endpoint)}"\).*?(?=^@app\.(?:post|get|put|delete)\(|\Z)'
    new_text, count = re.subn(pattern, replacement, text, flags=re.S | re.M)
    if count != 1:
        raise RuntimeError(
            f"Could not safely replace /api/{endpoint}. "
            "The main.py structure is different from the expected project version."
        )
    return new_text


def main() -> None:
    if not MAIN.exists():
        raise SystemExit(f"Missing {MAIN}")

    text = MAIN.read_text(encoding="utf-8")
    original = text

    text = add_import(text)
    for endpoint, replacement in ENDPOINTS.items():
        text = replace_endpoint(text, endpoint, replacement)

    if text == original:
        print("No changes were necessary.")
        return

    backup = MAIN.with_suffix(".py.before-office-fix")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    MAIN.write_text(text, encoding="utf-8")
    print("Applied high-fidelity Office -> PDF backend fix.")
    print(f"Backup: {backup}")
    print("Also replace backend/requirements.txt, backend/Dockerfile and render.yaml with the files from this package.")


if __name__ == "__main__":
    main()
