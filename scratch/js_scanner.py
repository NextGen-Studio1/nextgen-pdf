import os
import glob
import re

root = r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen"

for jspath in sorted(glob.glob(f"{root}/js/**/*.js", recursive=True)):
    rel = os.path.relpath(jspath, root).replace("\\", "/")
    content = open(jspath, encoding='utf-8', errors='ignore').read()
    print(f"=== JS FILE: {rel} ===")
    
    # window.location
    locs = re.findall(r'window\.location(?:\.href)?\s*=\s*[\'"]([^\'"]+)[\'"]', content)
    if locs:
        print("  Redirects:", locs)
        
    # fetch calls
    fetches = re.findall(r'fetch\(\s*[\'"`]([^\'"`]+)[\'"`]', content)
    if fetches:
        print("  Fetch static strings:", fetches)
        
    # dynamic API endpoints
    api_calls = re.findall(r'(?:API_BASE_URL|CONFIG\.API_BASE_URL|baseUrl)\s*\+\s*[\'"`]([^\'"`]+)[\'"`]', content)
    if api_calls:
        print("  API Relative endpoints:", api_calls)

print("\nScanning HTML inline scripts...")
for hpath in sorted(glob.glob(f"{root}/**/*.html", recursive=True)):
    rel = os.path.relpath(hpath, root).replace("\\", "/")
    content = open(hpath, encoding='utf-8', errors='ignore').read()
    
    locs = re.findall(r'window\.location(?:\.href)?\s*=\s*[\'"]([^\'"]+)[\'"]', content)
    fetches = re.findall(r'fetch\(\s*[\'"`]([^\'"`]+)[\'"`]', content)
    
    if locs or fetches:
        print(f"--- {rel} ---")
        if locs:
            print("  Inline Redirects:", locs)
        if fetches:
            print("  Inline Fetches:", fetches)
