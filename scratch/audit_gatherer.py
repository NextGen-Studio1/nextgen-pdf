import os
import glob
import re
import json

root_dir = os.getcwd()

print("=== 1. HTML PAGES SCAN ===")
all_html = [f.replace("\\", "/") for f in glob.glob("**/*.html", recursive=True) if not f.startswith("scratch")]
root_html = [f for f in all_html if not f.startswith("NextGen-PDF-Full-Updated/")]
print(f"Total HTML files in repo: {len(all_html)}")
print(f"Root active HTML files: {len(root_html)}")

pages_by_dir = {
    "root": [f for f in root_html if "/" not in f],
    "auth": [f for f in root_html if f.startswith("pages/auth/")],
    "dashboard": [f for f in root_html if f.startswith("pages/dashboard/") and "business/" not in f],
    "business": [f for f in root_html if f.startswith("pages/dashboard/business/")],
    "main_pages": [f for f in root_html if f.startswith("pages/") and not f.startswith("pages/auth/") and not f.startswith("pages/dashboard/")]
}

for cat, files in pages_by_dir.items():
    print(f"Category {cat}: {len(files)} files")

print("\n=== 2. FASTAPI ROUTES EXTRACTION ===")
import sys
sys.path.insert(0, os.path.join(root_dir, "backend"))
try:
    from app.main import app as fastapi_app
    print(f"FastAPI App loaded successfully. Title: {fastapi_app.title}")
    routes_info = []
    for route in fastapi_app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        name = getattr(route, "name", None)
        endpoint = getattr(route, "endpoint", None)
        endpoint_name = endpoint.__name__ if endpoint else ""
        routes_info.append({
            "path": path,
            "methods": list(methods) if methods else [],
            "name": name,
            "endpoint": endpoint_name
        })
    print(f"Total FastAPI Routes found: {len(routes_info)}")
    for r in sorted(routes_info, key=lambda x: x['path']):
        print(f"  {','.join(r['methods']):<10} {r['path']} -> {r['endpoint']}")
except Exception as e:
    print(f"Error loading FastAPI app: {e}")

print("\n=== 3. CHECK FOR 404 / BROKEN REFERENCES ===")
broken_refs = []
for h_file in root_html:
    with open(h_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # find href and src
    links = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', content)
    for link in links:
        if link.startswith("http://") or link.startswith("https://") or link.startswith("#") or link.startswith("data:"):
            continue
        # Check clean URLs or actual file paths
        target_path = link.split("?")[0].split("#")[0]
        if not target_path:
            continue
        
        # relative path resolution
        base_dir = os.path.dirname(h_file)
        if target_path.startswith("/"):
            resolved = target_path.lstrip("/")
        else:
            resolved = os.path.normpath(os.path.join(base_dir, target_path)).replace("\\", "/")
        
        # Check if resolved exists or resolved + .html exists
        exists = os.path.exists(resolved) or os.path.exists(resolved + ".html") or os.path.exists(os.path.join(resolved, "index.html"))
        if not exists and not resolved.startswith("api/"):
            broken_refs.append({
                "source": h_file,
                "link": link,
                "resolved": resolved
            })

print(f"Found {len(broken_refs)} potential broken file references in HTML:")
for b in broken_refs[:15]:
    print(f"  {b['source']} -> {b['link']} (resolved: {b['resolved']})")

