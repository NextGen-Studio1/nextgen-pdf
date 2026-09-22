import os
import glob
import json
import re
from bs4 import BeautifulSoup

root = r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen"

# 1. Gather files
all_files = [os.path.relpath(p, root).replace("\\", "/") for p in glob.glob(f"{root}/**/*", recursive=True) if os.path.isfile(p)]
all_files = [f for f in all_files if not any(x in f for x in ['.git/', '__pycache__/', '.pytest_cache/'])]

html_files = sorted([f for f in all_files if f.endswith('.html')])
js_files = sorted([f for f in all_files if f.endswith('.js')])
css_files = sorted([f for f in all_files if f.endswith('.css')])
py_files = sorted([f for f in all_files if f.endswith('.py')])

print(f"Total HTML: {len(html_files)}")
print(f"Total JS: {len(js_files)}")
print(f"Total CSS: {len(css_files)}")
print(f"Total Python: {len(py_files)}")

# 2. Analyze HTML pages & Broken References
broken_refs = []
page_details = {}

for rel_hpath in html_files:
    hpath = os.path.join(root, rel_hpath)
    with open(hpath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    soup = BeautifulSoup(content, 'html.parser')
    title = soup.title.string.strip() if (soup.title and soup.title.string) else 'MISSING'
    
    # Meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    desc = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else 'MISSING'
    
    # Scripts
    scripts = [s.get('src') for s in soup.find_all('script') if s.get('src')]
    # CSS
    stylesheets = [l.get('href') for l in soup.find_all('link', rel=lambda r: r and 'stylesheet' in r) if l.get('href')]
    # Links
    links = [a.get('href') for a in soup.find_all(['a', 'link']) if a.get('href')]
    
    h_dir = os.path.dirname(hpath)
    
    missing_scripts = []
    missing_stylesheets = []
    missing_links = []
    
    for src in scripts:
        if src.startswith(('http://', 'https://', '//', 'data:')):
            continue
        target = os.path.join(root, src.lstrip('/')) if src.startswith('/') else os.path.normpath(os.path.join(h_dir, src))
        target_rel = os.path.relpath(target, root).replace("\\", "/")
        if not os.path.exists(target):
            missing_scripts.append((src, target_rel))
            broken_refs.append({
                'source': rel_hpath,
                'type': 'script',
                'ref': src,
                'expected': target_rel
            })
            
    for href in stylesheets:
        if href.startswith(('http://', 'https://', '//', 'data:')):
            continue
        target = os.path.join(root, href.lstrip('/')) if href.startswith('/') else os.path.normpath(os.path.join(h_dir, href))
        target_rel = os.path.relpath(target, root).replace("\\", "/")
        if not os.path.exists(target):
            missing_stylesheets.append((href, target_rel))
            broken_refs.append({
                'source': rel_hpath,
                'type': 'css',
                'ref': href,
                'expected': target_rel
            })
            
    for href in links:
        if href.startswith(('http://', 'https://', '#', 'javascript:', 'mailto:', 'tel:', '//', 'data:')):
            continue
        target = os.path.join(root, href.lstrip('/')) if href.startswith('/') else os.path.normpath(os.path.join(h_dir, href))
        target_rel = os.path.relpath(target, root).replace("\\", "/")
        if not os.path.exists(target):
            missing_links.append((href, target_rel))
            broken_refs.append({
                'source': rel_hpath,
                'type': 'link',
                'ref': href,
                'expected': target_rel
            })
            
    page_details[rel_hpath] = {
        'title': title,
        'description': desc,
        'scripts': scripts,
        'stylesheets': stylesheets,
        'missing_scripts': missing_scripts,
        'missing_stylesheets': missing_stylesheets,
        'missing_links': missing_links
    }

print(f"\nTotal broken references found across all HTML files: {len(broken_refs)}")

with open(os.path.join(root, 'scratch', 'broken_refs.json'), 'w') as f:
    json.dump(broken_refs, f, indent=2)

with open(os.path.join(root, 'scratch', 'page_details.json'), 'w') as f:
    json.dump(page_details, f, indent=2)

print("Saved broken_refs.json and page_details.json")
