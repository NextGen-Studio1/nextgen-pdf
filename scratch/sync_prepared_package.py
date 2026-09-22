import os
import shutil
from pathlib import Path

cur_dir = Path(r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen")
upd_dir = Path(r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen\NextGen-PDF-Full-Updated")

# 1. Sync HTML files from update package
html_files = list(upd_dir.glob("**/*.html"))
synced_html = 0
for h in html_files:
    rel_path = h.relative_to(upd_dir)
    target_path = cur_dir / rel_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(h, target_path)
    synced_html += 1

print(f"Synced {synced_html} HTML files from update package.")

# 2. Sync config & SEO files
for config_file in ["robots.txt", "sitemap.xml", "firebase.json", "404.html"]:
    src = upd_dir / config_file
    dst = cur_dir / config_file
    if src.exists():
        shutil.copy2(src, dst)
        print(f"Synced {config_file}")

# 3. Sync documentation files if present
for doc_file in ["ANTIGRAVITY_FULL_INTEGRATION.md", "DEPLOYMENT_INTEGRATION.md"]:
    src = upd_dir / doc_file
    dst = cur_dir / doc_file
    if src.exists():
        shutil.copy2(src, dst)
        print(f"Synced {doc_file}")

print("Package sync completed successfully!")
