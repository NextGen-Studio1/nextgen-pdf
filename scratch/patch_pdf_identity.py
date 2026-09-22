import re

pdf_py_path = r"d:\Download\NextGen-PDF-Launch-Ready-V1\nextgen\backend\app\api\v1\endpoints\pdf.py"
content = open(pdf_py_path, encoding='utf-8').read()

old_func = '''def get_client_identity(request: Request, current_user: dict | None) -> tuple[str, str]:
    if current_user and "uid" in current_user:
        is_anonymous = current_user.get("firebase", {}).get("sign_in_provider") == "anonymous"
        return current_user["uid"], "guest" if is_anonymous else "free"
    client_ip = request.client.host if request.client else "unknown_client"
    return client_ip, "guest"'''

new_func = '''def get_client_identity(request: Request, current_user: dict | None) -> tuple[str, str]:
    if current_user and "uid" in current_user:
        is_anonymous = current_user.get("firebase", {}).get("sign_in_provider") == "anonymous"
        return current_user["uid"], "guest" if is_anonymous else "free"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "unknown_client"
    return client_ip, "guest"'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open(pdf_py_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated get_client_identity with x-forwarded-for support.")
else:
    print("Could not find exact old_func string in pdf.py")
