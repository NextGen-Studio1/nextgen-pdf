import os
from pathlib import Path

root_dir = Path(r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen")
html_files = list(root_dir.glob("**/*.html"))

files_with_theme = []
files_without_theme = []

for h in html_files:
    if "node_modules" in str(h):
        continue
    content = h.read_text(encoding="utf-8", errors="ignore")
    rel_path = h.relative_to(root_dir)
    if "theme.js" in content:
        files_with_theme.append(str(rel_path))
    else:
        files_without_theme.append(str(rel_path))

print(f"Total HTML files: {len(html_files)}")
print(f"Files with theme.js reference: {len(files_with_theme)}")
print(f"Files WITHOUT theme.js reference: {len(files_without_theme)}")

print("\nFiles WITHOUT theme.js:")
for f in sorted(files_without_theme):
    print(f"  - {f}")
