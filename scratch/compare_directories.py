import os
import hashlib
from pathlib import Path

cur_dir = Path(r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen")
upd_dir = Path(r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen\NextGen-PDF-Full-Updated")

def get_rel_files(base_path, ignore_subdirs=["NextGen-PDF-Full-Updated", ".git", ".pytest_cache", "scratch", "node_modules", "__pycache__"]):
    rel_files = {}
    for root, dirs, files in os.walk(base_path):
        # Modify dirs in-place to skip ignored subdirectories
        dirs[:] = [d for d in dirs if d not in ignore_subdirs]
        for f in files:
            full_path = Path(root) / f
            rel_path = full_path.relative_to(base_path)
            # Skip python cache or temp files
            if ".pyc" in f or ".DS_Store" in f or f == ".sqlite" or f.endswith(".db"):
                continue
            rel_files[str(rel_path)] = full_path
    return rel_files

cur_files = get_rel_files(cur_dir)
upd_files = get_rel_files(upd_dir)

cur_keys = set(cur_files.keys())
upd_keys = set(upd_files.keys())

only_in_cur = sorted(list(cur_keys - upd_keys))
only_in_upd = sorted(list(upd_keys - cur_keys))
in_both = sorted(list(cur_keys & upd_keys))

identical = []
different = []

def file_hash(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

for r in in_both:
    if file_hash(cur_files[r]) == file_hash(upd_files[r]):
        identical.append(r)
    else:
        different.append(r)

print(f"Total files in Current Project: {len(cur_files)}")
print(f"Total files in Update Package: {len(upd_files)}")
print(f"Files ONLY in Current Project: {len(only_in_cur)}")
print(f"Files ONLY in Update Package: {len(only_in_upd)}")
print(f"Identical files in both: {len(identical)}")
print(f"Different files in both: {len(different)}")

print("\n--- FILES ONLY IN UPDATE PACKAGE ---")
for f in only_in_upd:
    print(f"  + {f}")

print("\n--- FILES ONLY IN CURRENT PROJECT ---")
for f in only_in_cur:
    print(f"  - {f}")

print("\n--- DIFFERENT FILES IN BOTH ---")
for f in different:
    print(f"  ~ {f}")
