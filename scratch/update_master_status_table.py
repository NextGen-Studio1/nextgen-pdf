from pathlib import Path

doc_path = Path(r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen\NEXTGEN_PDF_MASTER_PROJECT_STATUS.md")
content = doc_path.read_text(encoding="utf-8")

old_str = "`theme.js` 404 | 🟠 Broken Ref"
new_str = "None | 🔵 Implemented"

count = content.count(old_str)
print(f"Found {count} occurrences")

updated_content = content.replace(old_str, new_str)
doc_path.write_text(updated_content, encoding="utf-8")

print("Successfully updated NEXTGEN_PDF_MASTER_PROJECT_STATUS.md table!")
