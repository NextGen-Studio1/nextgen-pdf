# NextGen PDF Backend

FastAPI backend for the five initial tools:

- POST `/api/compress`
- POST `/api/merge`
- POST `/api/split`
- POST `/api/images-to-pdf`
- POST `/api/pdf-to-images`
- GET `/api/health`

## Local setup (Windows)

```powershell
cd nextgen\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Serve the frontend separately, for example from the project root:

```powershell
python -m http.server 5500
```

Then open `http://127.0.0.1:5500/`.

The frontend currently calls `http://127.0.0.1:8000/api`. For deployment, set `window.NEXTGEN_API_BASE` before loading `js/api.js`, or change the default in that file.

The backend keeps uploaded files in memory and returns generated files directly; it does not create a permanent upload store.
