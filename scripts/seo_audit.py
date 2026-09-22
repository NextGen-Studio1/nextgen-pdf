from pathlib import Path
from bs4 import BeautifulSoup
import re, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
errors = []
warnings = []
pages = []

for p in ROOT.rglob('*.html'):
    if any(x in p.parts for x in ['.git', '.venv', 'node_modules', 'backend', 'NextGen-PDF-Full-Updated']) or (p.name.startswith('google') and 'verification' not in p.name):
        continue
    pages.append(p)

titles = {}
descs = {}

for p in pages:
    s = BeautifulSoup(p.read_text(encoding='utf8', errors='ignore'), 'html.parser')
    rel = p.relative_to(ROOT).as_posix()
    private = rel.startswith(('pages/auth/', 'pages/dashboard/')) or rel == '404.html'
    
    if not s.title or not s.title.get_text(strip=True):
        errors.append(f'{rel}: missing title')
    else:
        titles.setdefault(s.title.get_text(' ', strip=True), []).append(rel)
        
    d = s.find('meta', attrs={'name': 'description'})
    if not d or not d.get('content', '').strip():
        errors.append(f'{rel}: missing description')
    else:
        descs.setdefault(d['content'].strip(), []).append(rel)
        
    c = s.find('link', attrs={'rel': lambda x: x and 'canonical' in x})
    if not private and (not c or not c.get('href')):
        errors.append(f'{rel}: missing canonical')
        
    r = s.find('meta', attrs={'name': 'robots'})
    if private and (not r or 'noindex' not in r.get('content', '').lower()):
        errors.append(f'{rel}: private page is not noindex')

for k, v in titles.items():
    if len(v) > 1:
        warnings.append('duplicate title: ' + k + ' -> ' + ', '.join(v))

for k, v in descs.items():
    public_v = [x for x in v if not x.startswith(('pages/auth/', 'pages/dashboard/')) and x != '404.html' and not x.startswith('google9e92')]
    if len(public_v) > 1:
        warnings.append('duplicate description -> ' + ', '.join(public_v))

try:
    ET.parse(ROOT / 'sitemap.xml')
except Exception as e:
    errors.append(f'sitemap.xml invalid: {e}')

if not (ROOT / 'robots.txt').exists():
    errors.append('robots.txt missing')

missing = []
for p in pages:
    s = BeautifulSoup(p.read_text(encoding='utf8', errors='ignore'), 'html.parser')
    for tag, attr in [('script', 'src'), ('link', 'href')]:
        for el in s.find_all(tag):
            u = el.get(attr, '')
            if not u or u.startswith(('http:', 'https:', '//', '#', 'mailto:', 'javascript:', 'data:')):
                continue
            target = (p.parent / u).resolve()
            try:
                target.relative_to(ROOT.resolve())
            except ValueError:
                continue
            if not target.exists():
                missing.append(f'{p.relative_to(ROOT)} -> {u}')

if missing:
    errors += ['missing local asset: ' + x for x in missing]

print(f'Pages checked: {len(pages)}')
print(f'Errors: {len(errors)}')
print(f'Warnings: {len(warnings)}')

for x in errors:
    print('ERROR:', x)
for x in warnings[:50]:
    print('WARNING:', x)

raise SystemExit(1 if errors else 0)
