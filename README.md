# NextGen PDF

Frontend + FastAPI backend for the first production-ready MVP of NextGen PDF.

## V1 tools
- JPG/PNG → PDF
- Merge PDF
- Split PDF (split every page or extract page/range groups)
- Compress PDF (best quality, balanced, smallest size)
- PDF → JPG/PNG (all pages or selected pages/ranges)

## Run locally

### Backend
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend
In another terminal from the project root:
```powershell
python -m http.server 5500
```
Open `http://127.0.0.1:5500`.

The frontend calls `http://127.0.0.1:8000/api` by default. Set `window.NEXTGEN_API_BASE` before loading the app when the API is deployed elsewhere.

## File rules
- Maximum single upload: 25 MB.
- Merge and image-to-PDF: up to 20 files.
- One output file downloads directly.
- Multiple output files are packaged as a ZIP.
- Generated files are streamed back and are not intentionally persisted by this MVP.
