import os
import sys
import glob
import re
from bs4 import BeautifulSoup

root = r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen"

# 1. Scan all tool HTML files in pages/ for data-tool
tool_pages = {}
for hpath in sorted(glob.glob(f"{root}/pages/*.html")):
    rel = os.path.relpath(hpath, root).replace("\\", "/")
    content = open(hpath, encoding='utf-8', errors='ignore').read()
    soup = BeautifulSoup(content, 'html.parser')
    
    # Tool pages have data-tool on body
    data_tool = soup.body.get('data-tool') if soup.body else None
    if data_tool:
        tool_pages[data_tool] = rel

print(f"Total HTML tool pages with data-tool: {len(tool_pages)}")
for dt, p in sorted(tool_pages.items()):
    print(f"  data-tool: {dt:25} -> page: {p}")

# 2. Inspect js/api.js for endpoint mapping logic
print("\nScanning js/api.js endpoint logic...")
api_js_content = open(os.path.join(root, 'js', 'api.js'), encoding='utf-8', errors='ignore').read()

# re to find endpoint selection
# const endpoint = tool === 'images-to-pdf' ? 'images-to-pdf' : tool === 'pdf-to-images' ? 'pdf-to-images' : tool;
m_endpoint = re.search(r'const endpoint = (.*?);', api_js_content)
if m_endpoint:
    print("  js/api.js endpoint logic:", m_endpoint.group(0))

# 3. Inspect legacy backend/main.py routes
legacy_routes = {}
main_py_content = open(os.path.join(root, 'backend', 'main.py'), encoding='utf-8', errors='ignore').read()
matches = re.findall(r'@app\.post\([\'"](/api/[^\'"]+)[\'"]\)', main_py_content)
for r in matches:
    legacy_routes[r.replace('/api/', '')] = r

print(f"\nTotal legacy routes in backend/main.py: {len(legacy_routes)}")
for route, full in sorted(legacy_routes.items()):
    print(f"  Legacy path: {full:30} -> tool key: {route}")

# 4. Inspect current modular backend/app/api/v1/endpoints/pdf.py
current_v1_routes = {}
pdf_py_content = open(os.path.join(root, 'backend', 'app', 'api', 'v1', 'endpoints', 'pdf.py'), encoding='utf-8', errors='ignore').read()
matches_v1 = re.findall(r'@router\.post\([\'"](/[\w-]+)[\'"]\)', pdf_py_content)
for r in matches_v1:
    current_v1_routes[r.lstrip('/')] = f"/api/v1{r}"

print(f"\nCurrent v1 PDF routes in app/api/v1/endpoints/pdf.py: {len(current_v1_routes)}")
for route, full in sorted(current_v1_routes.items()):
    print(f"  Modular v1 path: {full:30} -> tool key: {route}")
