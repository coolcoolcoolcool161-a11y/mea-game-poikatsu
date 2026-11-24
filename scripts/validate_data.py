#!/usr/bin/env python3
"""Validate S07 ledgers, foreign keys, evidence links and publication gates.

スキーマCSVは site/schema/ に同梱する（配置先に依存しない）。
台帳は games / campaigns / knowledge / sources / campaign_history の5つ。
情報ランクは調査ポリシーのA〜Eに統一する（指示書のS〜D表記は使わない）。
攻略本文は knowledge 台帳に一本化し、games.guide_sections は廃止した。
"""
import csv, json, re, sys
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
SCHEMA_ROOT=ROOT/'schema'
DATA=ROOT/'data'
TABLES={
 'games':('02_ゲーム台帳スキーマ.csv','game_id'),
 'campaigns':('03_案件台帳スキーマ.csv','campaign_id'),
 'knowledge':('04_攻略情報台帳スキーマ.csv','knowledge_id'),
 'sources':('05_出典台帳スキーマ.csv','source_id'),
 'campaign_history':('23_案件履歴台帳スキーマ.csv','history_id'),
}
ELIGIBLE={'確認済み','confirmed'}; PUBLISHED={'公開','published'}
RANKS={'A','B','C','D','E'}
PUBLISHABLE_RANKS={'A','B','C'}
SLUG_PATTERN=r'[a-z0-9]+(?:-[a-z0-9]+)*'
ALLOWED={
 'eligibility_status':{'確認済み','確認待ち','対象外','confirmed','pending','ineligible'},
 'publication_status':{'未作成','下書き','審査中','公開','停止','draft','review','published','paused'},
 'campaign_status':{'掲載中','終了','再開','変更','確認不能','active','ended','reopened','changed','unknown'},
 'source_type':{'公式','第三者','推定','official','third_party','estimate'},
 'info_rank':RANKS,
 'change_type':{'掲載開始','報酬変更','条件変更','期限変更','状態変更','終了','再開','確認不能','訂正'},
}
# 状態が変わった案件は campaign_history に履歴が必須（付け忘れ検出）
HISTORY_REQUIRED_STATUS={'変更','終了','再開','changed','ended','reopened'}
def https_url(v):
 p=urlparse(v or ''); return p.scheme=='https' and bool(p.netloc)
def load_schema(filename):
 path=SCHEMA_ROOT/filename
 if not path.exists(): raise ValueError(f'スキーマCSVがありません: schema/{filename}')
 with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def load_data(name):
 p=DATA/(name+'.json')
 if not p.exists(): return []
 try: value=json.loads(p.read_text(encoding='utf-8'))
 except Exception as e: raise ValueError(f'{p.name}: JSON解析エラー: {e}')
 if not isinstance(value,list): raise ValueError(f'{p.name}: 最上位は配列必須')
 return value
def knowledge_body_len(k):
 total=len(str(k.get('conclusion') or ''))
 steps=k.get('steps')
 if isinstance(steps,list):
  for s in steps:
   if isinstance(s,dict): total+=len(str(s.get('heading') or ''))+len(str(s.get('text') or ''))
 return total
def main():
 errors=[]; records={}
 for name,(schema_file,id_field) in TABLES.items():
  try:
   schema=load_schema(schema_file); data=load_data(name)
  except Exception as e: errors.append(str(e)); continue
  records[name]=data
  required=[r['field'].lstrip('\ufeff') for r in schema if r.get('必須性')=='必須']
  seen=set()
  for n,item in enumerate(data,1):
   label=f'{name}[{n}]'
   if not isinstance(item,dict): errors.append(f'{label}: object以外'); continue
   for key in required:
    if item.get(key) in (None,'',[]): errors.append(f'{label}: 必須項目 {key} が空')
   ident=item.get(id_field)
   if ident in seen: errors.append(f'{label}: {id_field}重複 {ident}')
   if ident: seen.add(ident)
   for key,value in item.items():
    if key.endswith('_url') or key in ('url','eligibility_evidence','campaign_url'):
     if value not in (None,'') and not https_url(value): errors.append(f'{label}: {key}はhttps URL必須')
    if key in ALLOWED and value not in (None,'') and value not in ALLOWED[key]: errors.append(f'{label}: {key}の値が不正 {value}')
  records[name+'_ids']=seen
 source_by_id={s.get('source_id'):s for s in records.get('sources',[]) if isinstance(s,dict) and s.get('source_id')}
 # --- games: slug形式・一意性 ---
 seen_slugs=set()
 for n,g in enumerate(records.get('games',[]),1):
  if not isinstance(g,dict): continue
  slug=g.get('slug')
  if slug:
   if not isinstance(slug,str) or not re.fullmatch(SLUG_PATTERN,slug): errors.append(f'games[{n}]: slug形式不正')
   elif slug in seen_slugs: errors.append(f'games[{n}]: slug重複 {slug}')
   else: seen_slugs.add(slug)
 # --- 外部キー: campaigns/knowledge → games ---
 for name in ('campaigns','knowledge'):
  for n,item in enumerate(records.get(name,[]),1):
   if isinstance(item,dict) and item.get('game_id') and item['game_id'] not in records.get('games_ids',set()):
    errors.append(f'{name}[{n}]: 存在しないgame_id {item["game_id"]}')
 # --- campaigns: source_id 外部キー ---
 for n,c in enumerate(records.get('campaigns',[]),1):
  if not isinstance(c,dict): continue
  sid=c.get('source_id')
  if sid and sid not in source_by_id: errors.append(f'campaigns[{n}]: 存在しないsource_id {sid}')
  if c.get('campaign_status') in ('掲載中','active') and not https_url(c.get('campaign_url')):
   errors.append(f'campaigns[{n}]: 掲載中なのに根拠URLなし')
 # --- knowledge: source外部キー・種別一致・topic_slug・steps構造 ---
 topic_seen={}
 for n,k in enumerate(records.get('knowledge',[]),1):
  if not isinstance(k,dict): continue
  sid=k.get('source_id')
  if sid and sid not in source_by_id: errors.append(f'knowledge[{n}]: 存在しないsource_id {sid}')
  elif sid in source_by_id:
   src=source_by_id[sid]
   if k.get('source_type') and src.get('source_type') and k['source_type']!=src['source_type']:
    errors.append(f'knowledge[{n}]: source_typeが出典台帳と不一致 ({k["source_type"]} != {src["source_type"]})')
  ts=k.get('topic_slug')
  if ts:
   if not isinstance(ts,str) or not re.fullmatch(SLUG_PATTERN,ts): errors.append(f'knowledge[{n}]: topic_slug形式不正')
   else:
    key=(k.get('game_id'),ts)
    if key in topic_seen: errors.append(f'knowledge[{n}]: 同一ゲーム内でtopic_slug重複 {ts}')
    else: topic_seen[key]=n
  steps=k.get('steps')
  if steps not in (None,'',[]):
   if not isinstance(steps,list): errors.append(f'knowledge[{n}]: stepsは配列必須')
   else:
    for j,s in enumerate(steps,1):
     if not isinstance(s,dict): errors.append(f'knowledge[{n}]: steps[{j}]はobject必須'); continue
     if not str(s.get('text') or '').strip(): errors.append(f'knowledge[{n}]: steps[{j}].textが空')
 # --- campaign_history: 外部キーと付け忘れ検出 ---
 history_by_campaign={}
 for n,h in enumerate(records.get('campaign_history',[]),1):
  if not isinstance(h,dict): continue
  cid=h.get('campaign_id')
  if cid:
   if cid not in records.get('campaigns_ids',set()): errors.append(f'campaign_history[{n}]: 存在しないcampaign_id {cid}')
   else: history_by_campaign.setdefault(cid,[]).append(h)
  sid=h.get('source_id')
  if sid and sid not in source_by_id: errors.append(f'campaign_history[{n}]: 存在しないsource_id {sid}')
 for n,c in enumerate(records.get('campaigns',[]),1):
  if not isinstance(c,dict): continue
  if c.get('campaign_status') in HISTORY_REQUIRED_STATUS and c.get('campaign_id') not in history_by_campaign:
   errors.append(f'campaigns[{n}]: 状態が「{c["campaign_status"]}」だがcampaign_historyに履歴がありません')
 # --- 公開ゲート: games（攻略はknowledge台帳から判定する。guide_sectionsは使わない） ---
 knowledge_by_game={}
 for k in records.get('knowledge',[]):
  if isinstance(k,dict) and k.get('game_id'): knowledge_by_game.setdefault(k['game_id'],[]).append(k)
 for n,g in enumerate(records.get('games',[]),1):
  if not isinstance(g,dict): continue
  if g.get('eligibility_status') in ELIGIBLE and not https_url(g.get('eligibility_evidence')): errors.append(f'games[{n}]: 対象確認済みなのに掲載根拠URLなし')
  if g.get('publication_status') in PUBLISHED:
   for key in ('official_title','official_game_url','eligibility_evidence','first_checked_at','last_checked_at','wiki_summary'):
    if not g.get(key): errors.append(f'games[{n}]: 公開状態なのに{key}なし')
   if g.get('info_rank') not in PUBLISHABLE_RANKS: errors.append(f'games[{n}]: 公開状態なのに情報ランクがA〜Cではない ({g.get("info_rank")})')
   ks=knowledge_by_game.get(g.get('game_id'),[])
   if not ks: errors.append(f'games[{n}]: 公開状態なのにknowledge台帳に攻略情報なし')
   elif sum(knowledge_body_len(k) for k in ks)<100: errors.append(f'games[{n}]: 攻略本文が短すぎます（knowledge合計100文字以上必要）')
 if errors:
  print('\n'.join('FAIL: '+e for e in errors)); return 1
 counts=', '.join(f'{k}={len(records.get(k,[]))}' for k in TABLES)
 print(f'PASS: {counts}。必須項目・一意ID・外部キー・出典整合性・URL・情報ランク・履歴・公開品質ゲートを検査。'); return 0
if __name__=='__main__': sys.exit(main())
