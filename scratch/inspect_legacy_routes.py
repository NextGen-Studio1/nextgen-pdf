import re

main_py = open('backend/main.py', encoding='utf-8', errors='ignore').read()

routes = re.findall(r'@app\.post\([\'"](/api/[^\'"]+)[\'"]\)\s*def\s+(\w+)\s*\((.*?)\):', main_py)
if not routes:
    routes = re.findall(r'@app\.post\([\'"](/api/[^\'"]+)[\'"]\)\s*async def\s+(\w+)\s*\((.*?)\):', main_py)

print(f"Found {len(routes)} post endpoints in backend/main.py:")
for route, name, params in sorted(routes):
    print(f"  {route:30} -> fn: {name}")

# Also extract response types (Response, FileResponse, JSONResponse, dict)
print("\nScanning return statements per route...")
endpoints_info = []
matches = re.finditer(r'@app\.post\([\'"](/api/([^\'"]+))[\'"]\)\s*(?:async\s+)?def\s+(\w+)\((.*?)\):', main_py, re.DOTALL)

for m in matches:
    full_route = m.group(1)
    tool_key = m.group(2)
    fn_name = m.group(3)
    params = m.group(4)
    
    # get code block until next @app
    start = m.start()
    next_match = re.search(r'@app\.', main_py[start+10:])
    end = start + 10 + next_match.start() if next_match else len(main_py)
    code = main_py[start:end]
    
    returns = re.findall(r'return\s+([^\n]+)', code)
    endpoints_info.append({
        'route': full_route,
        'tool_key': tool_key,
        'fn_name': fn_name,
        'params': [p.strip() for p in params.split(',') if p.strip()],
        'returns': returns
    })

print(f"Detailed scan for {len(endpoints_info)} endpoints completed.")
