import os
import glob
import re
import json

root_dir = os.getcwd()

# 1. Gather HTML files
all_html_files = sorted([f.replace("\\", "/") for f in glob.glob("**/*.html", recursive=True) if not f.startswith("scratch") and not f.startswith("NextGen-PDF-Full-Updated/")])

# Categorize pages
public_pages = []
auth_pages = []
dashboard_pages = []
business_pages = []
tool_pages = []

for f in all_html_files:
    if f.startswith("pages/auth/"):
        auth_pages.append(f)
    elif f.startswith("pages/dashboard/business/"):
        business_pages.append(f)
    elif f.startswith("pages/dashboard/"):
        dashboard_pages.append(f)
    elif f in ["index.html", "404.html", "google9e92fa48642e65a1.html"] or f in ["pages/about.html", "pages/contact.html", "pages/pricing.html", "pages/faq.html", "pages/terms.html", "pages/privacy.html", "pages/cookie-policy.html", "pages/refund-policy.html", "pages/tools.html"]:
        public_pages.append(f)
    else:
        tool_pages.append(f)

print(f"Public pages: {len(public_pages)}")
print(f"Auth pages: {len(auth_pages)}")
print(f"Dashboard pages: {len(dashboard_pages)}")
print(f"Business pages: {len(business_pages)}")
print(f"Tool pages: {len(tool_pages)}")
print(f"Total active root pages: {len(all_html_files)}")
