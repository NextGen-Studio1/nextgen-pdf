import os
from pathlib import Path

root_dir = Path(r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen")
html_files = list(root_dir.glob("**/*.html"))

updated_count = 0

for h in html_files:
    if "node_modules" in str(h) or "tmp_storage" in str(h) or "google9e92fa48642e65a1" in str(h):
        continue
    
    content = h.read_text(encoding="utf-8", errors="ignore")
    if "theme.js" in content:
        continue  # Already has theme.js reference
    
    # Determine relative path to js/theme.js
    rel_to_root = h.relative_to(root_dir)
    depth = len(rel_to_root.parts) - 1
    if depth == 0:
        script_src = "js/theme.js"
    else:
        script_src = "../" * depth + "js/theme.js"
    
    script_tag = f'  <script src="{script_src}"></script>\n'
    
    # Insert in <head> right before </head>, or at top of body
    if "</head>" in content:
        new_content = content.replace("</head>", f"{script_tag}</head>", 1)
    elif "<head>" in content:
        new_content = content.replace("<head>", f"<head>\n{script_tag}", 1)
    else:
        new_content = script_tag + content
    
    h.write_text(new_content, encoding="utf-8")
    updated_count += 1
    print(f"Updated: {rel_to_root} -> {script_src}")

print(f"\nTotal HTML files updated with theme.js: {updated_count}")
