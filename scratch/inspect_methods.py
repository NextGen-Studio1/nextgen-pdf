import re

content = open('backend/main.py', encoding='utf-8', errors='ignore').read()

for fn in ['pdf-to-pdfa', 'resize-pages', 'ai-summarize']:
    m = re.search(r'@app\.post\("/api/' + fn + r'"\).*?(?=@app|\Z)', content, re.DOTALL)
    if m:
        print(f"=== {fn} ===")
        print(m.group(0)[:500])
        print("\n" + "="*40 + "\n")
