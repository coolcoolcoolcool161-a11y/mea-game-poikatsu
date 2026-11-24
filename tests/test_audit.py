#!/usr/bin/env python3
import contextlib, io, subprocess, sys, tempfile
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
r=Path(__file__).resolve().parents[1]
p=subprocess.run([sys.executable,str(r/'scripts'/'audit_site.py')],capture_output=True,text=True)
print(p.stdout,end='')
if p.returncode: print(p.stderr); raise SystemExit(p.returncode)
assert 'ERROR 0' in p.stdout
spec=spec_from_file_location('audit_site',r/'scripts'/'audit_site.py')
mod=module_from_spec(spec); spec.loader.exec_module(mod)
# Parser regression checks: duplicate IDs and title/H1 counts remain observable.
d=mod.Doc(); d.feed('<html lang="ja"><head><title>A</title><title>B</title></head><body><main><h1>X</h1><div id="dup"></div><div id="dup"></div></main></body></html>')
assert d.title_count==2 and d.h1_count==1 and d.ids.count('dup')==2
# URL resolver retains fragments and resolves root-relative routes under the site root.
page=r/'about'/'index.html'; dest,frag=mod.local_target(page,'/games/#list')
assert dest==r/'games'/'index.html' and frag=='list'
# Integration fixture proves that a missing fragment is detected (not merely parsed).
with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'assets').mkdir(); (root/'other').mkdir()
    html='''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Test</title><meta name="description" content="A valid test page description"><meta name="robots" content="index,follow"></head><body><main><h1>Test</h1>{}</main></body></html>'''
    (root/'index.html').write_text(html.format('<a href="/other/#missing">Other</a>'),encoding='utf-8')
    (root/'other'/'index.html').write_text(html.format('<div id="present"></div>'),encoding='utf-8')
    (root/'assets'/'site.css').write_text('@media(max-width:700px){.x{min-width:0}} .x{minmax(0,1fr);}:focus-visible{outline:2px solid} @media(prefers-reduced-motion:reduce){*{animation:none}} p{overflow-wrap:anywhere}',encoding='utf-8')
    (root/'sitemap.xml').write_text('<urlset><url><loc>https://example.test/</loc></url></urlset>',encoding='utf-8')
    original=mod.ROOT; mod.ROOT=root
    output=io.StringIO()
    with contextlib.redirect_stdout(output): result=mod.main()
    mod.ROOT=original
    assert result==1 and 'ページ内アンカー切れ: /other/#missing' in output.getvalue(),output.getvalue()
print('PASS: 全HTML・内部リンク・ページ内アンカー・重複ID・SEO基本項目・アクセシビリティ・モバイルCSS監査')
