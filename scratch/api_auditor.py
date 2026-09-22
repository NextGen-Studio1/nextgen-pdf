import os
import sys
import glob
import re

root = r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen"
sys.path.insert(0, os.path.join(root, "backend"))

# 1. Backend endpoints from FastAPI app
from app.main import app

fastapi_routes = []
for r in app.routes:
    methods = sorted(list(getattr(r, 'methods', [])))
    methods_str = ', '.join(methods) if methods else 'GET'
    fastapi_routes.append({
        'methods': methods_str,
        'path': r.path,
        'name': getattr(r, 'name', ''),
        'endpoint_fn': getattr(r.endpoint, '__name__', str(r.endpoint))
    })

print(f"Total Registered FastAPI Routes in app.main: {len(fastapi_routes)}")
for r in sorted(fastapi_routes, key=lambda x: x['path']):
    print(f"  {r['methods']:12} | {r['path']:40} | {r['endpoint_fn']}")

# 2. Check routers defined in backend python files that may NOT be included in app.main
print("\nChecking backend python files for all router decorators...")
all_py_routes = []
for pypath in glob.glob(f"{root}/backend/**/*.py", recursive=True):
    rel = os.path.relpath(pypath, root).replace("\\", "/")
    content = open(pypath, encoding='utf-8', errors='ignore').read()
    
    matches = re.findall(r'@(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]', content)
    for m, path in matches:
        all_py_routes.append({
            'file': rel,
            'method': m.upper(),
            'path': path
        })

print(f"Total decorator endpoints found in backend python files: {len(all_py_routes)}")
for r in sorted(all_py_routes, key=lambda x: x['path']):
    print(f"  {r['method']:6} | {r['path']:35} | {r['file']}")
