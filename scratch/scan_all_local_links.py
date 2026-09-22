import os
import glob
import re

root_dir = os.getcwd()
html_files = [f.replace("\\", "/") for f in glob.glob("**/*.html", recursive=True) if not f.startswith("scratch") and not f.startswith("NextGen-PDF-Full-Updated/")]
js_files = [f.replace("\\", "/") for f in glob.glob("**/*.js", recursive=True) if not f.startswith("scratch") and not f.startswith("NextGen-PDF-Full-Updated/")]

broken = []

for hf in html_files:
    with open(hf, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    links = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', content)
    base_dir = os.path.dirname(hf)

    for link in links:
        if link.startswith("http://") or link.startswith("https://") or link.startswith("#") or link.startswith("data:") or link.startswith("mailto:") or link.startswith("javascript:"):
            continue
        
        target = link.split("?")[0].split("#")[0]
        if not target:
            continue

        if target.startswith("/"):
            resolved = target.lstrip("/")
        else:
            resolved = os.path.normpath(os.path.join(base_dir, target)).replace("\\", "/")

        exists = (
            os.path.exists(resolved) or
            os.path.exists(resolved + ".html") or
            os.path.exists(os.path.join(resolved, "index.html"))
        )

        if not exists:
            broken.append({
                "source": hf,
                "link": link,
                "resolved": resolved
            })

print(f"Total HTML files scanned: {len(html_files)}")
print(f"Broken links count: {len(broken)}")
for b in broken:
    print(f"  [BROKEN] {b['source']} -> {b['link']} (resolved: {b['resolved']})")
