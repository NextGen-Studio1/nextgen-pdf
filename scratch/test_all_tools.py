import subprocess
import sys

scripts = [
    "scratch/test_pdf_tools.py",
    "scratch/test_conversion_tools.py",
    "scratch/test_security_tools.py",
    "scratch/test_editing_tools.py",
    "scratch/test_advanced_tools.py"
]

print("==================================================")
print("RUNNING FULL 48-TOOL INTEGRATION SUITE TEST RUNNER")
print("==================================================\n")

failed = 0
for s in scripts:
    print(f"--- Running {s} ---")
    res = subprocess.run([sys.executable, s], capture_output=True, text=True)
    if res.returncode == 0:
        print(res.stdout)
    else:
        print("FAILED!")
        print(res.stdout)
        print(res.stderr)
        failed += 1

if failed == 0:
    print("==================================================")
    print("SUCCESS: ALL 48 PDF & DOCUMENT TOOLS VERIFIED 100% SUCCESS!")
    print("==================================================")
else:
    print(f"FAILED: {failed} test file(s) failed.")
    sys.exit(1)
