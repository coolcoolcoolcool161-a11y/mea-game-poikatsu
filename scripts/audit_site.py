#!/usr/bin/env python3
"""Offline HTML, SEO, link, accessibility and responsive-CSS audit (stdlib only)."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote
from collections import Counter
import os, re, sys, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def base_path():
    """ビルドと同じ規則でベースパスを求める（リンク解決時に接頭辞を取り除く）。"""
    env_path=os.environ.get('S07_SITE_BASE_PATH','').strip().rstrip('/')
    if env_path: return env_path
    raw=os.environ.get('S07_SITE_BASE_URL','').strip().rstrip('/')
    if raw:
        p=urlparse(raw).path.rstrip('/')
        if p: return p
    return '/mea-game-poikatsu'
BASE_PATH = base_path()

def strip_base(path: str) -> str:
    if BASE_PATH and (path == BASE_PATH or path.startswith(BASE_PATH + '/')):
        return path[len(BASE_PATH):] or '/'
    return path
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags=[]; self.links=[]; self.images=[]; self.titles=[]; self.title_count=0
        self.h1=[]; self.h1_count=0; self.desc=[]; self.robots=[]; self.canonical=[]
        self.lang=None; self.viewport=[]; self.headings=[]; self.ids=[]; self.charset=[]
        self.mains=0; self.navs=0; self.tables=0; self.table_headers=0
        self._title=False; self._h1=False; self._a_index=None; self._a_text=''
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); self.tags.append((tag,a))
        if tag=='html': self.lang=a.get('lang')
        if 'id' in a: self.ids.append(a['id'])
        if tag=='meta':
            if a.get('name','').lower()=='viewport': self.viewport.append(a.get('content',''))
            if a.get('name','').lower()=='description': self.desc.append(a.get('content',''))
            if a.get('name','').lower()=='robots': self.robots.append(a.get('content',''))
            if 'charset' in a: self.charset.append(a['charset'].lower())
        if tag=='link' and 'canonical' in a.get('rel','').lower().split(): self.canonical.append(a.get('href',''))
        if tag=='a':
            self.links.append({'href':a.get('href',''),'aria':a.get('aria-label',''),'text':''})
            self._a_index=len(self.links)-1; self._a_text=''
        if tag=='img': self.images.append(a)
        if tag=='title': self.title_count+=1; self._title=True
        if tag=='h1': self.h1_count+=1; self._h1=True
        if tag in ('h1','h2','h3','h4','h5','h6'): self.headings.append(int(tag[1]))
        if tag=='main': self.mains+=1
        if tag=='nav': self.navs+=1
        if tag=='table': self.tables+=1
        if tag in ('th',): self.table_headers+=1
    def handle_endtag(self, tag):
        if tag=='title': self._title=False
        if tag=='h1': self._h1=False
        if tag=='a': self._a_index=None
    def handle_data(self, data):
        if self._title: self.titles.append(data)
        if self._h1: self.h1.append(data)
        if self._a_index is not None: self._a_text+=data; self.links[self._a_index]['text']=self._a_text.strip()

def local_target(page: Path, href: str):
    parsed=urlparse(href)
    if parsed.scheme or parsed.netloc or href.startswith(('mailto:','tel:','javascript:','data:')):
        return None, parsed.fragment
    path=unquote(parsed.path)
    if not path: return page, parsed.fragment
    if path.startswith('/'): path=strip_base(path)
    dest=(ROOT/path.lstrip('/')) if path.startswith('/') else (page.parent/path)
    dest=dest.resolve()
    if path.endswith('/') or not dest.suffix: dest=dest/'index.html'
    return dest, parsed.fragment

def main():
    errors=[]; warnings=[]
    html_files=sorted(p for p in ROOT.rglob('*.html') if not any(x in p.parts for x in ('.git','__pycache__')))
    parsed_docs={}
    for p in html_files:
        rel=p.relative_to(ROOT).as_posix(); d=Doc(); parsed_docs[p.resolve()]=d
        try: d.feed(p.read_text(encoding='utf-8'))
        except Exception as ex: errors.append(f'{rel}: HTML解析失敗 {ex}'); continue
        def err(s): errors.append(f'{rel}: {s}')
        def warn(s): warnings.append(f'{rel}: {s}')
        title=''.join(d.titles).strip(); desc=d.desc[0].strip() if d.desc else ''
        if not d.lang: err('html lang欠落')
        if len(d.charset)!=1: err('文字コードcharset欠落/重複')
        if len(d.viewport)!=1 or 'width=device-width' not in (d.viewport[0] if d.viewport else ''): err('viewport設定不正/欠落')
        if d.title_count!=1 or not title: err('titleタグ欠落/重複/空')
        elif len(title)>65: warn(f'titleが長い（{len(title)}文字）')
        if len(d.desc)!=1 or not desc: err('meta description欠落/重複/空')
        elif len(desc)>170: warn(f'meta descriptionが長い（{len(desc)}文字）')
        if len(d.robots)!=1 or not d.robots[0].strip(): err('robots meta欠落/重複/空')
        if d.h1_count!=1 or not ''.join(d.h1).strip(): err('H1は1つ必須')
        if d.mains!=1: err(f'mainランドマークは1つ必須（{d.mains}）')
        if not d.canonical:
            if not any('noindex' in x.lower() for x in d.robots): warn('canonical未設定（実ホスト確定後に絶対URLを設定）')
        elif len(d.canonical)!=1: err('canonical重複')
        elif urlparse(d.canonical[0]).scheme!='https' or not urlparse(d.canonical[0]).netloc: err('canonicalはHTTPS絶対URL必須')
        counts=Counter(d.ids)
        for ident,n in counts.items():
            if not ident: err('空のid属性')
            elif n>1: err(f'id重複: {ident}（{n}回）')
        for im in d.images:
            if 'alt' not in im: err('画像alt属性欠落')
        for link in d.links:
            href,aria=link['href'],link['aria']
            if not href or not (aria.strip() or link['text'].strip()): err('リンク先またはリンク名が空'); continue
            if href.strip()=='#': warn('href="#"の死にリンク残存（リンク先未設定）'); continue
            dest,fragment=local_target(p,href)
            if dest is None: continue
            if dest.is_dir(): dest=dest/'index.html'
            if not dest.is_file(): err(f'内部リンク切れ: {href}'); continue
            if fragment:
                target_doc=parsed_docs.get(dest.resolve())
                if target_doc is None:
                    target_doc=Doc()
                    try: target_doc.feed(dest.read_text(encoding='utf-8'))
                    except Exception: target_doc=None
                if target_doc and fragment not in target_doc.ids: err(f'ページ内アンカー切れ: {href}')
        prev=0
        for level in d.headings:
            if prev and level>prev+1: warn(f'見出し階層が飛んでいる: h{prev}→h{level}')
            prev=level
        for tag,attrs in d.tags:
            if tag=='a' and attrs.get('target')=='_blank' and 'noopener' not in attrs.get('rel','').lower().split():
                warn('target="_blank"にrel="noopener"未指定')
    sm=ROOT/'sitemap.xml'
    if sm.exists():
        try:
            tree=ET.parse(sm)
            for loc in tree.findall('.//{*}loc'):
                url=(loc.text or '').strip()
                if 'REPLACE-WITH-ACTUAL-HOST' in url: warnings.append('sitemap.xml: 実ホスト未設定のプレースホルダー')
                path=strip_base(urlparse(url).path or '/'); dest=ROOT/unquote(path.lstrip('/'))
                if path.endswith('/') or not dest.suffix: dest=dest/'index.html'
                if not dest.is_file(): errors.append(f'sitemap.xml: 実在しないURL {url}')
                else:
                    d=parsed_docs.get(dest.resolve()) or Doc();
                    if dest.resolve() not in parsed_docs: d.feed(dest.read_text(encoding='utf-8'))
                    if any('noindex' in x.lower() for x in d.robots): errors.append(f'sitemap.xml: noindexページを掲載 {url}')
        except Exception as ex: errors.append(f'sitemap.xml: XML不正 {ex}')
    css=ROOT/'assets'/'site.css'
    if not css.exists(): errors.append('assets/site.css欠落')
    else:
        c=css.read_text(encoding='utf-8')
        if not re.search(r'@media\s*\(max-width\s*:\s*\d+px\)',c): errors.append('CSS: モバイル向けmedia query欠落')
        if 'minmax(0,1fr)' not in c.replace(' ',''): warnings.append('CSS: gridの横幅縮小対策 minmax(0,1fr)未確認')
        if ':focus-visible' not in c: warnings.append('CSS: 明示的なfocus-visibleスタイル未確認')
        if 'prefers-reduced-motion' not in c: warnings.append('CSS: 動きを抑える設定 prefers-reduced-motion 未確認')
        if 'overflow-wrap:' not in c and 'overflow-wrap :' not in c: warnings.append('CSS: 長い文字列の折返し制御未確認')
    print(f'HTML監査対象: {len(html_files)} files')
    for x in warnings: print('WARN:',x)
    for x in errors: print('ERROR:',x)
    print(f'結果: ERROR {len(errors)} / WARN {len(warnings)}')
    return 1 if errors else 0
if __name__=='__main__': sys.exit(main())
