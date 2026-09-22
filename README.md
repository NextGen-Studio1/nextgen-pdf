# NextGen PDF — High-Fidelity Office → PDF Fix

This patch fixes the core Office-to-PDF problem in the NextGen PDF backend.

## What was wrong

The previous `/api/word-to-pdf`, `/api/excel-to-pdf`, and `/api/pptx-to-pdf`
implementations extracted text with Python libraries and manually drew that
text into a new PDF. That discards much of the original document layout.

## What this patch changes

Office documents are now rendered by **LibreOffice**:

DOCX/DOC → LibreOffice → PDF
XLSX/XLS → LibreOffice → PDF
PPTX/PPT → LibreOffice → PDF

This is a document renderer, not a text reconstruction pipeline. It therefore
preserves the original document's layout much more faithfully, including images,
fonts available on the server, paragraph formatting, tables, margins,
headers/footers, page breaks and spacing.

## Files

- `backend/office_converter.py` — reusable conversion engine
- `backend/Dockerfile` — installs LibreOffice + fonts on Render
- `backend/requirements.txt` — backend dependencies
- `render.yaml` — switches the Render service to Docker
- `apply_conversion_fix.py` — safely patches the existing `backend/main.py`

## Apply to your current project

Copy these files into the root of your current NextGen PDF project, then run:

```powershell
python apply_conversion_fix.py
```

The script creates:

```text
backend/main.py.before-office-fix
```

before changing `backend/main.py`.

Then verify:

```powershell
python -m py_compile backend/main.py backend/office_converter.py
```

## Local requirement

For local Word/Excel/PowerPoint → PDF testing, install LibreOffice on the
machine and make sure `libreoffice` or `soffice` is on PATH.

## Render deployment

The included `render.yaml` uses the Dockerfile so Render installs LibreOffice.
This is required; simply adding a Python package is not enough.

After deployment, test with the original Word assignment and compare the PDF
page-by-page with Word.

## Important

Do not use the old text-reconstruction implementations for Office → PDF again.
All three Office conversion endpoints should use `convert_office_to_pdf()`.
