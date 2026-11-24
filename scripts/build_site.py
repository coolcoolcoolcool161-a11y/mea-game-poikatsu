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
import json, html, os, re, shutil, subprocess, sys
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


def jsonld(obj):
 if obj is None:
  return ''
 text = json.dumps(obj, ensure_ascii=False).replace('</', '<\\/')
 return f'<script type="application/ld+json">{text}</script>'


def page_head(title, desc, robots, canonical_path=None, ld=None):
 parts = ['<!doctype html>', '<html lang="ja"><head>', '<meta charset="utf-8">',
          '<meta name="viewport" content="width=device-width, initial-scale=1">',
          f'<title>{e(title)}</title>',
          f'<meta name="description" content="{e(desc)}">',
          f'<meta name="robots" content="{robots}">']
 if canonical_path is not None and BASE:
  parts.append(f'<link rel="canonical" href="{e(BASE + canonical_path)}">')
 parts.append(f'<link rel="stylesheet" href="{BP}/assets/site.css">')
 parts.append(ga4_snippet())
 parts.append(f'<script src="{BP}/assets/site.js" defer></script>')
 if ld:
  parts.append(jsonld(ld))
 parts.append('</head>')
 return '\n'.join(parts)


def site_header():
 links = ''.join(f'<a href="{BP}{p}">{t}</a>' for p, t in NAV)
 return (f'<header><div class="wrap head"><a class="brand" href="{BP}/">{SITE_NAME}</a>'
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


def page_shell(title, desc, robots, canonical_path, ld, body):
 return page_head(title, desc, robots, canonical_path, ld) + '\n<body>\n' + site_header() + '\n' + body + '\n' + site_footer() + '\n</body></html>\n'


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
def game_card(g, cs):
 badges = ''
 if any(c.get('campaign_status') in ACTIVE_STATUS for c in cs):
  badges = '<p><span class="badge badge-ok">掲載確認済みの案件あり</span></p>'
 elif cs:
  badges = '<p><span class="badge badge-end">現行案件なし（過去の記録）</span></p>'
 return (f'<article class="card game-card" data-name="{e(g["official_title"])}">'
         f'<h3><a href="{BP}/games/{e(g["slug"])}/">{e(g["official_title"])}</a></h3>'
         f'<p>{e(g["wiki_summary"])}</p>'
         f'<p class="small muted">最終確認：{e(g.get("last_checked_at"))}</p>{badges}</article>')


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
def build_top(visible, campaigns_by_game, knowledge_by_game, history):
 cards = [game_card(g, campaigns_by_game.get(g['game_id'], [])) for g in sorted(visible, key=lambda x: str(x['official_title']))]
 events = []
 games_by_id = {g['game_id']: g for g in visible}
 for g in visible:
  if g.get('last_checked_at'):
   events.append((str(g['last_checked_at']), f'{g["official_title"]}の情報を確認'))
 for g in visible:
  for c in campaigns_by_game.get(g['game_id'], []):
   if c.get('checked_at'):
    events.append((str(c['checked_at']), f'{g["official_title"]}（{c.get("service_name")}）の案件条件を確認'))
 for h in history:
  c_game = None
  for g in visible:
   if any(c.get('campaign_id') == h.get('campaign_id') for c in campaigns_by_game.get(g['game_id'], [])):
    c_game = g
    break
  if c_game and h.get('changed_at'):
   events.append((str(h['changed_at']), f'{c_game["official_title"]}の案件に{h.get("change_type")}を確認'))
 events.sort(key=lambda x: x[0], reverse=True)
 updates = events[:5]
 if updates:
  updates_html = '<ul class="clean">' + ''.join(f'<li>{e(d)}：{e(t)}</li>' for d, t in updates) + '</ul>'
 else:
  updates_html = '<p class="muted">まだ更新情報はありません。対象ゲームの確認が完了したものから掲載します。</p>'
 if cards:
  games_html = '<div class="grid">' + ''.join(cards) + '</div>'
 else:
  games_html = '<p class="muted">現在、公開基準を満たしたゲーム情報はありません。対象ゲームの確認が完了したものから掲載します。</p>'
 main_col = (
  '<section class="hero"><div class="eyebrow">GAME GUIDE / POINT REWARDS</div>'
  '<h1>ポイ活ゲーム攻略Wiki</h1>'
  '<p class="lead">ポイ活対象ゲームの攻略情報、達成条件、つまずきやすいポイントをゲーム別に整理する独立Wikiです。サービスごとに異なる案件条件と、ゲーム共通の攻略情報を分けて確認できるようにします。</p>'
  f'<p><a href="{BP}/games/">ゲーム一覧を見る →</a></p></section>'
  '<section class="panel"><h2>ゲーム名で探す</h2>' + search_block('search-top') + '</section>'
  '<section><h2>掲載ゲーム</h2>' + games_html + '</section>'
  '<section class="grid">'
  '<div class="panel"><h2>ゲーム別に攻略を確認</h2><p>対象ゲームの掲載確認と情報整理が完了したものから公開します。未確認のゲームや条件を推測で掲載することはありません。</p></div>'
  '<div class="panel"><h2>条件と攻略情報を分離</h2><p>ゲームの一般的な進め方と、ポイントサイト・アプリごとの報酬や期限・達成条件を区別して掲載します。</p>'
  f'<p><a href="{BP}/how-to-read/">情報の見方 →</a></p></div>'
  '</section>')
 aside = ('<section class="panel"><h2>更新情報</h2>' + updates_html + '</section>'
          '<section class="panel"><h2>掲載情報の確認方針</h2><ul class="clean"><li>情報源と確認日を記載</li><li>公式情報・第三者情報・推定を区別</li><li>掲載終了や条件変更を履歴管理</li><li>実プレイしていない内容を実測として表現しない</li></ul>'
          f'<p><a href="{BP}/editorial-policy/">編集・検証方針を確認する →</a></p></section>')
 body = f'<main class="wrap"><div class="layout"><div class="main-col">{main_col}</div><aside class="side-col">{aside}</aside></div></main>'
 ld = {'@context': 'https://schema.org', '@type': 'WebPage', 'name': 'ポイ活ゲーム攻略Wiki｜ゲーム別の達成条件・攻略情報', 'url': BASE + '/'} if BASE else None
 return page_shell('ポイ活ゲーム攻略Wiki｜ゲーム別の達成条件・攻略情報',
                   'ポイ活対象ゲームの攻略情報、達成条件、注意点をゲーム別に整理。情報源と確認日を明示し、サービス別の案件条件を分けて掲載します。',
                   'index,follow', '/', ld, body)


def build_list(visible, campaigns_by_game, any_indexable):
 cards = [game_card(g, campaigns_by_game.get(g['game_id'], [])) for g in sorted(visible, key=lambda x: str(x['official_title']))]
 if cards:
  body_cards = '<div class="grid">' + ''.join(cards) + '</div>'
 else:
  body_cards = '<p class="muted">現在、公開基準を満たしたゲーム情報はありません。対象ゲームの確認が完了したものから掲載します。</p>'
 robots = 'index,follow' if (visible and any_indexable) else 'noindex,follow'
 body = ('<main class="wrap">' + breadcrumb([('トップ', '/'), ('ゲーム一覧', None)])
         + '<h1>ゲーム一覧</h1><p>対象サービスでの掲載と公開基準を確認できたゲームを掲載しています。</p>'
         + search_block('search-list')
         + f'<section aria-label="公開中のゲーム"><h2>掲載中のゲーム</h2>{body_cards}</section></main>')
 ld = {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': 'ゲーム一覧', 'url': BASE + '/games/'} if BASE else None
 return page_shell('ゲーム一覧 | ポイ活ゲーム攻略Wiki',
                   'ポイ活対象ゲームの攻略情報一覧。掲載根拠と確認状況を明示しています。',
                   robots, '/games/', ld, body), robots


def build_detail(g, ks, cs, history_entries, sources_by_id):
 slug = g['slug']
 title = g['official_title']
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
  links = ''.join(f'<li><a href="{BP}/games/{e(slug)}/{e(k["topic_slug"])}/">{e(k["topic"])}の進め方・注意点</a></li>' for k in ks)
  sections.append('<section class="panel"><h2>攻略テーマ</h2><ul class="clean">' + links + '</ul></section>')
 active = [c for c in cs if c.get('campaign_status') in ACTIVE_STATUS]
 if cs:
  rows = []
  for c in active:
   rows.append(f'<li>{e(c.get("service_name"))}：{e(c.get("campaign_title"))}'
               + (f'（報酬：{e(c["reward_amount"])}）' if c.get('reward_amount') else '')
               + (f'（期限：{e(c["deadline"])}）' if c.get('deadline') else '')
               + f' {campaign_status_badge(c.get("campaign_status"))}</li>')
  note = ''.join(rows) if rows else '<li>現在、掲載中の案件はありません。</li>'
  sections.append('<section class="panel"><h2>サービス別案件情報</h2><ul class="clean">' + note + '</ul>'
                  f'<p><a href="{BP}/games/{e(slug)}/conditions/">達成条件・確認記録を見る →</a></p></section>')
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
  related.insert(0, f'<li><a href="{BP}/games/{e(slug)}/conditions/">{e(title)}の達成条件・確認記録</a></li>')
 sections.append('<section class="panel"><h2>関連ページ</h2><ul class="clean">' + ''.join(related) + '</ul></section>')
 indexable = game_indexable(g, ks, sources_by_id)
 robots = 'index,follow' if indexable else 'noindex,follow'
 crumbs = [('トップ', '/'), ('ゲーム一覧', '/games/'), (title, None)]
 ld = breadcrumb_ld(crumbs, f'/games/{slug}/')
 body = ('<main class="wrap">' + breadcrumb(crumbs)
         + f'<h1>{e(title)}のポイ活攻略</h1><p class="lead">{e(g["wiki_summary"])}</p>'
         + ''.join(sections) + '</main>')
 page = page_shell(f'{title}のポイ活攻略｜達成条件・進め方・注意点',
                   f'{title}のゲーム概要、ポイ活達成のポイント、関連攻略、確認済み情報をまとめます。',
                   robots, f'/games/{slug}/', ld, body)
 return page, indexable


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
  if sib.get('knowledge_id') != k.get('knowledge_id'):
   related.append(f'<li><a href="{BP}/games/{e(slug)}/{e(sib["topic_slug"])}/">{e(sib["topic"])}</a></li>')
 aside = ('<section class="panel"><h2>目次</h2>' + toc + '</section>'
          '<section class="panel"><h2>関連ページ</h2><ul class="clean">' + ''.join(related) + '</ul></section>')
 indexable = topic_indexable(k, sources_by_id)
 robots = 'index,follow' if indexable else 'noindex,follow'
 crumbs = [('トップ', '/'), ('ゲーム一覧', '/games/'), (title, f'/games/{slug}/'), (k['topic'], None)]
 ld = breadcrumb_ld(crumbs, f'/games/{slug}/{k["topic_slug"]}/')
 body = ('<main class="wrap">' + breadcrumb(crumbs)
         + f'<h1>{e(title)}：{e(k["topic"])}の進め方・注意点</h1>'
         + f'<div class="layout"><div class="main-col">{"".join(main_parts)}</div><aside class="side-col">{aside}</aside></div></main>')
 page = page_shell(f'{title}：{k["topic"]}の進め方・注意点',
                   f'{k["topic"]}の具体的な手順、失敗しやすい点、確認できた根拠を整理します。',
                   robots, f'/games/{slug}/{k["topic_slug"]}/', ld, body)
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
 body = ('<main class="wrap">' + breadcrumb(crumbs)
         + f'<h1>{e(title)}のポイ活達成条件・確認記録</h1>'
         + '<p>掲載サービスごとの達成条件と確認記録を、情報源・確認日・バージョンを区別して整理します。サービスや時期によって条件は異なります。</p>'
         + ''.join(parts) + '</main>')
 page = page_shell(f'{title}のポイ活達成条件・確認記録',
                   '掲載サービスごとの達成条件と確認記録を、情報源・確認日・バージョンを区別して整理します。',
                   robots, f'/games/{slug}/conditions/', ld, body)
 return page, indexable


# ---------- 静的ページの後処理（canonical・計測・ベースパス） ----------
def process_static(rel, canonical_path):
 p = ROOT / rel
 text = p.read_text(encoding='utf-8')
 text = re.sub(r'<!-- build:head -->.*?<!-- /build:head -->', '', text, flags=re.S)
 if BP:
  text = text.replace(f'href="{BP}/', 'href="/').replace(f'src="{BP}/', 'src="/')
  text = text.replace('href="/', f'href="{BP}/').replace('src="/', f'src="{BP}/')
 inject = ''
 if BASE:
  inject += f'<link rel="canonical" href="{e(BASE + canonical_path)}">'
 inject += ga4_snippet() + f'<script src="{BP}/assets/site.js" defer></script>'
 text = re.sub(r'</head>', '<!-- build:head -->' + inject + '<!-- /build:head --></head>', text, count=1, flags=re.I)
 p.write_text(text, encoding='utf-8')


def write_discovery_files(index_paths):
 robots = ROOT / 'robots.txt'
 sitemap = ROOT / 'sitemap.xml'
 prefix = BASE if BASE else PLACEHOLDER_HOST + BP
 robots.write_text(f'User-agent: *\nAllow: /\nSitemap: {prefix}/sitemap.xml\n', encoding='utf-8')
 body = ''.join(f'  <url><loc>{e(prefix + u)}</loc></url>\n' for u in index_paths)
 sitemap.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + '</urlset>\n', encoding='utf-8')


def main():
 global BP, BASE
 BP, BASE = resolve_base()
 run_validate()
 games = load('games')
 campaigns = load('campaigns')
 knowledge = load('knowledge')
 sources = load('sources')
 history = load('campaign_history')
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
 for g in visible:
  slug = g['slug']
  ks = knowledge_by_game.get(g['game_id'], [])
  cs = campaigns_by_game.get(g['game_id'], [])
  hist = [h for c in cs for h in history_by_campaign.get(c.get('campaign_id'), [])]
  folder = games_dir / slug
  folder.mkdir(parents=True, exist_ok=True)
  page, idx = build_detail(g, ks, cs, hist, sources_by_id)
  (folder / 'index.html').write_text(page, encoding='utf-8')
  detail_indexable[slug] = idx
  if idx:
   index_paths.append(f'/games/{slug}/')
  generated_topics = set()
  for k in ks:
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
 list_page, list_robots = build_list(visible, campaigns_by_game, any(detail_indexable.values()))
 (games_dir / 'index.html').write_text(list_page, encoding='utf-8')
 if list_robots.startswith('index'):
  index_paths.insert(4, '/games/')
 (ROOT / 'index.html').write_text(build_top(visible, campaigns_by_game, knowledge_by_game, history), encoding='utf-8')
 generated_slugs = {g['slug'] for g in visible}
 for p in games_dir.iterdir():
  if p.is_dir() and p.name not in generated_slugs:
   shutil.rmtree(p)
 for rel, path in STATIC_PAGES:
  process_static(rel, path)
 write_discovery_files(sorted(set(index_paths), key=index_paths.index))
 print(f'PASS: トップ・一覧（{list_robots}）・ゲーム詳細{len(visible)}件・攻略{sum(len(knowledge_by_game.get(g["game_id"], [])) for g in visible)}件・条件ページ{sum(1 for g in visible if campaigns_by_game.get(g["game_id"]))}件を生成。index対象{len(set(index_paths))}URL、ベースパス={BP or "/"}、ホスト設定={"あり" if BASE else "なし"}')
 return 0


if __name__ == '__main__':
 sys.exit(main())
