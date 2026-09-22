import re

content = open('backend/main.py', encoding='utf-8', errors='ignore').read()

for fn in ['ai-summarize', 'chat-pdf', 'translate-pdf']:
    m = re.search(r'@app\.post\("/api/' + fn + r'"\).*?(?=@app|\Z)', content, re.DOTALL)
    if m:
        print(f"=== /api/{fn} ===")
        print(m.group(0)[:600])
        print("\n" + "="*40 + "\n")
