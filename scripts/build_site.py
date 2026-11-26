#!/usr/bin/env python3
"""Generate the S07 game wiki from the five ledgers (games/campaigns/knowledge/sources/campaign_history).

- ビルド冒頭で validate_data.py を実行し、失敗したら生成を中止する。
- 生成判定（掲載資格＋公開状態）と index 判定（G01〜G12相当）は分離する。
- ベースパスは S07_SITE_BASE_PATH（既定 /mea-game-poikatsu）で差し替え可能。
  S07_SITE_BASE_URL はパス付き（https://host/mea-game-poikatsu）も許可し、
  canonical・sitemap はその実ホストが確定したときだけ出力する。
- 全ページに GA4（G-8BB8V3DRW8）と referral_click 計測（site.js）を組み込む。広告は入れない。
- JSONデータは必ずエスケープしてから挿入し、原文HTMLは無加工で挿入しない。
"""
import base64, json, html, os, re, shutil, struct, subprocess, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SITE_NAME = 'ポイ活ゲーム攻略Wiki'
GA4_ID = 'G-8BB8V3DRW8'
DEFAULT_BASE_PATH = '/mea-game-poikatsu'
PLACEHOLDER_HOST = 'https://REPLACE-WITH-ACTUAL-HOST'
ELIGIBLE = {'確認済み', 'confirmed'}
PUBLISHED = {'公開', 'published'}
ACTIVE_STATUS = {'掲載中', '再開', '変更', 'active', 'reopened', 'changed'}
INDEXABLE_RANKS = {'A', 'B', 'C'}
SLUG_RE = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
RANK_LABEL = {
 'A': 'ランクA（公式で現行条件まで確認済み）',
 'B': 'ランクB（公式情報だが現行性に不明点あり）',
 'C': 'ランクC（複数の外部情報で裏付けあり）',
 'D': 'ランクD（単独の利用者報告・参考情報）',
 'E': 'ランクE（未確認）',
}
NAV = [('/', 'トップ'), ('/games/', 'ゲーム一覧'), ('/about/', 'サイトについて'), ('/editorial-policy/', '編集・検証方針')]
FOOT_LINKS = [('/about/', 'サイトについて'), ('/editorial-policy/', '編集・検証方針'), ('/how-to-read/', '情報の見方')]
STATIC_PAGES = [('about/index.html', '/about/'), ('editorial-policy/index.html', '/editorial-policy/'), ('how-to-read/index.html', '/how-to-read/')]

BP = DEFAULT_BASE_PATH   # ベースパス（resolve_base で確定）
BASE = ''                # canonical用の完全な接頭辞 https://host + BP（ホスト未確定時は空）


def e(v):
 return html.escape(str(v if v is not None else ''), quote=True)


def resolve_base():
 raw_url = os.environ.get('S07_SITE_BASE_URL', '').strip().rstrip('/')
 env_path = os.environ.get('S07_SITE_BASE_PATH', '').strip()
 origin = ''
 url_path = ''
 if raw_url:
  u = urlparse(raw_url)
  if u.scheme != 'https' or not u.netloc or u.query or u.fragment:
   raise SystemExit('ERROR: S07_SITE_BASE_URLは https://host[/path] の形式で指定してください（query・fragment不可）')
  origin = f'{u.scheme}://{u.netloc}'
  url_path = u.path.rstrip('/')
 if env_path:
  if not env_path.startswith('/') or '://' in env_path:
   raise SystemExit('ERROR: S07_SITE_BASE_PATHは /path の形式で指定してください')
  bp = env_path.rstrip('/') or '/'
 elif url_path:
  bp = url_path
 else:
  bp = DEFAULT_BASE_PATH
 if bp == '/':
  bp = ''
 if url_path and bp != url_path:
  raise SystemExit('ERROR: S07_SITE_BASE_PATH と S07_SITE_BASE_URL のパスが一致しません')
 return bp, (origin + bp) if origin else ''


def run_validate():
 r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'validate_data.py')], capture_output=True, text=True)
 if r.stdout:
  sys.stdout.write(r.stdout if r.stdout.endswith('\n') else r.stdout + '\n')
 if r.returncode != 0:
  if r.stderr:
   sys.stderr.write(r.stderr)
  raise SystemExit('ERROR: データ検証に失敗したため生成を中止しました')


def load(name):
 p = DATA / (name + '.json')
 if not p.exists():
  return []
 try:
  value = json.loads(p.read_text(encoding='utf-8'))
 except Exception as ex:
  raise SystemExit(f'ERROR: {p.name} 読込失敗: {ex}')
 if not isinstance(value, list):
  raise SystemExit(f'ERROR: {p.name} の最上位は配列必須')
 return value


# ---------- 共通レイアウト ----------
def ga4_snippet():
 return ('<!-- Google tag (gtag.js) -->\n'
         f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>\n'
         f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA4_ID}');</script>")


def favicon_links():
 # ファビコン実ファイルはリポジトリ直下（サイトルート）に配置し、ci_build.sh が dist へコピーする
 return '\n'.join([
  f'<link rel="icon" href="{BP}/favicon.ico" sizes="any">',
  f'<link rel="icon" type="image/png" sizes="16x16" href="{BP}/favicon-16.png">',
  f'<link rel="icon" type="image/png" sizes="32x32" href="{BP}/favicon-32.png">',
  f'<link rel="apple-touch-icon" sizes="180x180" href="{BP}/favicon-180.png">',
  f'<link rel="icon" type="image/png" sizes="192x192" href="{BP}/favicon-192.png">',
  f'<link rel="icon" type="image/png" sizes="512x512" href="{BP}/favicon-512.png">'])


def logo_img(cls):
 # ヘッダー用ロゴ（青いQシンボル）。実ファイルはリポジトリ直下の logo-symbol.png
 return f'<img class="{cls}" src="{BP}/logo-symbol.png" alt="" width="256" height="256">'


def jsonld(obj):
 if obj is None:
  return ''
 text = json.dumps(obj, ensure_ascii=False).replace('</', '<\\/')
 return f'<script type="application/ld+json">{text}</script>'


# ---------- OGP・Twitterカード・画像寸法 ----------
OG_COMMON_IMAGE_PATH = '/img/hero-main-a.webp'  # ブランド共通の代表画像（実寸1600x900）
OG_COMMON_IMAGE_SIZE = (1600, 900)
LOGO_SYMBOL_SIZE = (256, 256)  # logo-symbol.png の実寸（logo_img の宣言と同一）
ICONS = {}  # main() で data/icons.json を設定する


def image_size(data):
 """PNG/JPEG/GIF/WebP のバイト列から (width, height) を返す。判定できなければ None。"""
 if not data or len(data) < 30:
  return None
 if data[:8] == b'\x89PNG\r\n\x1a\n':
  return struct.unpack('>II', data[16:24])
 if data[:6] in (b'GIF87a', b'GIF89a'):
  return struct.unpack('<HH', data[6:10])
 if data[:2] == b'\xff\xd8':
  i = 2
  while i + 9 < len(data):
   if data[i] != 0xFF:
    i += 1
    continue
   marker = data[i + 1]
   if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
    h, w = struct.unpack('>HH', data[i + 5:i + 9])
    return (w, h)
   if marker == 0x01 or 0xD0 <= marker <= 0xD9:
    i += 2
    continue
   i += 2 + struct.unpack('>H', data[i + 2:i + 4])[0]
  return None
 if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
  fmt = data[12:16]
  if fmt == b'VP8X':
   return (int.from_bytes(data[24:27], 'little') + 1, int.from_bytes(data[27:30], 'little') + 1)
  if fmt == b'VP8 ':
   return (struct.unpack('<H', data[26:28])[0] & 0x3FFF, struct.unpack('<H', data[28:30])[0] & 0x3FFF)
  if fmt == b'VP8L':
   bits = int.from_bytes(data[21:25], 'little')
   return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
 return None


def b64_image_size(path):
 """static-perfect / pages-assets の .b64 ファイルから画像寸法を読む。"""
 try:
  raw = re.sub(r'\s+', '', Path(path).read_text(encoding='ascii'))
  return image_size(base64.b64decode(raw))
 except Exception:
  return None


def data_uri_size(src):
 """data:image/...;base64,... の先頭バイトから画像寸法を読む。"""
 try:
  payload = src.split(',', 1)[1]
  payload = payload[:len(payload) // 4 * 4]
  return image_size(base64.b64decode(payload))
 except Exception:
  return None


def store_image_size(url):
 """ストア配信画像のURLに寸法トークンが含まれる場合に読み取る。"""
 m = re.search(r'/(\d+)x(\d+)bb\.', url)
 if m:
  return (int(m.group(1)), int(m.group(2)))
 m = re.search(r'=w(\d+)-h(\d+)', url)
 if m:
  return (int(m.group(1)), int(m.group(2)))
 return None


def social_meta(title, desc, canonical_path, image_url=None, image_size=None, og_type='article'):
 """OGP／Twitterカードの meta 群。絶対URL（BASE）が確定している場合のみ出力する。"""
 if not BASE or canonical_path is None:
  return ''
 if image_url is None:
  image_url = BASE + OG_COMMON_IMAGE_PATH
  image_size = OG_COMMON_IMAGE_SIZE
 parts = [f'<meta property="og:type" content="{og_type}">',
          '<meta property="og:site_name" content="ポイゲークエスト">',
          '<meta property="og:locale" content="ja_JP">',
          f'<meta property="og:title" content="{e(title)}">']
 if desc:
  parts.append(f'<meta property="og:description" content="{e(desc)}">')
 parts.append(f'<meta property="og:url" content="{e(BASE + canonical_path)}">')
 parts.append(f'<meta property="og:image" content="{e(image_url)}">')
 if image_size:
  parts.append(f'<meta property="og:image:width" content="{image_size[0]}">')
  parts.append(f'<meta property="og:image:height" content="{image_size[1]}">')
 parts.append('<meta name="twitter:card" content="summary_large_image">')
 parts.append(f'<meta name="twitter:title" content="{e(title)}">')
 if desc:
  parts.append(f'<meta name="twitter:description" content="{e(desc)}">')
 parts.append(f'<meta name="twitter:image" content="{e(image_url)}">')
 return '\n'.join(parts)


def game_og_image(gid):
 """生成ゲームページ用の og:image（そのゲームのアイコン。無ければ共通画像に任せる）。"""
 url = icon_url(ICONS, gid)
 if url:
  return url, store_image_size(url)
 return None, None


def add_img_dims(text, resolver):
 """<img> に実寸の width/height が無ければ resolver(src) で寸法を付与する（script内は対象外）。"""
 def sub(m):
  tag = m.group(0)
  if re.search(r'\bwidth\s*=', tag):
   return tag
  sm = re.search(r'src="([^"]+)"', tag)
  if not sm:
   return tag
  size = resolver(sm.group(1))
  if not size:
   return tag
  return tag.replace('<img', f'<img width="{size[0]}" height="{size[1]}"', 1)
 chunks = re.split(r'(<script\b[^>]*>.*?</script>)', text, flags=re.S)
 for i in range(0, len(chunks), 2):
  chunks[i] = re.sub(r'<img\b[^>]*>', sub, chunks[i])
 return ''.join(chunks)


def page_head(title, desc, robots, canonical_path=None, ld=None, og_image=None, og_image_size=None, og_type='article'):
 parts = ['<!doctype html>', '<html lang="ja"><head>', '<meta charset="utf-8">',
          '<meta name="viewport" content="width=device-width, initial-scale=1">',
          f'<title>{e(title)}</title>',
          f'<meta name="description" content="{e(desc)}">',
          f'<meta name="robots" content="{robots}">']
 parts.append(favicon_links())
 if canonical_path is not None and BASE:
  parts.append(f'<link rel="canonical" href="{e(BASE + canonical_path)}">')
  sm = social_meta(title, desc, canonical_path, og_image, og_image_size, og_type)
  if sm:
   parts.append(sm)
 parts.append(f'<link rel="stylesheet" href="{BP}/assets/site.css">')
 parts.append(ga4_snippet())
 parts.append(f'<script src="{BP}/assets/site.js" defer></script>')
 if ld:
  parts.append(jsonld(ld))
 parts.append('</head>')
 return '\n'.join(parts)


def site_header():
 links = ''.join(f'<a href="{BP}{p}">{t}</a>' for p, t in NAV)
 return (f'<header><div class="wrap head"><a class="brand" href="{BP}/">{logo_img("lg-logo")}{SITE_NAME}</a>'
         f'<nav aria-label="メインナビゲーション">{links}</nav></div></header>')


def bottom_nav():
 links = ''.join(f'<a href="{BP}{p}">{t}</a>' for p, t in NAV)
 return f'<nav class="bottomnav" aria-label="モバイルナビゲーション">{links}</nav>'


def site_footer():
 links = ''.join(f'<a href="{BP}{p}">{t}</a>' for p, t in FOOT_LINKS)
 return ('<footer><div class="wrap">'
         f'<div class="footlinks">{links}</div>'
         '<p class="small">掲載情報は確認時点の内容です。案件条件・掲載状況はサービスや時期により変更される場合があります。</p>'
         '<p class="small">本サイトの案件リンクには、広告（紹介プログラム）のリンクが含まれる場合があります。</p>'
         '</div></footer>' + bottom_nav())


def page_shell(title, desc, robots, canonical_path, ld, body, og_image=None, og_image_size=None, og_type='article'):
 return page_head(title, desc, robots, canonical_path, ld, og_image, og_image_size, og_type) + '\n<body>\n' + site_header() + '\n' + body + '\n' + site_footer() + '\n</body></html>\n'


def breadcrumb(items):
 """items: [(label, path or None), ...] 表示と構造化データで同じ内容を使う。"""
 parts = []
 for label, path in items:
  parts.append(f'<a href="{BP}{path}">{e(label)}</a>' if path else e(label))
 return '<nav class="breadcrumb" aria-label="パンくず">' + ' &gt; '.join(parts) + '</nav>'


def breadcrumb_ld(items, current_path):
 if not BASE:
  return None
 elements = []
 for i, (label, path) in enumerate(items):
  elements.append({'@type': 'ListItem', 'position': i + 1, 'name': label, 'item': BASE + (path or current_path)})
 return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': elements}


def rank_badge(rank):
 if rank not in RANK_LABEL:
  return ''
 return f'<span class="badge badge-rank">情報{RANK_LABEL[rank]}</span>'


def campaign_status_badge(status):
 cls = {'掲載中': 'badge-ok', '再開': 'badge-info', '変更': 'badge-warn', '終了': 'badge-end', '確認不能': 'badge-warn',
        'active': 'badge-ok', 'reopened': 'badge-info', 'changed': 'badge-warn', 'ended': 'badge-end', 'unknown': 'badge-warn'}.get(status, 'badge-info')
 return f'<span class="badge {cls}">案件状態：{e(status)}</span>'


def source_block(src):
 if not src:
  return ''
 rows = [f'<p class="small">発信元：{e(src.get("publisher"))}／情報区分：{e(src.get("source_type"))}</p>']
 url = src.get('url') or ''
 title = src.get('title') or url
 rows.append(f'<p class="small">出典：<a href="{e(url)}" rel="nofollow noopener">{e(title)}</a></p>')
 meta = []
 if src.get('published_at'):
  meta.append('公開日：' + e(src['published_at']))
 if src.get('checked_at'):
  meta.append('確認日：' + e(src['checked_at']))
 if src.get('game_version'):
  meta.append('対象バージョン：' + e(src['game_version']))
 if meta:
  rows.append('<p class="small">' + '／'.join(meta) + '</p>')
 if src.get('conditions'):
  rows.append(f'<p class="small">適用条件：{e(src["conditions"])}</p>')
 if src.get('limitations'):
  rows.append(f'<p class="small">制約・不確実性：{e(src["limitations"])}</p>')
 return '<div class="source">' + ''.join(rows) + '</div>'


def dl_rows(pairs):
 rows = ''.join(f'<dt>{e(k)}</dt><dd>{v}</dd>' for k, v in pairs if v not in (None, ''))
 return f'<dl>{rows}</dl>' if rows else ''


# ---------- 判定（生成とindexは分離する） ----------
def knowledge_body_len(k):
 total = len(str(k.get('conclusion') or ''))
 steps = k.get('steps')
 if isinstance(steps, list):
  for s in steps:
   if isinstance(s, dict):
    total += len(str(s.get('heading') or '')) + len(str(s.get('text') or ''))
 return total


def game_indexable(g, ks, sources_by_id):
 """ゲーム詳細のindex判定（G01/G02/G03/G04/G06。G07/G08は構成上担保）"""
 if g.get('eligibility_status') not in ELIGIBLE:
  return False
 if not (g.get('official_title') and g.get('publisher') and g.get('official_game_url')):
  return False  # G02
 if g.get('info_rank') not in INDEXABLE_RANKS:
  return False  # G04/G11
 if not g.get('wiki_summary') or not g.get('last_checked_at'):
  return False  # G03/G06
 if not ks or sum(knowledge_body_len(k) for k in ks) < 100:
  return False  # G03
 for k in ks:  # G04
  if k.get('source_id') not in sources_by_id or not k.get('checked_at') or k.get('info_rank') not in INDEXABLE_RANKS:
   return False
 return True


def topic_indexable(k, sources_by_id):
 if not k.get('conclusion') or not k.get('checked_at'):
  return False
 if k.get('info_rank') not in INDEXABLE_RANKS:
  return False
 if k.get('source_id') not in sources_by_id:
  return False
 return knowledge_body_len(k) >= 100


def conditions_indexable(g, cs, sources_by_id):
 """条件ページは原則noindex。根拠が公式（ランクA）で揃い、対象バージョンが分かる場合だけindex。"""
 if not cs or not g.get('game_version'):
  return False
 for c in cs:
  if c.get('info_rank') != 'A' or not c.get('campaign_url') or not c.get('checked_at'):
   return False
  if c.get('source_id') not in sources_by_id:
   return False
 return True


# ---------- 部品 ----------
def icon_url(icons, gid):
 if not icons:
  return ''
 ent = icons.get(gid)
 if isinstance(ent, dict):
  inner = ent.get('icon')
  if isinstance(inner, dict):
   return inner.get('icon') or ''
  return ent.get('icon') if isinstance(ent.get('icon'), str) else ''
 return ent if isinstance(ent, str) else ''


def game_card(g, cs, icons=None):
 badges = ''
 if any(c.get('campaign_status') in ACTIVE_STATUS for c in cs):
  badges = '<p><span class="badge badge-ok">掲載確認済みの案件あり</span></p>'
 elif cs:
  badges = '<p><span class="badge badge-end">現行案件なし（過去の記録）</span></p>'
 icon = ''
 _iu = icon_url(icons, g['game_id'])
 if _iu:
  icon = f'<img class="game-icon" src="{e(_iu)}" alt="" loading="lazy" width="44" height="44">'
 return (f'<article class="card game-card js-filter-item" data-name="{e(g["official_title"])} {e(g["slug"])}">'
         f'{icon}'
         f'<h3><a href="{BP}/games/{e(g["slug"])}/">{e(g["official_title"])}のポイ活攻略</a></h3>'
         f'<p>{e(g["wiki_summary"])}</p>'
         f'<p class="small muted">最終確認：{e(g.get("last_checked_at"))}</p>{badges}</article>')


def ended_notice_html(g, ks, rail_games, icons=None):
 """案件が全て終了したゲームの詳細ページに出す標準お知らせ部品。
    見出し画像（共通）＋お知らせパネル＋他ゲームの案件レール。
    攻略セクション自体は残し、案件表示だけをこの形に切り替える。"""
 slug = g['slug']
 title = e(g['official_title'])
 guide_line = ('下の「攻略テーマ」から、各攻略ページへそのまま進めます。' if ks
               else 'このページに掲載している攻略情報は、これまで通り読めます。')
 parts = [f'<figure class="nc-fig"><img src="{BP}/img/notice-ended.webp" alt="ポイ活案件の掲載は終了しました（お知らせ）" loading="lazy" width="1280" height="720"></figure>',
          '<div class="nc-panel">'
          '<p class="nc-phead">現在搭載の案件が終了した可能性があり更新されていません</p>'
          '<div class="nc-row"><div class="nc-ic">📢</div><div class="nc-tx"><h4>現在、ご案内できる案件はありません</h4>'
          f'<p>{title}のポイ活案件は、現在ご案内できる掲載がありません。新しい案件が確認でき次第、このページでお知らせします。</p></div></div>'
          '<div class="nc-row"><div class="nc-ic">📖</div><div class="nc-tx"><h4>攻略ページはこれまで通り読めます</h4>'
          f'<p>{guide_line}</p></div></div>'
          '<div class="nc-row"><div class="nc-ic">🗂️</div><div class="nc-tx"><h4>終了した案件の記録について</h4>'
          f'<p>終了した案件の条件・ステップは、<a href="{BP}/games/{e(slug)}/conditions/">案件条件の詳細</a>に当時の記録として残しています（申込導線は設置していません）。</p></div></div>'
          '</div>']
 tiles = []
 for rg, rcs in (rail_games or []):
  if rg['game_id'] == g['game_id']:
   continue
  amt = max_reward(rg['game_id'], {rg['game_id']: rcs})
  if not amt:
   continue
  iu = icon_url(icons, rg['game_id'])
  img = f'<img src="{e(iu)}" alt="" loading="lazy" width="76" height="76">' if iu else ''
  tiles.append(f'<a class="tile" href="{BP}/games/{e(rg["slug"])}/">{img}'
               f'<span class="tname">{e(rg["official_title"])}</span>'
               f'<span class="tpt">最大{amt:,}円相当</span></a>')
  if len(tiles) >= 3:
   break
 if tiles:
  parts.append('<section class="panel"><h2>いま挑戦できる他のゲームの案件</h2>'
               '<div class="rail nc-rail">' + ''.join(tiles) + '</div>'
               f'<p><a href="{BP}/games/">ゲーム一覧で他の案件を探す →</a></p></section>')
 return ''.join(parts)


def search_block(input_id):
 return ('<form class="search" data-game-search role="search" aria-label="ゲーム名検索">'
         f'<label class="visually-hidden" for="{input_id}">ゲーム名で検索</label>'
         f'<input id="{input_id}" type="search" name="q" placeholder="ゲーム名を入力" autocomplete="off">'
         '<button type="submit">検索</button></form>'
         '<p class="small muted" data-search-count></p>'
         '<p class="muted" data-search-empty hidden>該当するゲームが見つかりませんでした。</p>')


def history_list(entries):
 if not entries:
  return ''
 items = []
 for h in sorted(entries, key=lambda x: str(x.get('changed_at') or ''), reverse=True):
  detail = e(h.get('change_type'))
  if h.get('field'):
   detail += '（' + e(h['field']) + '）'
  if h.get('old_value') or h.get('new_value'):
   detail += '：' + e(h.get('old_value') or '―') + ' → ' + e(h.get('new_value') or '―')
  if h.get('note'):
   detail += '。' + e(h['note'])
  items.append(f'<li>{e(h.get("changed_at"))}：{detail}</li>')
 return '<ul class="clean">' + ''.join(items) + '</ul>'


# ---------- ページ生成 ----------
def max_reward(gid, campaigns_by_game):
 best = 0
 for c in campaigns_by_game.get(gid, []):
  if c.get('campaign_status') not in ACTIVE_STATUS:
   continue
  texts = [c.get('reward_amount') or ''] + list(c.get('reward_stages') or [])
  for t in texts:
   for m in re.finditer(r'([\d][\d,]*)\s*(?:pt|P|円)', t or ''):
    best = max(best, int(m.group(1).replace(',', '')))
 return best


TOP_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Hiragino Kaku Gothic ProN","Hiragino Sans","Noto Sans JP",sans-serif;color:#333;font-size:14px;line-height:1.6;-webkit-text-size-adjust:100%;background:#fff}
a{color:#3977B8}
.page{margin:0 auto;background:#fff;min-height:100vh}
.header{position:sticky;top:0;z-index:60;background:#fff;border-bottom:1px solid #e5e5e5}
.hrow{display:flex;align-items:center;padding:9px 12px}
.logo{font-size:20px;font-weight:900;color:#333;white-space:nowrap}
.lg-mark{display:inline-block;background:#ff6900;color:#fff;border-radius:5px;padding:0 6px;margin-right:5px;font-size:18px}
.lg-logo{width:34px;height:34px;vertical-align:-9px;margin-right:6px;border-radius:7px}
.lg-sub{font-size:9px;font-weight:700;color:#ff6900;vertical-align:super;margin-left:3px}
.gnav{display:flex;border-top:1px solid #f0f0f0;overflow-x:auto;white-space:nowrap}
.gnav a{flex:1;text-align:center;padding:8px 4px;font-size:12.5px;font-weight:700;color:#333;text-decoration:none;border-bottom:3px solid transparent}
.hero{padding:14px 12px 4px}
.hero h1{font-size:21px;font-weight:900;line-height:1.35}
.hero .lead{margin-top:6px;font-size:13px;color:#444}
.search{padding:10px 12px 2px}
.search form{display:flex;gap:6px}
.search input{flex:1;padding:9px 10px;border:1px solid #cfd8e3;border-radius:8px;font-size:14px;min-width:0}
.search button{padding:9px 14px;border:0;border-radius:8px;background:#172B49;color:#fff;font-weight:700}
.search .small{font-size:11.5px;color:#888;margin-top:5px}
.sec{padding:14px 0 4px}
.sec-head{display:flex;align-items:center;justify-content:space-between;background:#fdf3e3;border-left:5px solid #ff6900;padding:7px 10px 7px 9px;margin:0 0 10px}
.sec-head h2{font-size:16px;font-weight:800}
.sec-head a{font-size:12px;font-weight:700;text-decoration:none}
.pop-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px 6px;padding:0 12px}
.pop-tile{display:flex;flex-direction:column;align-items:center;gap:3px;text-decoration:none;color:#333;text-align:center}
.pop-icon{width:56px;height:56px;border-radius:14px;border:1px solid #e5e5e5}
.pop-initial{display:flex;align-items:center;justify-content:center;width:56px;height:56px;border-radius:14px;background:#EAF2FC;color:#172B49;font-size:22px;font-weight:900}
.pop-name{font-size:11px;font-weight:700;line-height:1.3}
.pop-amt{font-size:10px;font-weight:800;color:#e05e00}
.rank-list{list-style:none;padding:0 12px}
.rank-list li{border-bottom:1px solid #eee}
.rank-list a{display:flex;align-items:center;gap:8px;padding:8px 2px;text-decoration:none;color:#333}
.rank-no{flex:0 0 22px;height:22px;border-radius:50%;background:#172B49;color:#fff;font-size:12px;font-weight:900;display:flex;align-items:center;justify-content:center}
.rank-icon{width:34px;height:34px;border-radius:9px;border:1px solid #e5e5e5}
.rank-name{flex:1;font-weight:700;font-size:13px}
.rank-amt{font-weight:900;color:#e05e00;font-size:13px;white-space:nowrap}
.updates{list-style:none;padding:0 12px}
.updates li{padding:6px 0;border-bottom:1px dotted #ddd;font-size:13px}
.grid{display:grid;grid-template-columns:1fr;gap:10px;padding:0 12px}
.card{border:1px solid #e5e5e5;border-radius:10px;padding:12px;background:#fff;overflow:hidden}
.card h3{font-size:15px;margin-bottom:4px}
.card h3 a{color:#172B49;text-decoration:none}
.card p{font-size:12.5px;color:#444}
.small{font-size:11.5px}.muted{color:#888}
.badge{display:inline-block;font-size:10.5px;font-weight:800;border-radius:3px;padding:1px 6px}
.badge-ok{background:#E9F5EF;color:#1d7a4c}.badge-end{background:#f0f0f0;color:#777}
.game-icon{width:44px;height:44px;border-radius:10px;float:left;margin:2px 10px 6px 0}
.guide-links{display:grid;grid-template-columns:1fr;gap:8px;padding:0 12px}
.guide-links a{display:block;border:1px solid #e3ddf2;background:#F0ECFA;color:#463a75;border-radius:10px;padding:11px 12px;font-weight:800;text-decoration:none}
.guide-links a span{float:right;color:#7a68b8}
.footer{margin-top:30px;background:#f7f7f7;border-top:1px solid #e5e5e5;padding:16px 12px 28px}
.footer nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin-bottom:10px}
.footer nav a{font-size:12px;color:#3977B8;text-decoration:none}
.footer p{font-size:11px;color:#888;line-height:1.7}
.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
"""


def build_top(games, campaigns_by_game, knowledge_by_game, history, icons=None):
 icons = icons or {}
 title = 'ポイゲークエスト｜ポイ活ゲームの攻略・案件条件まとめ'
 desc = 'ポイ活ゲームのおすすめ案件を、条件・到達ステップ・攻略情報までゲームごとに整理した攻略Wiki「ポイゲークエスト」。ポイントが高い順のランキングと比較、ゲーム名検索から条件を確認できます。'
 robots = 'index,follow' if games else 'noindex,follow'
 head = ['<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width, initial-scale=1">',
         f'<title>{e(title)}</title>',
         f'<meta name="description" content="{e(desc)}">',
         f'<meta name="robots" content="{robots}">']
 head.append(favicon_links())
 if BASE:
  head.append(f'<link rel="canonical" href="{e(BASE + "/")}">')
  sm = social_meta(title, desc, '/', None, None, 'website')
  if sm:
   head.append(sm)
 head.append(ga4_snippet())
 head.append(f'<script src="{BP}/assets/site.js" defer></script>')
 if BASE:
  ld = {'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'ポイゲークエスト', 'url': BASE + '/'}
  head.append(f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>')
 head.append(f'<style>{TOP_CSS}</style>')
 head.append('</head>')

 def amt(g):
  return max_reward(g['game_id'], campaigns_by_game)

 def icon_img(g, cls):
  url = icon_url(icons, g['game_id'])
  if url:
   return f'<img class="{cls}" src="{e(url)}" alt="" loading="lazy">'
  return f'<span class="pop-initial" aria-hidden="true">{e(str(g["official_title"])[:1])}</span>'

 ranked = sorted(games, key=lambda g: (-amt(g), str(g['official_title'])))
 popular = [g for g in ranked if amt(g) > 0][:8] or ranked[:8]
 pop_tiles = ''.join(
  f'<a class="pop-tile" href="{BP}/games/{g["slug"]}/">{icon_img(g, "pop-icon")}'
  f'<span class="pop-name">{e(g["official_title"])}</span>'
  + (f'<span class="pop-amt">最大{amt(g):,}円相当</span>' if amt(g) else '')
  + '</a>' for g in popular)
 rank_rows = ''.join(
  f'<li><a href="{BP}/games/{g["slug"]}/"><span class="rank-no">{i}</span>{icon_img(g, "rank-icon")}'
  f'<span class="rank-name">{e(g["official_title"])}</span>'
  f'<span class="rank-amt">{amt(g):,}円相当</span></a></li>'
  for i, g in enumerate([g for g in ranked if amt(g) > 0][:10], 1))
 camp_game = {}
 for gid, cs in campaigns_by_game.items():
  for c in cs:
   camp_game[c['campaign_id']] = gid
 titles = {g['game_id']: g['official_title'] for g in games}
 slugs = {g['game_id']: g['slug'] for g in games}
 events = []
 for h in history:
  events.append((str(h.get('changed_at') or ''), '条件変更', h['campaign_id']))
 known = {h['campaign_id'] for h in history}
 for cs in campaigns_by_game.values():
  for c in cs:
   if c['campaign_id'] not in known:
    events.append((str(c.get('last_checked_at') or ''), '案件情報を確認', c['campaign_id']))
 events.sort(key=lambda x: x[0], reverse=True)
 ev_items = ''
 for d, label, cid in events[:6]:
  gid = camp_game.get(cid)
  if not gid or gid not in titles:
   continue
  ev_items += f'<li><a href="{BP}/games/{slugs[gid]}/">{e(titles[gid])}</a>：{label}（{e(d)}）</li>'

 header = ('<header class="header"><div class="hrow"><div class="logo">'
           f'{logo_img("lg-logo")}ポイゲークエスト<span class="lg-sub">POIKATSU GAME WIKI</span></div></div>'
           '<nav class="gnav">'
           '<a href="#popular">人気ゲーム</a><a href="#updates">新着・更新</a>'
           f'<a href="#ranking">ランキング</a><a href="{BP}/games/">ゲーム一覧</a>'
           '</nav></header>')
 hero = ('<div class="hero"><h1>ポイ活ゲーム攻略Wiki「ポイゲークエスト」</h1>'
         '<p class="lead">ポイ活で遊べるゲームの案件条件・到達ステップ・攻略情報を、ゲームごとに整理しています。ゲームポイ活とは、ポイントサイトの案件として掲載されているゲームを遊び、達成条件を満たすとポイントが付く仕組みです。条件は公式掲載を確認した時点の情報です。</p></div>')
 search = f'<div class="search">{search_block("search-top")}</div>'
 if games:
  sections = f'<section class="sec" id="popular"><div class="sec-head"><h2>人気のポイ活ゲーム</h2><a href="{BP}/games/">ゲーム一覧 ＞</a></div><div class="pop-grid">{pop_tiles}</div></section>'
  if not rank_rows:
   rank_rows = '<li class="muted" style="padding:8px 2px">ポイント額を確認できた案件はまだありません。</li>'
  sections += f'<section class="sec" id="ranking"><div class="sec-head"><h2>ポイ活ゲームランキング（ポイントが高い順）</h2></div><ol class="rank-list">{rank_rows}</ol></section>'
  if ev_items:
   sections += f'<section class="sec" id="updates"><div class="sec-head"><h2>新着・更新</h2></div><ul class="updates">{ev_items}</ul></section>'
  cards = ''.join(game_card(g, campaigns_by_game.get(g['game_id'], []), icons) for g in sorted(games, key=lambda x: str(x['official_title'])))
  sections += f'<section class="sec" id="games"><div class="sec-head"><h2>全ゲーム一覧</h2></div><div class="grid">{cards}</div></section>'
 else:
  sections = '<p class="muted" style="padding:4px 12px">現在、公開基準を満たしたゲーム情報はありません。対象ゲームの確認が完了したものから掲載します。</p>'
 sections += (f'<section class="sec"><div class="sec-head"><h2>サイトの案内</h2></div><div class="guide-links">'
              f'<a href="{BP}/how-to-read/">案件条件の見方<span>＞</span></a>'
              f'<a href="{BP}/editorial-policy/">編集方針<span>＞</span></a>'
              f'<a href="{BP}/about/">このサイトについて<span>＞</span></a></div></section>')
 footer = ('<footer class="footer"><nav>'
           f'<a href="{BP}/games/">ゲーム一覧</a><a href="#ranking">ポイントが高い順</a>'
           f'<a href="{BP}/how-to-read/">案件条件の見方</a><a href="{BP}/editorial-policy/">編集方針</a>'
           f'<a href="{BP}/about/">このサイトについて</a></nav>'
           '<p>掲載している金額・条件は、各ポイントサイトの公式掲載を確認した時点の情報です。最新の条件は各ポイントサイトでご確認ください。</p>'
           '<p>© ポイゲークエスト</p></footer>')
 body = f'<body><div class="page">{header}{hero}{search}<main>{sections}</main>{footer}</div></body></html>'
 return '\n'.join(head) + '\n' + body
GENRE_GROUPS = [('パズルゲーム', ['puzzles-and-survival', 'puzzles-and-conquest', 'puzzles-and-chaos', 'color-link']),
                ('放置ゲーム', ['kinoko-densetsu', 'hero-wars-alliance'])]


def build_list(visible, campaigns_by_game, any_indexable, icons=None):
 cards = [game_card(g, campaigns_by_game.get(g['game_id'], []), icons) for g in sorted(visible, key=lambda x: str(x['official_title']))]
 if cards:
  body_cards = '<div class="grid">' + ''.join(cards) + '</div>'
 else:
  body_cards = '<p class="muted">現在、公開基準を満たしたゲーム情報はありません。対象ゲームの確認が完了したものから掲載します。</p>'
 robots = 'index,follow' if (visible and any_indexable) else 'noindex,follow'
 by_slug = {g['slug']: g for g in visible}
 genre_html = ''
 for genre, slugs in GENRE_GROUPS:
  members = [by_slug[s] for s in slugs if s in by_slug]
  if not members:
   continue
  links = ''.join(f'<li><a href="{BP}/games/{e(m["slug"])}/">{e(m["official_title"])}のポイ活攻略</a></li>' for m in members)
  genre_html += f'<h3>{e(genre)}</h3><ul class="clean">{links}</ul>'
 if genre_html:
  genre_html = f'<section aria-label="ジャンル別"><h2>ジャンルで探す</h2>{genre_html}</section>'
 body = ('<main class="wrap">' + breadcrumb([('トップ', '/'), ('ゲーム一覧', None)])
         + '<h1>ポイ活ゲーム一覧</h1><p>対象サービスでの掲載と公開基準を確認できたゲームを掲載しています。パズルゲームや放置ゲームなど、ジャンル別の入口も用意しています。</p>'
         + search_block('search-list')
         + f'<section aria-label="公開中のゲーム"><h2>掲載中のゲーム</h2>{body_cards}</section>'
         + genre_html + '</main>')
 ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': 'ポイ活ゲーム一覧', 'url': BASE + '/games/'} if BASE else None
 return page_shell('ポイ活ゲームの一覧・検索｜ポイ活ゲーム攻略Wiki',
                   'ポイ活ゲームの案件・攻略情報を一覧で検索できます。パズルゲームや放置ゲームなど、遊びたいゲームの達成条件・最大ポイントをゲームごとに確認できます。',
                   robots, '/games/', ld, body, og_type='website'), robots


def build_detail(g, ks, cs, history_entries, sources_by_id, rail_games=None, icons=None):
 slug = g['slug']
 title = g['official_title']
 alias = str(g.get('search_alias') or '').strip()
 title_name = f'{title}（{alias}）' if alias and alias not in title else title
 active_cs = [c for c in cs if c.get('campaign_status') in ACTIVE_STATUS]
 service_names = list(dict.fromkeys(str(c.get('service_name')) for c in active_cs if c.get('service_name')))
 staged = any(c.get('reward_stages') for c in cs)
 cond_label = '案件条件・ステップ一覧' if staged else '案件条件・確認記録'
 pairs = [('運営・配信元', e(g.get('publisher') or '未確認')),
          ('対応OS', e(g.get('supported_os') or '未確認')),
          ('対象バージョン', e(g.get('game_version') or '未確認')),
          ('公式情報', f'<a href="{e(g["official_game_url"])}" rel="nofollow noopener">公式ページ</a>'),
          ('対象掲載根拠', f'<a href="{e(g["eligibility_evidence"])}" rel="nofollow noopener">掲載確認元</a>'),
          ('最終確認', e(g.get('last_checked_at')))]
 sections = ['<section class="panel"><h2>ゲーム基本情報</h2>' + dl_rows(pairs)
             + f'<p>{rank_badge(g.get("info_rank"))}</p></section>']
 if ks:
  points = []
  for k in ks:
   points.append(f'<li><a href="{BP}/games/{e(slug)}/{e(k["topic_slug"])}/">{e(k["topic"])}</a>：{e(k.get("conclusion"))}</li>')
  sections.append('<section class="panel"><h2>攻略の要点</h2><ul class="clean">' + ''.join(points) + '</ul></section>')
  links = ''.join(f'<li><a href="{BP}/games/{e(slug)}/{e(k["topic_slug"])}/">{e(topic_title(k))}</a></li>' for k in ks)
  sections.append('<section class="panel"><h2>攻略テーマ</h2><ul class="clean">' + links + '</ul></section>')
 active = [c for c in cs if c.get('campaign_status') in ACTIVE_STATUS]
 if cs and not active:
  # 案件が全て終了したゲーム：攻略は残し、案件表示をお知らせ部品に切り替える
  sections.append(ended_notice_html(g, ks, rail_games, icons))
 elif cs:
  rows = []
  for c in active:
   rows.append(f'<li>{e(c.get("service_name"))}：{e(c.get("campaign_title"))}'
               + (f'（報酬：{e(c["reward_amount"])}）' if c.get('reward_amount') else '')
               + (f'（期限：{e(c["deadline"])}）' if c.get('deadline') else '')
               + f' {campaign_status_badge(c.get("campaign_status"))}</li>')
  note = ''.join(rows) if rows else '<li>現在、掲載中の案件はありません。</li>'
  sections.append('<section class="panel"><h2>ポイ活案件情報（サービス別）</h2><ul class="clean">' + note + '</ul>'
                  f'<p><a href="{BP}/games/{e(slug)}/conditions/">案件条件の詳細を確認する →</a></p></section>')
 cautions = []
 for k in ks:
  if k.get('cautions') and k['cautions'] not in cautions:
   cautions.append(k['cautions'])
 if cautions:
  sections.append('<section class="panel"><h2>注意点</h2>' + ''.join(f'<p>{e(c)}</p>' for c in cautions) + '</section>')
 used_sources = []
 for k in ks:
  s = sources_by_id.get(k.get('source_id'))
  if s and s not in used_sources:
   used_sources.append(s)
 for c in cs:
  s = sources_by_id.get(c.get('source_id'))
  if s and s not in used_sources:
   used_sources.append(s)
 if used_sources:
  sections.append('<section class="panel"><h2>出典・確認記録</h2>' + ''.join(source_block(s) for s in used_sources) + '</section>')
 if history_entries:
  sections.append('<section class="panel"><h2>更新履歴</h2>' + history_list(history_entries) + '</section>')
 related = [f'<li><a href="{BP}/games/">ゲーム一覧</a></li>']
 if cs:
  related.insert(0, f'<li><a href="{BP}/games/{e(slug)}/conditions/">{e(title)}の{e(cond_label)}</a></li>')
 sections.append('<section class="panel"><h2>関連ページ</h2><ul class="clean">' + ''.join(related) + '</ul></section>')
 indexable = game_indexable(g, ks, sources_by_id)
 robots = 'index,follow' if indexable else 'noindex,follow'
 crumbs = [('トップ', '/'), ('ゲーム一覧', '/games/'), (title, None)]
 ld = breadcrumb_ld(crumbs, f'/games/{slug}/')
 intro = ''
 if active_cs and service_names:
  intro = (f'<p>ポイ活で始める場合、このゲームの案件は{"・".join(service_names)}に掲載されています。'
           f'掲載先によって最大ポイントや達成条件が異なるため、始める前に<a href="{BP}/games/{e(slug)}/conditions/">{e(title)}の{e(cond_label)}</a>で比較するのがおすすめです。'
           '案件ページを経由してインストールし、期限内に条件を達成するとポイントが付きます。</p>')
 body = ('<main class="wrap">' + breadcrumb(crumbs)
         + f'<h1>{e(title_name)}のポイ活攻略</h1><p class="lead">{e(g["wiki_summary"])}</p>'
         + intro
         + ''.join(sections) + '</main>')
 if active_cs and service_names:
  amt = max_reward(g['game_id'], {g['game_id']: cs})
  amt_part = f'最大{amt:,}円相当。' if amt else ''
  desc = f'{title_name}のポイ活攻略。{"・".join(service_names)}に案件掲載中、{amt_part}達成条件・ステップの進め方と、課金・無課金の注意点をまとめています。'
 else:
  desc = f'{title_name}のゲーム概要、ポイ活達成のポイント、関連攻略、確認済み情報をまとめます。'
 og_url, og_size = game_og_image(g['game_id'])
 page = page_shell(f'{title_name}のポイ活攻略｜達成条件・進め方・注意点',
                   desc,
                   robots, f'/games/{slug}/', ld, body, og_image=og_url, og_image_size=og_size)
 return page, indexable


def topic_title(k):
 """トピックの表示タイトル。名前に既に「進め方／やり方」が入っている場合は重ねない
 （「…への進め方の進め方・注意点」という重複の防止。2026-11-27 パズサバ見直し第2回で発見）。"""
 t = k['topic']
 if '進め方' in t or 'やり方' in t:
  return t + '・注意点'
 return t + 'の進め方・注意点'


def top_menu_html(g, k, siblings):
 """攻略ページ上部メニュー（案A・2026-11-27 ベース組み込み）。
 ゲームトップ＋同ゲームの全攻略トピックをタイル化し、現在ページに now を付ける。
 7件以上は折りたたみ（初期6件）。部品仕様は PARTS_SPEC（上部メニュー）。"""
 slug = g['slug']
 tiles = [f'<a href="{BP}/games/{e(slug)}/"><span class="tml">攻略トップ</span></a>']
 for sib in siblings:
  if sib.get('static_page'):
   continue
  cls = ' class="now"' if sib.get('knowledge_id') == k.get('knowledge_id') else ''
  tiles.append(f'<a href="{BP}/games/{e(slug)}/{e(sib["topic_slug"])}/"{cls}><span class="tml">{e(sib["topic"])}</span></a>')
 label = '<div class="tm-label">▼ 攻略メニュー ▼</div>'
 if len(tiles) <= 6:
  return f'<div class="topmenu-a">{label}<div class="tm-menu">' + ''.join(tiles) + '</div></div>'
 script = ("<script>(function(){var tg=document.getElementById('menuToggle'),mg=document.getElementById('menuGrid');"
           "tg.addEventListener('click',function(){var f=mg.classList.toggle('folded');"
           "tg.textContent=f?'もっと見る ▼':'閉じる ▲';tg.setAttribute('aria-expanded',String(!f));});})();</script>")
 return (f'<div class="topmenu-a">{label}<div class="tm-menu folded" id="menuGrid">' + ''.join(tiles) + '</div>'
         '<button type="button" class="tm-toggle" id="menuToggle" aria-expanded="false">もっと見る ▼</button>'
         + script + '</div>')


def build_topic(g, k, siblings, sources_by_id):
 slug = g['slug']
 title = g['official_title']
 src = sources_by_id.get(k.get('source_id'))
 toc_items = [('結論', '#conclusion')]
 if k.get('answer_scope'):
  toc_items.append(('事前確認', '#precheck'))
 toc_items.append(('手順', '#steps'))
 if k.get('cautions'):
  toc_items.append(('注意点・失敗しやすい点', '#cautions'))
 if k.get('condition_differences'):
  toc_items.append(('条件差', '#differences'))
 toc_items.append(('根拠と確認日', '#source'))
 toc = '<ul class="clean">' + ''.join(f'<li><a href="{a}">{e(t)}</a></li>' for t, a in toc_items) + '</ul>'
 main_parts = [f'<section class="panel" id="conclusion"><h2>結論</h2><p>{e(k.get("conclusion"))}</p></section>']
 if k.get('answer_scope'):
  main_parts.append(f'<section class="panel" id="precheck"><h2>事前確認</h2><p>{e(k["answer_scope"])}</p></section>')
 steps_html = []
 for i, s in enumerate(k.get('steps') or [], 1):
  if not isinstance(s, dict):
   continue
  head = f'<strong>STEP {i}：{e(s["heading"])}</strong>' if s.get('heading') else f'<strong>STEP {i}</strong>'
  steps_html.append(f'<li>{head}<p>{e(s.get("text"))}</p></li>')
 main_parts.append('<section class="panel" id="steps"><h2>手順</h2><ol class="steps">' + ''.join(steps_html) + '</ol></section>')
 if k.get('cautions'):
  main_parts.append(f'<section class="panel" id="cautions"><h2>注意点・失敗しやすい点</h2><p>{e(k["cautions"])}</p></section>')
 if k.get('condition_differences'):
  main_parts.append(f'<section class="panel" id="differences"><h2>バージョン・条件による違い</h2><p>{e(k["condition_differences"])}</p></section>')
 source_html = source_block(src) if src else ''
 main_parts.append('<section class="panel" id="source"><h2>根拠と確認日</h2>' + source_html
                   + f'<p class="small">確認日：{e(k.get("checked_at"))}／{e(k.get("confidence_note"))}</p>'
                   + f'<p>{rank_badge(k.get("info_rank"))}</p></section>')
 related = [f'<li><a href="{BP}/games/{e(slug)}/">{e(title)}のポイ活攻略</a></li>']
 for sib in siblings:
  if sib.get('knowledge_id') != k.get('knowledge_id') and not sib.get('static_page'):
   related.append(f'<li><a href="{BP}/games/{e(slug)}/{e(sib["topic_slug"])}/">{e(sib["topic"])}</a></li>')
 aside = ('<section class="panel"><h2>目次</h2>' + toc + '</section>'
          '<section class="panel"><h2>関連ページ</h2><ul class="clean">' + ''.join(related) + '</ul></section>')
 indexable = topic_indexable(k, sources_by_id)
 robots = 'index,follow' if indexable else 'noindex,follow'
 crumbs = [('トップ', '/'), ('ゲーム一覧', '/games/'), (title, f'/games/{slug}/'), (k['topic'], None)]
 ld = breadcrumb_ld(crumbs, f'/games/{slug}/{k["topic_slug"]}/')
 body = ('<main class="wrap">' + breadcrumb(crumbs)
         + f'<h1>{e(title)}：{e(topic_title(k))}</h1>'
         + top_menu_html(g, k, siblings)
         + f'<div class="layout"><div class="main-col">{"".join(main_parts)}</div><aside class="side-col">{aside}</aside></div></main>')
 og_url, og_size = game_og_image(g['game_id'])
 page = page_shell(f'{title}：{topic_title(k)}',
                   f'{title}：{k["topic"]}の具体的な手順、失敗しやすい点、確認できた根拠を整理します。',
                   robots, f'/games/{slug}/{k["topic_slug"]}/', ld, body, og_image=og_url, og_image_size=og_size)
 return page, indexable


def campaign_card(g, c, history_entries, sources_by_id):
 src = sources_by_id.get(c.get('source_id'))
 pairs = []
 if c.get('reward_amount'):
  pairs.append(('報酬', e(c['reward_amount'])))
 stages = c.get('reward_stages')
 if isinstance(stages, list) and stages:
  pairs.append(('段階報酬', '<ul class="clean">' + ''.join(f'<li>{e(s)}</li>' for s in stages) + '</ul>'))
 pairs.append(('達成条件', e(c.get('completion_condition'))))
 if c.get('completion_condition_original'):
  pairs.append(('達成条件（原文）', e(c['completion_condition_original'])))
 if c.get('exclusion_conditions'):
  pairs.append(('対象外・否認条件', e(c['exclusion_conditions'])))
 if c.get('deadline'):
  pairs.append(('達成期限', e(c['deadline'])))
 if c.get('valid_from_to'):
  pairs.append(('有効期間', e(c['valid_from_to'])))
 if c.get('eligible_os'):
  pairs.append(('対象OS', e(c['eligible_os'])))
 if c.get('new_user_only'):
  pairs.append(('新規限定条件', e(c['new_user_only'])))
 if c.get('tracking_conditions'):
  pairs.append(('成果判定・計測条件', e(c['tracking_conditions'])))
 if c.get('point_grant_timing'):
  pairs.append(('ポイント付与時期', e(c['point_grant_timing'])))
 pairs.append(('確認日', e(c.get('checked_at'))))
 active = c.get('campaign_status') in ACTIVE_STATUS
 cta = ''
 if active and c.get('campaign_url'):
  cta = (f'<p><a class="cta" href="{e(c["campaign_url"])}" target="_blank" rel="sponsored nofollow noopener" '
         f'data-ref-service="{e(c.get("service_name"))}" data-ref-placement="conditions">掲載元で条件を確認する</a></p>')
 hist = ''
 if history_entries:
  hist = '<h4>変更履歴</h4>' + history_list(history_entries)
 return (f'<article class="card campaign" id="campaign-{e(c.get("campaign_id"))}">'
         f'<h3>{e(c.get("service_name"))}：{e(c.get("campaign_title"))}</h3>'
         f'<p>{campaign_status_badge(c.get("campaign_status"))} {rank_badge(c.get("info_rank"))}</p>'
         + dl_rows(pairs) + (source_block(src) if src else '') + hist + cta + '</article>')


def build_conditions(g, cs, history_by_campaign, sources_by_id):
 slug = g['slug']
 title = g['official_title']
 legend = ('<section class="panel"><h2>情報区分の見方</h2><ul class="clean">'
           '<li><strong>公式情報：</strong>ゲーム運営元・掲載サービス運営元が公開した情報</li>'
           '<li><strong>第三者情報：</strong>攻略サイト、検証記事、コミュニティ等の情報</li>'
           '<li><strong>推定・目安：</strong>前提や環境差を伴う推定値。確定条件として扱いません</li>'
           '<li><strong>情報ランク：</strong>A＝公式で現行条件まで確認済み／B＝公式だが現行性に不明点あり／C＝複数の外部情報で裏付けあり／D＝単独の利用者報告（参考）／E＝未確認</li>'
           '</ul></section>')
 active = [c for c in cs if c.get('campaign_status') in ACTIVE_STATUS]
 ended = [c for c in cs if c.get('campaign_status') not in ACTIVE_STATUS]
 parts = [legend]
 if active:
  parts.append('<section><h2>掲載中の案件</h2>' + ''.join(campaign_card(g, c, history_by_campaign.get(c.get('campaign_id'), []), sources_by_id) for c in active) + '</section>')
 else:
  parts.append('<section class="panel"><h2>掲載中の案件</h2><p class="muted">現在、掲載中の案件はありません。</p></section>')
 if ended:
  parts.append('<section><h2>終了・確認不能の案件（過去の記録）</h2><p class="small muted">終了した案件には申込導線を設置していません。条件は当時の記録です。</p>'
               + ''.join(campaign_card(g, c, history_by_campaign.get(c.get('campaign_id'), []), sources_by_id) for c in ended) + '</section>')
 indexable = conditions_indexable(g, cs, sources_by_id)
 robots = 'index,follow' if indexable else 'noindex,follow'
 crumbs = [('トップ', '/'), ('ゲーム一覧', '/games/'), (title, f'/games/{slug}/'), ('達成条件・検証記録', None)]
 ld = breadcrumb_ld(crumbs, f'/games/{slug}/conditions/')
 staged = any(c.get('reward_stages') for c in cs)
 if staged:
  caution = 'ステップアップ案件は、ステップの順番と達成期限を守らないとポイントが反映されない場合があります。各ステップの条件を確認してから始めてください。'
  cond_title = f'{title}のポイ活案件条件｜ステップアップ条件・確認記録'
 else:
  caution = '達成期限を過ぎるとポイントの対象外になるため、期限と条件を確認してから始めてください。'
  cond_title = f'{title}のポイ活案件条件・確認記録'
 body = ('<main class="wrap">' + breadcrumb(crumbs)
         + f'<h1>{e(title)}のポイ活達成条件・確認記録</h1>'
         + '<p>掲載サービスごとの達成条件と確認記録を、情報源・確認日・バージョンを区別して整理します。サービスや時期によって条件は異なります。'
         + caution + '</p>'
         + ''.join(parts) + '</main>')
 active_parts = []
 for c in active:
  part = str(c.get('service_name') or '')
  if c.get('campaign_title'):
   part = f'{part}：{c["campaign_title"]}' if part else str(c['campaign_title'])
  if part:
   active_parts.append(part)
 if active_parts:
  cond_desc = (f'{title}のポイ活案件条件まとめ。' + '／'.join(active_parts[:3])
               + 'の達成条件・ステップ・期限と確認記録を、情報源・確認日を区別して整理しています。')
 else:
  cond_desc = f'{title}のポイ活案件条件まとめ。現在、掲載中の案件はありません。終了した案件の達成条件と確認記録を整理しています。'
 og_url, og_size = game_og_image(g['game_id'])
 page = page_shell(cond_title,
                   cond_desc[:140],
                   robots, f'/games/{slug}/conditions/', ld, body, og_image=og_url, og_image_size=og_size)
 return page, indexable


# ---------- 静的ページの後処理（canonical・計測・ベースパス） ----------
def process_static(rel, canonical_path):
 p = ROOT / rel
 text = p.read_text(encoding='utf-8')
 text = re.sub(r'<!-- build:head -->.*?<!-- /build:head -->', '', text, flags=re.S)
 if BP:
  text = text.replace(f'href="{BP}/', 'href="/').replace(f'src="{BP}/', 'src="/')
  text = text.replace('href="/', f'href="{BP}/').replace('src="/', f'src="{BP}/')
 inject = favicon_links()
 if BASE:
  inject += f'<link rel="canonical" href="{e(BASE + canonical_path)}">'
  tm = re.search(r'<title>(.*?)</title>', text, re.S)
  dm = re.search(r'<meta name="description" content="([^"]*)"', text)
  full_title = tm.group(1).strip() if tm else ''
  sm = social_meta(full_title, dm.group(1) if dm else '', canonical_path, None, None, 'article')
  if sm:
   inject += sm
  short = full_title.split('｜')[0].strip()
  if short:
   inject += jsonld(breadcrumb_ld([('トップ', '/'), (short, None)], canonical_path))
 inject += ga4_snippet() + f'<script src="{BP}/assets/site.js" defer></script>'
 text = re.sub(r'</head>', '<!-- build:head -->' + inject + '<!-- /build:head --></head>', text, count=1, flags=re.I)
 p.write_text(text, encoding='utf-8')


# ---------- トップ「新着・更新の攻略」レールの自動生成 ----------
# pages-src/index.html.txt 側はレールの中身を持たず、マーカーだけを置く。
# ビルド時に候補ページのソース（static-perfect）から更新日とタイトルを読み、
# 新しい順に並べてカードを生成する。ページの更新日を直せば次回ビルドで
# レールの並び・日付チップ・「新」バッジへ自動で反映される。
# 候補（sub=カードの補足文、img=カード画像）はキュレーションとしてここで管理し、
# 日付・タイトル・並び順は手で書かない。
GUIDE_RAIL_MARKER = '<!-- build:guide-rail -->'
GUIDE_RAIL_LIMIT = 8
GUIDE_RAIL_PAGES = [
    # (game slug, ゲーム表示名, ページファイル名, カード補足文, カード画像)
    ('puzzles-and-survival', 'パズル＆サバイバル', 'joban.html', '最初の1週間でやること', 'feature-2.jpg'),
    ('puzzles-and-survival', 'パズル＆サバイバル', 'kensetsu.html', 'コントロールセンターへの近道', 'feature-5.jpg'),
    ('puzzles-and-survival', 'パズル＆サバイバル', 'hero-search.html', '属性・兵種・スキルで絞り込む', 'ui-hero-bag.webp'),
    ('puzzles-and-survival', 'パズル＆サバイバル', 'tools-cc.html', '目標レベルまでの資源を計算', 'building-headquarters.webp'),
    ('puzzles-and-survival', 'パズル＆サバイバル', 'event-calendar.html', '曜日ごとの開催イベント早見', 'inf-event-week.png'),
    ('puzzles-and-survival', 'パズル＆サバイバル', 'tools-watersort.html', 'ウォーターソートの手順を自動計算', 'gamein-puzzle.webp'),
    ('puzzles-and-survival', 'パズル＆サバイバル', 'doumei.html', '同盟の入り方とギルド対決', 'feature-4.jpg'),
    ('puzzles-and-survival', 'パズル＆サバイバル', 'board.html', '質問・雑談・同盟募集', 'shot-run-01.jpg'),
]


def _rail_page_meta(slug, fname):
    """static-perfect のページソースから (更新日 (y, m, d) | None, タイトル) を読む。"""
    p = PERFECT_DIR / slug / (fname + '.txt')
    if not p.exists():
        return None, ''
    s = p.read_text(encoding='utf-8')
    m = re.search(r'更新日：<b>(\d{4})年(\d{1,2})月(\d{1,2})日', s)
    upd = (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    t = re.search(r'<title>(.*?)</title>', s, re.S)
    title = re.sub(r'｜.*$', '', t.group(1)).strip() if t else ''
    return upd, title


def build_guide_rail():
    """「新着・更新の攻略」レールのカードHTMLを生成する。
    更新日の新しい順（同日は候補リストの順）、上限 GUIDE_RAIL_LIMIT 件。
    更新日が無いページは最後に回り、日付チップと「新」バッジを出さない。
    「新」バッジは更新日が生成日から7日以内のページだけに出す。"""
    import datetime
    today = datetime.date.today()
    items = []
    for slug, game, fname, sub, img in GUIDE_RAIL_PAGES:
        upd, title = _rail_page_meta(slug, fname)
        items.append(dict(slug=slug, game=game, fname=fname, sub=sub, img=img,
                          upd=upd, title=title))
    items.sort(key=lambda x: x['upd'] or (0, 0, 0), reverse=True)
    out = []
    for it in items[:GUIDE_RAIL_LIMIT]:
        name = it['title'] or it['fname']
        url = f"{BASE or BP}/games/{it['slug']}/{it['fname']}"
        ribbon = ''
        dbadge = ''
        if it['upd']:
            dbadge = f'<span class="gr-date">{it["upd"][1]}月{it["upd"][2]}日更新</span>'
            if 0 <= (today - datetime.date(*it['upd'])).days <= 7:
                ribbon = '<span class="gr-new" role="img" aria-label="新しく更新されたページ"></span>'
        out.append(
            f'<article class="gr-card"><a class="gr-art" href="{e(url)}" aria-label="{e(name)}">'
            f'<img src="{BP}/games/{it["slug"]}/img/{it["img"]}" alt="{e(name)}の画像" loading="lazy">{ribbon}</a>'
            f'<div class="gr-body"><span class="gr-meta"><span class="gr-game">{e(it["game"])}</span>{dbadge}</span>'
            f'<a class="gr-name" href="{e(url)}">{e(name)}</a>'
            f'<span class="gr-sub">{e(it["sub"])}</span></div></article>')
    return ''.join(out)


# ---------- サイトトップ／お問い合わせのダークモード ----------
# ゲームページ側の theme_toggle 部品（EXPANSION_BASE/parts/theme-toggle.html）と
# 同じ仕組みを、サイトトップ（index.html）とお問い合わせ（contact.html）にも入れる。
#   INIT  : localStorage 'poigame-theme' → 端末の prefers-color-scheme の順で
#           html[data-theme] を決める（ゲームページとキーを共有し、選択を引き継ぐ）
#   CSS   : 暗テーマの上書き。色はトップのカラースロット（案C：深い空→明るい空の
#           グラデ、金額は金茶 #C98A04）から作った暗テーマ値。背景だけ暗転させず
#           文字色も必ず暗テーマ側で上書きする（dark-contrast-fix の学び）
#   TOGGLE: ヘッダー右のアイコン列（.hacts）へ .hact と同じ見た目で追加する
# pages-src の再生成で消えないよう、オーバーレイ時にビルド側で差し込む。
TOP_THEME_PAGES = {'index.html', 'contact.html'}
TOP_THEME_INIT = """<script>(function(){try{var t=localStorage.getItem('poigame-theme');if(t!=='dark'&&t!=='light'){t=(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','light');}})();</script>"""
TOP_THEME_CSS = """<style>
/* === top-dark-theme-2026-11-26 === */
.theme-toggle .ic{font-size:19px;line-height:1}
html[data-theme="dark"]{color-scheme:dark;background:#0A1524}
html[data-theme="dark"] body{background:#0A1524;color:#E8EFF7}
html[data-theme="dark"] a{color:#82B4E8}
html[data-theme="dark"] header.site{background:#0E1E33;box-shadow:0 1px 5px rgba(0,0,0,.5)}
html[data-theme="dark"] .hrow{background:#0E1E33}
html[data-theme="dark"] .htag .t1{color:#EAF2FB}
html[data-theme="dark"] .htag .t2{color:#93A9C2}
html[data-theme="dark"] .hact{background:#1B3552;color:#BFD9F2}
html[data-theme="dark"] .hact:active{background:#27496E}
html[data-theme="dark"] header.site nav{background:linear-gradient(90deg,#0F2C4E,#1D5C8F)}
html[data-theme="dark"] h1{color:#EAF2FB}
html[data-theme="dark"] .lead{color:#B9C9DA}
html[data-theme="dark"] h2{background:linear-gradient(90deg,#173F6E,#2F6CA8)}
html[data-theme="dark"] h2 .h2sub{color:#EAF6FF}
html[data-theme="dark"] .searchbox input{background:#132539;border-color:#3E6FA3;color:#E8EFF7}
html[data-theme="dark"] .searchbox input::placeholder{color:#7C93AC}
html[data-theme="dark"] .sres{background:#132539;border-color:#2A435F;box-shadow:0 8px 24px rgba(0,0,0,.5)}
html[data-theme="dark"] .sres a{color:#E8EFF7;border-top-color:#22384F}
html[data-theme="dark"] .chip{background:#1B3552;color:#BFD9F2}
html[data-theme="dark"] .car-card,html[data-theme="dark"] .rail-card,html[data-theme="dark"] .rail-card2,html[data-theme="dark"] .gr-card,html[data-theme="dark"] .feat,html[data-theme="dark"] .svc-card,html[data-theme="dark"] .camp-card,html[data-theme="dark"] .svc-car-card,html[data-theme="dark"] .gtile,html[data-theme="dark"] .camp-tile{background:#132539;border-color:#2A435F}
html[data-theme="dark"] .car-meta,html[data-theme="dark"] .gr-sub,html[data-theme="dark"] .rk-sub,html[data-theme="dark"] .news-date,html[data-theme="dark"] .note,html[data-theme="dark"] .checked-line,html[data-theme="dark"] .cmp-meta,html[data-theme="dark"] .svc-note,html[data-theme="dark"] .svc-pos,html[data-theme="dark"] .svc-checked,html[data-theme="dark"] .car-count,html[data-theme="dark"] .feat .fdesc,html[data-theme="dark"] .gtile .gt-desc,html[data-theme="dark"] .cmp-svcname,html[data-theme="dark"] .svc-code span{color:#93A9C2}
html[data-theme="dark"] .rail-main,html[data-theme="dark"] .gr-name,html[data-theme="dark"] .pop-card,html[data-theme="dark"] .ag-cell,html[data-theme="dark"] .cmp-game,html[data-theme="dark"] .news-row,html[data-theme="dark"] .rank-row,html[data-theme="dark"] .pop-main,html[data-theme="dark"] .rail-main2,html[data-theme="dark"] .rank-link{color:#E8EFF7}
html[data-theme="dark"] .kv-strip{background:#152A44;color:#EAF2FB}
html[data-theme="dark"] .bd-svc,html[data-theme="dark"] .sb-default{background:#1B3552;color:#BFD9F2;border-color:#33527A}
html[data-theme="dark"] .bd-dl,html[data-theme="dark"] .gr-date,html[data-theme="dark"] .tag-chg{background:#3A2C12;color:#F2CF8F;border-color:#6E5518}
html[data-theme="dark"] .bd-boost,html[data-theme="dark"] .tag-add{background:#14301D;color:#8FD7A4;border-color:#2E5C3A}
html[data-theme="dark"] .bd-new{background:#33270F;color:#E3AC29;border-color:#6E5518}
html[data-theme="dark"] .bd-info{background:#1D3550;color:#A9C8E2}
html[data-theme="dark"] .bd-gray{background:#2B2B2B;color:#BBBBBB}
html[data-theme="dark"] .gr-game{background:#1B3552;color:#BFD9F2;border-color:#33527A}
html[data-theme="dark"] .guide-btn{background:#1B3552;color:#BFD9F2;border-color:#33527A}
html[data-theme="dark"] .tab{background:#132539;color:#82B4E8;border-color:#3E6FA3}
html[data-theme="dark"] .tab.on{background:#2F74B5;color:#fff}
html[data-theme="dark"] .rank-row{border-bottom-color:#22384F}
html[data-theme="dark"] .rk{background:#1B3552;color:#EAF2FB}
html[data-theme="dark"] .ad{border-color:#33527A;background:#101F31;color:#93A9C2}
html[data-theme="dark"] .ad b{color:#B9C9DA}
html[data-theme="dark"] .ad-slot .ad-label{color:#93A9C2}
html[data-theme="dark"] .mini-pt,html[data-theme="dark"] .ag-pt,html[data-theme="dark"] .rail-sub{color:#82B4E8}
html[data-theme="dark"] .genre a{background:#2A2140;color:#C9B8EC}
html[data-theme="dark"] .gtile .gt-arr{color:#C9B8EC}
html[data-theme="dark"] .media-card{border-color:#2A435F;color:#E8EFF7}
html[data-theme="dark"] .nl{background:#132539}
html[data-theme="dark"] .guide-links a{background:#132539;border-color:#2A435F;color:#E8EFF7}
html[data-theme="dark"] .stat{background:linear-gradient(180deg,#16293F,#101F31);border-color:#2A435F}
html[data-theme="dark"] .stat .n{color:#7FB3E8}
html[data-theme="dark"] .stat .l{color:#93A9C2}
html[data-theme="dark"] .fbox{background:#2A1E12;border-color:#8A5A28;color:#E8EFF7}
html[data-theme="dark"] .farr{color:#FF8A3D}
html[data-theme="dark"] .hook{background:#132539;border-color:#2A435F;color:#D8E2EC}
html[data-theme="dark"] .bar-name,html[data-theme="dark"] .bar-val{color:#E8EFF7}
html[data-theme="dark"] .bar-track{background:#22384F}
html[data-theme="dark"] .state-label{color:#EAF2FB}
html[data-theme="dark"] .schip{background:#132539;color:#82B4E8;border-color:#3E6FA3}
html[data-theme="dark"] .cmp-row{border-color:#2A435F}
html[data-theme="dark"] .cmp-svcs{border-top-color:#22384F}
html[data-theme="dark"] .cmp-svc{border-bottom-color:#22384F}
html[data-theme="dark"] .cmp-svc.top .cmp-amt{color:#E3AC29}
html[data-theme="dark"] .cmp-svc.top .cmp-svcname{color:#EAF2FB}
html[data-theme="dark"] .cmp-svc.hl{background:#2E2410}
html[data-theme="dark"] .bigcta{background:linear-gradient(180deg,#241A10,#171310);border-color:#6E5518}
html[data-theme="dark"] .svctabs button{background:#141C26;color:#9AA7B4;border-color:#2A3442}
html[data-theme="dark"] .svctabs button .tt{color:#7C8896}
html[data-theme="dark"] .svctabs button.on{background:#132539;color:#E3AC29;border-color:#FF6900}
html[data-theme="dark"] .svctabs button.on .tt{color:#E3AC29}
html[data-theme="dark"] .sim{background:#12291A;border-color:#2E5C3A}
html[data-theme="dark"] .sim-title{color:#8FD7A4}
html[data-theme="dark"] .sim-body{color:#D8E2EC}
html[data-theme="dark"] .svc-namebox h3,html[data-theme="dark"] .camp-title{color:#EAF2FB}
html[data-theme="dark"] .svc-benefit{background:#1B3552;color:#E8EFF7}
html[data-theme="dark"] .svc-facts,html[data-theme="dark"] .camp-lines,html[data-theme="dark"] .svc-car-cond{color:#B9C9DA}
html[data-theme="dark"] .qa{background:#101F31;border-color:#2A435F}
html[data-theme="dark"] .qa summary{color:#EAF2FB}
html[data-theme="dark"] .camp-strip{background:linear-gradient(90deg,#2A2410,#241A0E);color:#EAF2FB;border-color:#6E5518}
html[data-theme="dark"] .camp-amt{color:#82B4E8}
html[data-theme="dark"] .svc-car-name{color:#EAF2FB}
html[data-theme="dark"] .svc-car-benefit{color:#82B4E8}
html[data-theme="dark"] .svc-car-note{background:#1B3552;color:#B9C9DA}
html[data-theme="dark"] .car-progress{background:#22384F}
html[data-theme="dark"] .camp-tile-img{background:#1B3552}
html[data-theme="dark"] footer.site{background:#0B1A2C}
html[data-theme="dark"] .note-card{background:#132539;color:#D8E2EC}
html[data-theme="dark"] .note-card b{color:#EAF2FB}
html[data-theme="dark"] form.cform{background:#132539;border-color:#2A435F}
html[data-theme="dark"] .frow label{color:#EAF2FB}
html[data-theme="dark"] .frow .opt{background:#1B3552;color:#93A9C2}
html[data-theme="dark"] .frow input,html[data-theme="dark"] .frow select,html[data-theme="dark"] .frow textarea{background:#0D1B2C;color:#E8EFF7;border-color:#2A435F}
html[data-theme="dark"] .thanks{background:#12291A;border-color:#2E5C3A;color:#A9DDBB}
html[data-theme="dark"] .fnote{color:#93A9C2}
html[data-theme="dark"] input::placeholder,html[data-theme="dark"] textarea::placeholder{color:#8FA5BC}
html[data-theme="dark"] .frow .must{background:#C04541}
html[data-theme="dark"] .submit{background:linear-gradient(90deg,#173F6E,#1D5C8F)}
html[data-theme="dark"] .cta{color:#fff}
html[data-theme="dark"] .cta-btn{color:#fff}
html[data-theme="dark"] .cta-hapitas{color:#111}
html[data-theme="dark"] .cta-warau{color:#fff}
html[data-theme="dark"] .cta-moppy{color:#05302B}
html[data-theme="dark"] .cta-freecash{color:#04331B}
html[data-theme="dark"] .nl a{color:#fff}
html[data-theme="dark"] .gtile{color:#E8EFF7}
html[data-theme="dark"] footer.site a{color:#CFE0F2}
html[data-theme="dark"] ol.rank li:nth-child(1) .rk{background:#C93568}
html[data-theme="dark"] ol.rank li:nth-child(2) .rk{background:#AD590C}
html[data-theme="dark"] .feat .band.b2{background:linear-gradient(135deg,#4A7A49,#2e4a2d)}
html[data-theme="dark"] .feat .band.b6{background:linear-gradient(135deg,#A04E68,#6e2f47)}
html[data-theme="dark"] .feat .band.b8{background:linear-gradient(135deg,#B25A14,#8a4510)}
/* === /top-dark-theme === */
</style>"""
TOP_THEME_TOGGLE = """<script>(function(){var host=document.querySelector('.hacts')||document.querySelector('.header-icons');if(!host)return;var cur=document.documentElement.getAttribute('data-theme')||'light';var d=document.createElement('div');d.className='hact theme-toggle';d.setAttribute('role','button');d.setAttribute('tabindex','0');d.setAttribute('aria-label','表示テーマを切り替える');function draw(){d.innerHTML='<span class="ic">'+(cur==='dark'?'☀️':'🌙')+'</span><span>テーマ</span>';}function flip(){cur=(cur==='dark')?'light':'dark';document.documentElement.setAttribute('data-theme',cur);try{localStorage.setItem('poigame-theme',cur);}catch(e){}draw();}draw();d.addEventListener('click',flip);d.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();flip();}});host.appendChild(d);})();</script>"""


def apply_pages_overlay(index_paths):
    """pages-src/ の承認済みページ（新トップ／サービス詳細／お問い合わせ）を
    __BASE__/__BP__ を実値へ置換して ROOT へ配置し、sitemap 対象へ追加する。
    ソースは preview-game8/topbuild/convert_prod.py が生成する。"""
    src_dir = ROOT / 'pages-src'
    if not src_dir.is_dir():
        return
    assets_dims = {}
    pa_dir = ROOT / 'pages-assets'
    if pa_dir.is_dir():
        for b64f in sorted(pa_dir.glob('*.b64')):
            sz = b64_image_size(b64f)
            if sz:
                assets_dims[b64f.name[:-4]] = sz
    perfect_dims = {}
    if PERFECT_DIR.is_dir():
        for b64f in sorted(PERFECT_DIR.glob('*/img/*.b64')):
            sz = b64_image_size(b64f)
            if sz:
                perfect_dims[b64f.name[:-4]] = sz

    def overlay_resolver(src):
        if src.startswith('data:image/'):
            return data_uri_size(src)
        if src == f'{BP}/logo-symbol.png':
            return LOGO_SYMBOL_SIZE
        if '/img/' in src or src.startswith('img/'):
            base = src.split('/')[-1]
            return assets_dims.get(base) or perfect_dims.get(base)
        if src.startswith('http'):
            return store_image_size(src)
        return None

    for p in sorted(src_dir.glob('*.html.txt')):
        name = p.name[:-len('.txt')]
        text = p.read_text(encoding='utf-8')
        text = text.replace('__BASE__', BASE).replace('__BP__', BP)
        if name == 'index.html' and GUIDE_RAIL_MARKER in text:
            # 「新着・更新の攻略」レールは各ページの更新日から自動生成する
            text = text.replace(GUIDE_RAIL_MARKER, build_guide_rail(), 1)
        tm = re.search(r'<title>(.*?)</title>', text, re.S)
        dm = re.search(r'<meta name="description" content="([^"]*)"', text)
        full_title = tm.group(1).strip() if tm else ''
        desc = dm.group(1) if dm else ''
        if name == 'index.html':
            cpath = '/'
            og_type = 'website'
            ld_objs = [{'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'ポイゲークエスト', 'url': BASE + '/'}] if BASE else []
        else:
            cpath = '/' + name
            og_type = 'article'
            short = full_title.split('｜')[0].strip()
            ld_objs = []
            if BASE and short:
                ld_objs = [{'@context': 'https://schema.org', '@type': 'WebPage', 'name': short, 'url': BASE + cpath},
                           breadcrumb_ld([('トップ', '/'), (short, None)], cpath)]
        inject = social_meta(full_title, desc, cpath, None, None, og_type)
        for obj in ld_objs:
            s = jsonld(obj)
            if s:
                inject += '\n' + s
        if name in TOP_THEME_PAGES:
            inject += '\n' + TOP_THEME_INIT + '\n' + TOP_THEME_CSS
        if inject:
            text = text.replace('</head>', inject + '\n</head>', 1)
        if name in TOP_THEME_PAGES:
            text = text.replace('</body>', TOP_THEME_TOGGLE + '\n</body>', 1)
        text = add_img_dims(text, overlay_resolver)
        (ROOT / name).write_text(text, encoding='utf-8')
        if name != 'index.html':
            index_paths.append('/' + name)


def write_discovery_files(index_paths):
 robots = ROOT / 'robots.txt'
 sitemap = ROOT / 'sitemap.xml'
 prefix = BASE if BASE else PLACEHOLDER_HOST + BP
 robots.write_text(f'User-agent: *\nAllow: /\nSitemap: {prefix}/sitemap.xml\n', encoding='utf-8')
 body = ''.join(f'  <url><loc>{e(prefix + u)}</loc></url>\n' for u in index_paths)
 sitemap.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + '</urlset>\n', encoding='utf-8')



PERFECT_DIR = ROOT / 'static-perfect'
STATIC_SITEMAP_EXCLUDE = {'board.html'}


def perfect_description(text, title):
 m = re.search(r'<p class="lead">(.*?)</p>', text, re.S)
 raw = re.sub(r'<[^>]+>', '', m.group(1)) if m else ''
 raw = html.unescape(re.sub(r'\s+', ' ', raw)).strip()
 if len(raw) < 30:
  raw = (title + 'の攻略情報ページです。' + raw).strip()
 return raw[:124]


def convert_perfect_page(text, slug, name, icon_targets=None, img_dims=None):
 full_title = re.search(r'<title>(.*?)</title>', text, re.S).group(1).strip()
 title = full_title.split('｜')[0].strip()
 desc = perfect_description(text, title)
 cpath = f'/games/{slug}/' if name == 'index.html' else f'/games/{slug}/{name}'
 text = text.replace('<a href="../index.html">トップ</a>', f'<a href="{BP}/">トップ</a>')
 text = text.replace('<a href="index.html">トップ</a>', f'<a href="{BP}/">トップ</a>')
 nav_targets = {'人気ゲーム': f'{BP}/#popular', '新着・更新': f'{BP}/#updates',
                'ランキング': f'{BP}/#ranking', 'ゲーム一覧': f'{BP}/games/',
                '攻略メニュー': f'{BP}/games/{slug}/'}

 def nav_sub(m):
  return f'<a href="{nav_targets[m.group(2)]}"{m.group(1) or ""}>{m.group(2)}</a>'

 text = re.sub(r'<a href="(?:\.\./)?index\.html"( class="on")?>(人気ゲーム|新着・更新|ランキング|ゲーム一覧|攻略メニュー)</a>', nav_sub, text)
 text = text.replace('<div class="crumbs">トップ ＞ ゲーム一覧 ＞ <b>',
                     f'<div class="crumbs"><a href="{BP}/">トップ</a> ＞ <a href="{BP}/games/">ゲーム一覧</a> ＞ <b>')
 for label, url in {'ゲーム一覧': f'{BP}/games/', 'ポイントが高い順': f'{BP}/#ranking',
                    '案件条件の見方': f'{BP}/how-to-read/', '編集方針': f'{BP}/editorial-policy/',
                    'このサイトについて': f'{BP}/about/', '条件の見方 ＞': f'{BP}/how-to-read/'}.items():
  text = text.replace(f'<a href="#">{label}</a>', f'<a href="{url}">{label}</a>')
 def more_sub(m):
  inner = m.group(1)
  if '編集方針' in inner:
   url = f'{BP}/editorial-policy/'
  elif '案件条件の見方' in inner or '購入系ステップ' in inner:
   url = f'{BP}/how-to-read/'
  else:
   return m.group(0)
  return f'<a class="more-link" href="{url}">{inner}</a>'
 text = re.sub(r'<a class="more-link" href="#">(.*?)</a>', more_sub, text)
 if icon_targets:
  def row_sub(m):
   url = icon_targets.get(m.group(2))
   if not url:
    return m.group(0)
   return f'<a class="row" href="{url}">{m.group(1)}'
  text = re.sub(r'<a class="row" href="#">(<img src="(https://[^"]+)"[^>]*>)', row_sub, text)
 text = text.replace('<a class="cta-btn" href="https://hapitas.jp/appinvite?i=26164523"',
                     '<a class="cta-btn" data-ref-service="ハピタス" data-ref-placement="campaign" href="https://hapitas.jp/appinvite?i=26164523"')
 text = text.replace('<a class="sticky-cta-bar" id="stickyCtaBar" href="https://hapitas.jp/appinvite?i=26164523"',
                     '<a class="sticky-cta-bar" id="stickyCtaBar" data-ref-service="ハピタス" data-ref-placement="sticky" href="https://hapitas.jp/appinvite?i=26164523"')
 text = text.replace("var d=SVC[key]; if(!d)return;",
                     "var d=SVC[key]; if(!d)return;\n  document.querySelectorAll('.cta-btn,#stickyCtaBar').forEach(function(el){el.setAttribute('data-ref-service',d.name);});")
 text = text.replace('<div class="logo"><span class="lg-mark">ポ</span>ポイゲークエスト<span class="lg-sub">POIKATSU GAME WIKI</span></div>',
                     f'<div class="logo"><img src="{BP}/logo-symbol.png" alt="" style="width:34px;height:34px;vertical-align:-9px;margin-right:6px;border-radius:7px">ポイゲークエスト<span class="lg-sub">POIKATSU GAME WIKI</span></div>')
 inject = (f'<meta name="description" content="{e(desc)}">\n'
           '<meta name="robots" content="index,follow">\n'
           + favicon_links() + '\n')
 if BASE:
  inject += f'<link rel="canonical" href="{e(BASE + cpath)}">\n'
  og_rel = 'img/keyart-main.jpg'
  cand = name[:-5] + '.webp'
  if name != 'index.html' and img_dims and cand in img_dims:
   og_rel = 'img/' + cand
  sm = social_meta(full_title, desc, cpath, BASE + f'/games/{slug}/' + og_rel,
                   (img_dims or {}).get(og_rel.split('/')[-1]), 'article')
  if sm:
   inject += sm + '\n'
  cm = re.search(r'<div class="crumbs">(.*?)</div>', text, re.S)
  if cm:
   items = []
   for m in re.finditer(r'<a href="([^"]*)"[^>]*>([^<]+)</a>|<b>([^<]+)</b>', cm.group(1)):
    if m.group(3) is not None:
     items.append((html.unescape(m.group(3)).strip(), None))
     continue
    href = m.group(1)
    if BP and href.startswith(BP + '/'):
     path = href[len(BP):]
    elif href.startswith('/'):
     path = href
    else:
     path = f'/games/{slug}/' + href
    if path.endswith('index.html'):
     path = path[:-len('index.html')]
    items.append((html.unescape(m.group(2)).strip(), path))
   items = [it for it in items if it[0]]
   if items:
    ld = breadcrumb_ld(items, cpath)
    if ld:
     inject += jsonld(ld) + '\n'
 inject += ga4_snippet() + f'\n<script src="{BP}/assets/site.js" defer></script>\n'
 text = text.replace('</head>', inject + '</head>', 1)
 text = text.replace('</header>', '</header>\n<main>', 1)
 text = text.replace('<footer', '</main>\n<footer', 1)

 def perfect_resolver(src):
  if src.startswith('img/'):
   return (img_dims or {}).get(src.split('/')[-1])
  if src == f'{BP}/logo-symbol.png':
   return LOGO_SYMBOL_SIZE
  if src.startswith('data:image/'):
   return data_uri_size(src)
  if src.startswith('http'):
   return store_image_size(src)
  return None

 text = add_img_dims(text, perfect_resolver)
 return text


def apply_static_overlay(g, folder, icons=None):
 slug = g['slug']
 icon_targets = {}
 if icons:
  for _gid, _ent in icons.items():
   _url = icon_url(icons, _gid)
   _slug = _ent.get('slug') if isinstance(_ent, dict) else None
   if _url and _slug:
    icon_targets[_url] = f'{BP}/games/{_slug}/'
 src_dir = PERFECT_DIR / slug
 if not src_dir.is_dir():
  raise SystemExit(f'静的ページのソースがありません: {src_dir}')
 img_dims = {}
 _img_dir = src_dir / 'img'
 if _img_dir.is_dir():
  for b64f in sorted(_img_dir.glob('*.b64')):
   sz = b64_image_size(b64f)
   if sz:
    img_dims[b64f.name[:-4]] = sz
 paths = []
 for txt in sorted(src_dir.glob('*.html.txt')):
  name = txt.name[:-4]
  out = convert_perfect_page(txt.read_text(encoding='utf-8'), slug, name, icon_targets, img_dims)
  (folder / name).write_text(out, encoding='utf-8')
  if name not in ('index.html', 'board.html'):
   paths.append(f'/games/{slug}/{name}')
 img_dir = src_dir / 'img'
 if img_dir.is_dir():
  out_img = folder / 'img'
  out_img.mkdir(exist_ok=True)
  for b64f in sorted(img_dir.glob('*.b64')):
   data = base64.b64decode(re.sub(r'\s+', '', b64f.read_text(encoding='ascii')))
   (out_img / b64f.name[:-4]).write_bytes(data)
 return paths

def main():
 global BP, BASE, ICONS
 BP, BASE = resolve_base()
 run_validate()
 games = load('games')
 campaigns = load('campaigns')
 knowledge = load('knowledge')
 sources = load('sources')
 history = load('campaign_history')
 icons = {}
 icons_path = DATA / 'icons.json'
 if icons_path.exists():
  icons = json.loads(icons_path.read_text(encoding='utf-8'))
 ICONS = icons
 sources_by_id = {s.get('source_id'): s for s in sources if isinstance(s, dict) and s.get('source_id')}
 campaigns_by_game = {}
 for c in campaigns:
  if isinstance(c, dict) and c.get('game_id'):
   campaigns_by_game.setdefault(c['game_id'], []).append(c)
 knowledge_by_game = {}
 for k in knowledge:
  if isinstance(k, dict) and k.get('game_id'):
   knowledge_by_game.setdefault(k['game_id'], []).append(k)
 history_by_campaign = {}
 for h in history:
  if isinstance(h, dict) and h.get('campaign_id'):
   history_by_campaign.setdefault(h['campaign_id'], []).append(h)
 # 生成判定：掲載資格が確認済み かつ 公開状態のゲームのみ（検証で整合性は担保済み）
 visible = []
 seen = set()
 for g in games:
  if not isinstance(g, dict):
   raise SystemExit('ERROR: games に object 以外の要素があります')
  slug = str(g.get('slug') or '').strip()
  if not SLUG_RE.fullmatch(slug):
   raise SystemExit(f'ERROR: slug不正 {slug}')
  if slug in seen:
   raise SystemExit(f'ERROR: slug重複 {slug}')
  seen.add(slug)
  if g.get('eligibility_status') in ELIGIBLE and g.get('publication_status') in PUBLISHED:
   visible.append(g)
 games_dir = ROOT / 'games'
 games_dir.mkdir(exist_ok=True)
 index_paths = ['/', '/about/', '/editorial-policy/', '/how-to-read/']
 detail_indexable = {}
 rail_ranked = sorted(visible, key=lambda gg: max_reward(gg['game_id'], campaigns_by_game), reverse=True)
 rail_games = [(gg, campaigns_by_game.get(gg['game_id'], [])) for gg in rail_ranked
               if max_reward(gg['game_id'], campaigns_by_game) > 0][:4]
 for g in visible:
  slug = g['slug']
  ks = knowledge_by_game.get(g['game_id'], [])
  cs = campaigns_by_game.get(g['game_id'], [])
  hist = [h for c in cs for h in history_by_campaign.get(c.get('campaign_id'), [])]
  folder = games_dir / slug
  folder.mkdir(parents=True, exist_ok=True)
  static_mode = g.get('page_mode') == 'static'
  if static_mode:
   detail_indexable[slug] = True
   index_paths.append(f'/games/{slug}/')
  else:
   page, idx = build_detail(g, ks, cs, hist, sources_by_id, rail_games, icons)
   (folder / 'index.html').write_text(page, encoding='utf-8')
   detail_indexable[slug] = idx
   if idx:
    index_paths.append(f'/games/{slug}/')
  generated_topics = set()
  for k in ks:
   if static_mode and k.get('static_page'):
    continue
   ts = str(k.get('topic_slug') or '').strip()
   if not SLUG_RE.fullmatch(ts):
    continue
   generated_topics.add(ts)
   tdir = folder / ts
   tdir.mkdir(parents=True, exist_ok=True)
   tpage, tidx = build_topic(g, k, ks, sources_by_id)
   (tdir / 'index.html').write_text(tpage, encoding='utf-8')
   if tidx:
    index_paths.append(f'/games/{slug}/{ts}/')
  if cs:
   cdir = folder / 'conditions'
   cdir.mkdir(parents=True, exist_ok=True)
   cpage, cidx = build_conditions(g, cs, history_by_campaign, sources_by_id)
   (cdir / 'index.html').write_text(cpage, encoding='utf-8')
   if cidx:
    index_paths.append(f'/games/{slug}/conditions/')
  keep = {'index.html'} | generated_topics | ({'conditions'} if cs else set())
  for p in folder.iterdir():
   if p.is_dir() and p.name not in keep:
    shutil.rmtree(p)
  if static_mode:
   index_paths.extend(apply_static_overlay(g, folder, icons))
 list_page, list_robots = build_list(visible, campaigns_by_game, any(detail_indexable.values()), icons)
 (games_dir / 'index.html').write_text(list_page, encoding='utf-8')
 if list_robots.startswith('index'):
  index_paths.insert(4, '/games/')
 (ROOT / 'index.html').write_text(build_top(visible, campaigns_by_game, knowledge_by_game, history, icons), encoding='utf-8')
 generated_slugs = {g['slug'] for g in visible}
 for p in games_dir.iterdir():
  if p.is_dir() and p.name not in generated_slugs:
   shutil.rmtree(p)
 for rel, path in STATIC_PAGES:
  process_static(rel, path)
 apply_pages_overlay(index_paths)
 write_discovery_files(sorted(set(index_paths), key=index_paths.index))
 print(f'PASS: トップ・一覧（{list_robots}）・ゲーム詳細{len(visible)}件・攻略{sum(len(knowledge_by_game.get(g["game_id"], [])) for g in visible)}件・条件ページ{sum(1 for g in visible if campaigns_by_game.get(g["game_id"]))}件を生成。index対象{len(set(index_paths))}URL、ベースパス={BP or "/"}、ホスト設定={"あり" if BASE else "なし"}')
 return 0


if __name__ == '__main__':
 sys.exit(main())
