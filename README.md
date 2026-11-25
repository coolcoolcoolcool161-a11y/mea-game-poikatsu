# S07 ポイ活ゲーム攻略Wiki 静的サイト

## 目的
対象ゲームの調査・選定はMuseが担当する。本フォルダは、5台帳からサイト全体を静的生成する基盤。

## 構成
- `index.html`：トップページ（ビルドで台帳から再生成される）
- `games/index.html`：ビルドで生成されるゲーム一覧（公開ゲームがない場合はnoindex）
- `games/{game-slug}/`：ゲーム詳細、`/games/{game-slug}/{topic-slug}/`：攻略テーマ、`/games/{game-slug}/conditions/`：達成条件・検証記録（いずれもビルド生成）
- `about/`・`editorial-policy/`・`how-to-read/`：共通案内ページ（静的。ビルド時にcanonical・計測・ベースパスを後処理する）
- `templates/`：ゲーム詳細・攻略テーマ・達成条件ページのテンプレート（生成ページと同構造。noindex。このファイル自体は公開しない）
- `data/games.json`：ゲーム台帳（初期状態は空配列）
- `data/campaigns.json`：サービス・時期・条件単位で分離する案件台帳（初期状態は空配列）
- `data/knowledge.json`：ゲーム固有の攻略情報台帳。攻略本文の唯一の管理元（初期状態は空配列）
- `data/sources.json`：出典台帳（初期状態は空配列）
- `data/campaign_history.json`：案件の状態・条件変更の履歴台帳（初期状態は空配列）
- `schema/`：台帳スキーマCSV（02〜05＋23_案件履歴台帳スキーマ）。検証はこの同梱CSVを読むため、配置先に依存しない
- `scripts/validate_data.py`：5台帳の必須項目・一意ID・外部キー・出典整合性・URL・情報ランク・履歴・公開条件チェック
- `scripts/build_site.py`：ビルド冒頭で検証を実行し、5台帳からトップ・一覧・詳細・攻略・条件を静的生成
- `scripts/audit_site.py`：HTML・リンク・SEO・アクセシビリティ・CSSのオフライン監査
- `assets/`：CSS / JS（ゲーム名検索と referral_click 計測）

## データの約束（確定仕様）
- 攻略本文は `knowledge.json` に一本化する。`games.json` に `guide_sections` は持たない。
- `knowledge.topic_slug` は必須（小文字英数字とハイフン、同一ゲーム内で一意）。URLは `/games/{game-slug}/{topic-slug}/`。
- `campaigns.source_id` で出典台帳へ接続する。案件原文（`completion_condition_original`）と要約（`completion_condition`）は区別する。
- 情報ランクは調査ポリシーの **A〜E** に統一する（A:公式で現行確認済／B:公式だが現行性に不明点／C:複数外部の裏付け／D:単独口コミ・参考／E:未確認）。公開にはA〜Cが必要。
- 案件の状態が「変更／終了／再開」になったら `campaign_history.json` に旧値・確認日・根拠とともに履歴を残す。履歴がない場合は検証で失敗する。
- 実情報がない台帳は空配列 `[]` を維持する。テストデータは本番台帳に残さない。

## データ投入・生成
Python 3が必要。外部ライブラリ・外部APIは不要。

```bash
python scripts/validate_data.py
python scripts/build_site.py   # 冒頭で検証を自動実行し、失敗時は生成を中止する
python scripts/audit_site.py
python tests/test_data_integrity.py
python tests/test_build.py
python tests/test_audit.py
```

生成判定とindex判定は分離している。生成されるのは「対象資格が確認済み かつ 公開状態」のゲームだけ。index可否はページ種別ごとに判定する（詳細・攻略は根拠・独自価値・ランク等を満たす場合のみ、条件ページは原則noindexで公式根拠が揃う場合のみ、一覧はindex可能な詳細がある場合のみ）。

## ベースパスと実ホストURL（公開ビルド時）
現行URL `/mea-game-poikatsu/` を維持するため、全リンクはベースパス付きで生成する。

- `S07_SITE_BASE_PATH`：ベースパス。既定は `/mea-game-poikatsu`。
- `S07_SITE_BASE_URL`：実ホスト。パス付きで指定できる（例：`https://mea-poikatsu.github.io/mea-game-poikatsu`）。設定した場合のみ canonical・sitemap・robots の絶対URLを生成する。HTTP・query・fragment付きは拒否する。パスの不一致（BASE_PATHと異なる）も拒否する。
- 未設定の場合は canonical を出力せず、robots/sitemap のホストはプレースホルダーに戻す。架空のホストを設定してはならない。

## 計測
全ページに GA4（`G-8BB8V3DRW8`）を組み込む。案件CTA（条件ページの掲載中案件リンク）には `data-ref-service` / `data-ref-placement="conditions"` を付け、`assets/site.js` が `referral_click` イベント（`service` / `placement` / `site_id: 's07'`）を送信する。終了案件にはCTAを設置しない。広告は入れない。開示はフッター表記のみとする。

## 検索
ゲーム名検索のみをトップとゲーム一覧に実装している。静的HTML内のゲームカードをJavaScriptで絞り込む方式で、外部通信は行わない。JavaScript無効時でも一覧のリンクからゲームに到達できる。ジャンル・難易度・OS等の絞り込みは仕様外のため追加しない。

## ローカル確認
このフォルダで `python -m http.server 8000` を実行し、`http://localhost:8000/mea-game-poikatsu/` 相当のパスで開く（ベースパス付きで配信する場合は親フォルダから配信する）。

## 公開前に必ず行うこと
1. 実ホストURLを `S07_SITE_BASE_URL` に設定してからビルドする。
2. ゲーム固有ページは、対象資格・出典・独自情報・確認日が揃うまで公開しない。
3. テンプレートのプレースホルダーを残したまま公開しない。
4. 実プレイしていない内容を実測・体験談と表現しない。
5. `validate_data.py`・`build_site.py`・`audit_site.py`・テスト一式を実行し、生成結果を確認する。

## 依存関係
外部JavaScriptライブラリ、外部フォント、外部APIを使用しない。HTML/CSS/JavaScript/Python標準ライブラリのみ。フォントはOS標準の日本語ゴシック系のみ。

## オフライン品質監査
`python scripts/audit_site.py` でHTML構造、内部リンク（ベースパスを除去して解決）、title/description/robots、viewport、H1、画像alt、見出し階層、sitemap内のnoindex混入、モバイル向けCSSを監査する。終了コード1はエラーあり。canonical未設定と実ホストのプレースホルダーは、実URLが未確定のため警告として扱う。

この監査はソース静的検査であり、実ブラウザ描画・実機でのモバイル表示・Core Web Vitals・検索エンジンの実クロール結果を保証しない。公開前に実ホストで追加確認すること。

## 静的ページ方式（page_mode=static）のゲーム

- 台帳 `games.json` の `page_mode` が `static` のゲームは、詳細ページを台帳から生成せず、`static-perfect/<slug>/` に置いた完璧版ページ群（`<name>.html.txt` と画像の `img/<name>.b64`）をビルド時に本番パスへ配置する（現在はパズル＆サバイバルが該当）。
- 配置時に本番用変換（canonical・GA4・計測属性・パンくず/ナビのリンク先・mainランドマーク・description/robots の注入）を行う。`board.html` はサイトマップに載せない。
- 完璧版の内容は台帳 `knowledge.json` に `static_page: true` のエントリとして登録し、台帳側を正とする（`page_file` が対応ファイル名）。
- 旧来の生成トピック（k001/k005）と条件ページは従来どおり生成され、旧URLを維持する。
- `data/icons.json` はゲームアイコン（App Store）の対応表で、トップページとゲーム一覧のカードで使う。
