#!/usr/bin/env python3
"""Regression tests for S07 cross-ledger validation (5 ledgers, ranks A-E)."""
import json, subprocess, sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]; D=R/'data'
names=('games','campaigns','knowledge','sources','campaign_history')
original={n:(D/f'{n}.json').read_text(encoding='utf-8') for n in names}
def write(n,v): (D/f'{n}.json').write_text(json.dumps(v,ensure_ascii=False),encoding='utf-8')
def run(): return subprocess.run([sys.executable,str(R/'scripts'/'validate_data.py')],capture_output=True,text=True)
def clear():
 for n in names: write(n,[])
GAME={'game_id':'G1','slug':'sample','official_title':'検証用ゲーム','official_game_url':'https://example.invalid/game','eligibility_status':'確認済み','eligibility_evidence':'https://example.invalid/listing','first_checked_at':'2026-11-24 JST','last_checked_at':'2026-11-24 JST','publication_status':'下書き','info_rank':'A'}
SOURCE={'source_id':'S1','source_type':'公式','publisher':'検証用発信元','title':'検証用出典','url':'https://example.invalid/source','checked_at':'2026-11-24 JST','conditions':'検証用条件','limitations':'検証用制約'}
KNOW={'knowledge_id':'K1','game_id':'G1','topic':'検証テーマ','topic_slug':'test-topic','conclusion':'検証用の結論です。','answer_scope':'検証用範囲','steps':[{'heading':'手順見出し','text':'検証用の手順本文です。'}],'source_type':'公式','source_id':'S1','checked_at':'2026-11-24 JST','confidence_note':'検証用の確度メモ','info_rank':'A'}
try:
 clear()
 ok=run(); assert ok.returncode==0,ok.stdout+ok.stderr
 # Dangling game reference is rejected.
 write('campaigns',[{'campaign_id':'C1','game_id':'MISSING'}])
 bad=run(); assert bad.returncode and '存在しないgame_id' in bad.stdout
 # Duplicate IDs are rejected even when references otherwise resolve.
 write('campaigns',[{'campaign_id':'C1'},{'campaign_id':'C1'}])
 bad=run(); assert bad.returncode and 'campaign_id重複' in bad.stdout
 # Source identity and source-type disagreement are rejected.
 write('games',[GAME]); write('sources',[SOURCE])
 k=dict(KNOW); k['source_type']='第三者'; write('knowledge',[k])
 bad=run(); assert bad.returncode and 'source_typeが出典台帳と不一致' in bad.stdout
 # Campaign source_id must resolve to the sources ledger.
 clear(); write('games',[GAME]); write('sources',[SOURCE])
 write('campaigns',[{'campaign_id':'C2','game_id':'G1','source_id':'MISSING','service_name':'検証サービス','campaign_title':'検証案件','completion_condition':'検証条件','campaign_url':'https://example.invalid/c','campaign_status':'掲載中','checked_at':'2026-11-24 JST','info_rank':'A'}])
 bad=run(); assert bad.returncode and '存在しないsource_id' in bad.stdout
 # topic_slug is required and must be unique within the same game.
 clear(); write('games',[GAME]); write('sources',[SOURCE])
 k=dict(KNOW); del k['topic_slug']; write('knowledge',[k])
 bad=run(); assert bad.returncode and '必須項目 topic_slug が空' in bad.stdout
 k1=dict(KNOW); k2=dict(KNOW); k2['knowledge_id']='K2'; write('knowledge',[k1,k2])
 bad=run(); assert bad.returncode and 'topic_slug重複' in bad.stdout
 # A published game no longer needs guide_sections; knowledge drives the gate.
 clear(); write('games',[dict(GAME,publication_status='公開',wiki_summary='検証用の要約です。')]); write('sources',[SOURCE]); write('knowledge',[KNOW])
 bad=run(); assert bad.returncode and '短すぎます' in bad.stdout  # 本文不足は拒否される
 k=dict(KNOW); k['conclusion']='検証用の結論です。'+'攻略本文の検証用テキストです。'*8; k['steps']=[{'heading':'手順','text':'検証用の手順本文です。'*6}]
 write('knowledge',[k])
 ok=run(); assert ok.returncode==0,ok.stdout+ok.stderr  # guide_sectionsなしで公開ゲートを通る
 # Rank E cannot be published (ranks are A-E from the research policy).
 write('games',[dict(GAME,publication_status='公開',wiki_summary='検証用の要約です。',info_rank='E')])
 bad=run(); assert bad.returncode and '情報ランクがA〜Cではない' in bad.stdout
 # Changed/ended campaigns require a campaign_history record (付け忘れ検出).
 clear(); write('games',[GAME]); write('sources',[SOURCE])
 write('campaigns',[{'campaign_id':'C3','game_id':'G1','source_id':'S1','service_name':'検証サービス','campaign_title':'検証案件','completion_condition':'検証条件','campaign_url':'https://example.invalid/c','campaign_status':'変更','checked_at':'2026-11-24 JST','info_rank':'A'}])
 bad=run(); assert bad.returncode and 'campaign_historyに履歴がありません' in bad.stdout
 write('campaign_history',[{'history_id':'H1','campaign_id':'C3','changed_at':'2026-11-24 JST','change_type':'条件変更'}])
 ok=run(); assert ok.returncode==0,ok.stdout+ok.stderr
 # History must reference an existing campaign.
 write('campaign_history',[{'history_id':'H2','campaign_id':'MISSING','changed_at':'2026-11-24 JST','change_type':'条件変更'}])
 bad=run(); assert bad.returncode and '存在しないcampaign_id' in bad.stdout
 # Campaign URL must be HTTPS and present for an active listing.
 clear(); write('games',[GAME]); write('sources',[SOURCE])
 write('campaigns',[{'campaign_id':'C4','game_id':'G1','source_id':'S1','service_name':'検証サービス','campaign_title':'検証案件','completion_condition':'検証条件','campaign_url':'http://invalid.test','campaign_status':'掲載中','checked_at':'2026-11-24 JST','info_rank':'A'}])
 bad=run(); assert bad.returncode and 'https URL必須' in bad.stdout
 print('PASS: 空台帳・外部キー欠落・ID重複・出典種別不一致・campaigns.source_id・topic_slug必須/一意性・guide_sections廃止後の公開ゲート・ランクE公開拒否・履歴付け忘れ検出・案件根拠URL')
finally:
 for n,v in original.items(): (D/f'{n}.json').write_text(v,encoding='utf-8')
