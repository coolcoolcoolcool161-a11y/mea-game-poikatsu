#!/usr/bin/env python3
"""Build regression tests: 4台帳＋履歴からの生成、index分離、サブパス、計測、冪等性。"""
import hashlib, json, os, subprocess, sys
from pathlib import Path
r=Path(__file__).resolve().parents[1]; D=r/'data'
names=('games','campaigns','knowledge','sources','campaign_history')
original={n:(D/f'{n}.json').read_text(encoding='utf-8') for n in names}
original_sitemap=(r/'sitemap.xml').read_text(encoding='utf-8'); original_robots=(r/'robots.txt').read_text(encoding='utf-8')
original_top=(r/'index.html').read_text(encoding='utf-8'); original_static={rel:(r/rel).read_text(encoding='utf-8') for rel in ('about/index.html','editorial-policy/index.html','how-to-read/index.html')}
env=os.environ.copy(); env.pop('S07_SITE_BASE_URL',None); env.pop('S07_SITE_BASE_PATH',None)
HOST={'S07_SITE_BASE_URL':'https://mea-poikatsu.github.io/mea-game-poikatsu'}
def run(script, extra_env=None, check=True):
 e=env.copy(); e.update(extra_env or {})
 return subprocess.run([sys.executable,str(r/'scripts'/script)],env=e,check=check,capture_output=True,text=True)
def write(n,v): (D/f'{n}.json').write_text(json.dumps(v,ensure_ascii=False),encoding='utf-8')
def tree_hashes():
 out={}
 for p in sorted(r.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.html','.xml','.txt'):
   out[p.relative_to(r).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
 return out
GAME={'game_id':'TEST-001','slug':'sample-game','official_title':'検証用サンプルゲーム','publisher':'検証用運営元','supported_os':'iOS/Android','game_version':'検証用バージョン','official_game_url':'https://example.invalid/game','eligibility_status':'確認済み','eligibility_evidence':'https://example.invalid/listing','first_checked_at':'2026-11-24 JST','last_checked_at':'2026-11-24 JST','publication_status':'公開','wiki_summary':'これは自動テスト専用の仮データであり、実在のゲームや案件を示すものではありません。','info_rank':'A'}
SOURCE={'source_id':'TEST-S1','source_type':'公式','publisher':'検証用発信元','title':'検証用出典','url':'https://example.invalid/source','checked_at':'2026-11-24 JST','conditions':'検証用条件','limitations':'検証用制約'}
KNOW={'knowledge_id':'TEST-K1','game_id':'TEST-001','topic':'検証テーマ','topic_slug':'test-topic','conclusion':'検証用の結論です。'+'攻略本文の検証用テキストです。'*8,'answer_scope':'検証用の対象範囲です。','steps':[{'heading':'最初の手順','text':'検証用の手順本文です。'*6},{'text':'見出しなし手順の本文です。'}],'cautions':'検証用の注意点です。','source_type':'公式','source_id':'TEST-S1','checked_at':'2026-11-24 JST','confidence_note':'検証用の確度メモ','info_rank':'A'}
CAMP_ACTIVE={'campaign_id':'TEST-C1','game_id':'TEST-001','source_id':'TEST-S1','service_name':'検証サービス','campaign_title':'検証用アクティブ案件','reward_amount':'検証用報酬','completion_condition':'検証用の達成条件です。','campaign_url':'https://example.invalid/campaign','campaign_status':'掲載中','checked_at':'2026-11-24 JST','info_rank':'A'}
CAMP_ENDED={'campaign_id':'TEST-C2','game_id':'TEST-001','source_id':'TEST-S1','service_name':'検証サービス2','campaign_title':'検証用終了案件','completion_condition':'検証用の達成条件です。','campaign_url':'https://example.invalid/campaign2','campaign_status':'終了','checked_at':'2026-11-24 JST','info_rank':'B'}
HISTORY=[{'history_id':'TEST-H1','campaign_id':'TEST-C2','changed_at':'2026-11-24 JST','change_type':'終了','old_value':'掲載中','new_value':'終了'}]
def load_fixture():
 write('games',[GAME]); write('sources',[SOURCE]); write('knowledge',[KNOW]); write('campaigns',[CAMP_ACTIVE,CAMP_ENDED]); write('campaign_history',HISTORY)
try:
 load_fixture()
 run('validate_data.py'); run('build_site.py')
 detail=(r/'games'/'sample-game'/'index.html').read_text(encoding='utf-8')
 topic=(r/'games'/'sample-game'/'test-topic'/'index.html').read_text(encoding='utf-8')
 cond=(r/'games'/'sample-game'/'conditions'/'index.html').read_text(encoding='utf-8')
 listing=(r/'games'/'index.html').read_text(encoding='utf-8')
 top=(r/'index.html').read_text(encoding='utf-8')
 # 4台帳＋履歴から詳細・攻略・条件が生成され、共通レイアウトとサブパスが効いている
 for page in (detail,topic,cond,listing,top):
  assert 'class="wrap head"' in page and 'class="brand"' in page and 'class="footlinks"' in page
  assert 'href="/mea-game-poikatsu/games/"' in page
  assert 'G-8BB8V3DRW8' in page and 'site.js' in page  # GA4＋計測スクリプト
 assert '検証用サンプルゲーム' in detail and '検証テーマ' in detail
 assert '検証用の結論です' in topic and 'STEP 1' in topic and '/games/sample-game/test-topic/' in detail
 assert '<link rel="canonical"' not in detail  # ホスト未確定ではcanonicalを出さない
 # 条件ページ: サービス分離、終了案件にCTAなし、掲載中案件に計測付きCTA
 assert '検証サービス：検証用アクティブ案件' in cond and '検証サービス2：検証用終了案件' in cond
 assert 'data-ref-service="検証サービス"' in cond and 'data-ref-placement="conditions"' in cond
 ended_part=cond.split('検証用終了案件')[1]
 assert 'data-ref-service' not in ended_part and '掲載元で条件を確認する' not in ended_part
 assert '変更履歴' in cond and '掲載中 → 終了' in cond  # campaign_history が伝播する
 # index分離: 詳細・攻略はindex、条件ページは原則noindexでsitemapに入らない
 assert 'content="index,follow"' in detail and 'content="index,follow"' in topic
 assert 'content="noindex,follow"' in cond
 assert 'content="index,follow"' in listing
 # 検索フォームがトップと一覧にあり、JSに絞り込みとreferral_clickが実装されている
 assert 'data-game-search' in top and 'data-game-search' in listing
 js=(r/'assets'/'site.js').read_text(encoding='utf-8')
 assert 'data-game-search' in js and 'referral_click' in js and "site_id: 's07'" in js.replace('"',"'")
 # 実ホスト（パス付き）でcanonicalとsitemapがサブパス込みになる
 run('build_site.py',HOST)
 detail=(r/'games'/'sample-game'/'index.html').read_text(encoding='utf-8')
 sitemap=(r/'sitemap.xml').read_text(encoding='utf-8'); robots=(r/'robots.txt').read_text(encoding='utf-8')
 assert '<link rel="canonical" href="https://mea-poikatsu.github.io/mea-game-poikatsu/games/sample-game/">' in detail
 assert 'https://mea-poikatsu.github.io/mea-game-poikatsu/games/sample-game/test-topic/' in sitemap
 assert 'conditions/' not in sitemap  # noindexの条件ページはsitemapに入らない
 assert 'Sitemap: https://mea-poikatsu.github.io/mea-game-poikatsu/sitemap.xml' in robots
 assert 'BreadcrumbList' in detail  # 表示パンくずと一致する構造化データ
 audit=run('audit_site.py',HOST)
 assert audit.returncode==0 and 'ERROR 0' in audit.stdout,audit.stdout
 # ホスト検証: HTTPは拒否する
 invalid=run('build_site.py',{'S07_SITE_BASE_URL':'http://example.invalid'},check=False)
 assert invalid.returncode!=0
 # エスケープ: タイトル内のHTMLは無加工で挿入されない
 write('games',[dict(GAME,official_title='<script>alert(1)</script>')])
 run('build_site.py',HOST)
 escaped=(r/'games'/'sample-game'/'index.html').read_text(encoding='utf-8')
 assert '&lt;script&gt;alert(1)&lt;/script&gt;' in escaped and '<script>alert(1)</script>' not in escaped
 write('games',[GAME])
 # 冪等性: 同じ入力で2回生成しても生成物が変わらない
 run('build_site.py',HOST); first=tree_hashes()
 run('build_site.py',HOST); second=tree_hashes()
 assert first==second
 # 検証失敗時はビルドが中止される
 write('campaigns',[{'campaign_id':'BROKEN'}])
 bad=run('build_site.py',check=False); assert bad.returncode!=0 and '生成を中止' in bad.stdout+bad.stderr
 write('campaigns',[CAMP_ACTIVE,CAMP_ENDED])
 # topic_slugを変えると旧い攻略ページの残骸が掃除される
 write('knowledge',[dict(KNOW,topic_slug='renamed-topic')])
 run('build_site.py')
 assert not (r/'games'/'sample-game'/'test-topic').exists()
 assert (r/'games'/'sample-game'/'renamed-topic'/'index.html').exists()
 assert (r/'games'/'sample-game'/'index.html').exists()
 write('knowledge',[KNOW])
 # 空状態: 一覧はnoindex、トップは空状態の説明、生成ページは掃除される
 for n in names: write(n,[])
 run('validate_data.py'); run('build_site.py')
 listing=(r/'games'/'index.html').read_text(encoding='utf-8'); top=(r/'index.html').read_text(encoding='utf-8')
 assert '現在、公開基準を満たしたゲーム情報はありません' in listing and 'content="noindex,follow"' in listing
 assert '現在、公開基準を満たしたゲーム情報はありません' in top
 assert not (r/'games'/'sample-game').exists()
 print('PASS: 4台帳＋履歴生成・共通レイアウト・サブパス・GA4/referral_click・index分離・sitemap・canonical・構造化データ・検索・終了案件CTA抑止・履歴伝播・エスケープ・冪等性・検証失敗時中止・残骸掃除・空状態')
finally:
 # 台帳と静的ページを元の状態に戻し、決定的に再生成して初期状態へ復元する
 for n,v in original.items(): (D/f'{n}.json').write_text(v,encoding='utf-8')
 for rel,v in original_static.items(): (r/rel).write_text(v,encoding='utf-8')
 run('validate_data.py'); run('build_site.py')
 assert (r/'sitemap.xml').read_text(encoding='utf-8')==original_sitemap
 assert (r/'robots.txt').read_text(encoding='utf-8')==original_robots
 assert (r/'index.html').read_text(encoding='utf-8')==original_top
