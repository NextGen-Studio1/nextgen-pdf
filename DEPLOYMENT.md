# NextGen PDF — Launch Checklist

This package is a launch-ready MVP. You still need to deploy the frontend/backend and provide your own domain, hosting accounts, and production configuration.

## 1. Test locally

Backend:
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend (from project root, in a second terminal):
```powershell
python -m http.server 5500
```

Open `http://127.0.0.1:5500`. Test all five tools with real files.

## 2. Put the project in GitHub

Create a new GitHub repository and upload the contents of this folder. Do not commit `backend/.venv`, secrets, private files, or generated output files.

## 3. Deploy the backend

Render can use the included `render.yaml`. Create a Web Service from the GitHub repository. Set `FRONTEND_ORIGINS` to the exact public frontend origin, for example:

`https://your-site.netlify.app`

Do not add a trailing slash.

After deployment, confirm:

`https://YOUR-BACKEND.onrender.com/api/health`

returns JSON with `status: ok`.

## 4. Set the frontend API URL

Edit `js/config.js` and replace the local URL with your deployed API URL:

```js
window.NEXTGEN_API_BASE = 'https://YOUR-BACKEND.onrender.com/api';
```

## 5. Deploy the frontend

Netlify can deploy the project root as a static site. The included `netlify.toml` sets the publish directory to the project root.

After deployment, open every tool page and run a real conversion.

## 6. Domain

Buy your chosen domain from a registrar, then connect the domain to Netlify. Enable HTTPS.

## 7. Production privacy

Before public launch, update the Privacy page with the actual hosting provider, file retention/deletion behavior, logs, backups, security controls, contact information, and any legal requirements that apply to your users.

## 8. Important production upgrades before significant traffic

- Add rate limiting / abuse protection.
- Add request and processing time limits.
- Add monitoring and error logging.
- Consider malware/file-content scanning.
- Review CORS and allowed domains.
- Set a clear privacy policy and terms.
- Add analytics only after deciding what data is necessary.

The current MVP intentionally avoids accounts, payments, permanent file storage, and a database.
