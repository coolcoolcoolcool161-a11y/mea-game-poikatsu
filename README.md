# ゲームポイ活ブログ（mea-game-poikatsu）

メアのポイ活メディア「ゲームポイ活ブログ」の独立サイト版。Astro＋Markdownで構築し、Cloudflare Pages（Free）で公開する。旧サイト（muse.ai）は移行完了＋ユーザー最終承認があるまで削除しない。

## 公開URL（暫定）

- https://mea-game-poikatsu.pages.dev （Cloudflare Pagesのプロジェクト作成時にサブドメインが確定したら `astro.config.mjs`・`public/robots.txt`・`public/sitemap.xml` のURLを書き換えること）

## 内容

- 記事：全19サービス分の個別記事ページ（`src/content/articles/`）。メインクエスト＝Freecash、注目クエスト＝ポケカツ
- トップページ：メインクエスト、注目クエスト、報酬ランキング13件、カテゴリ別クエスト一覧、攻略チャート4ステップ、FAQ 6件、姉妹ブログ
- カテゴリページ：ゲーム・ガチャ・買い物／ポイントサイト／動画・SNS／決済・銀行・通信／歩数・CM・予想アプリ／AIアシスタント
- サイト内検索：`/search/`（ビルド時に `/search-index.json` を生成し、ブラウザ内で絞り込み）
- 法務ページ：広告・紹介報酬に関する表記／プライバシーポリシー／利用規約・免責事項（旧サイトの文言をそのまま移行）
- SEO：ページごとの固有title・meta description・canonical・XMLサイトマップ・robots.txt・OGP・JSON-LD（WebPage／ItemList／FAQPage／Article／BreadcrumbList）・パンくず・内部リンク・モバイル対応。JavaScriptなしでも記事本文はHTMLに含まれる。

## 紹介コード・URLの扱い

- コード・紹介URL・特典額・条件は `src/content/articles/*.md` のfrontmatterと本文に記載。変更するときは `~/workspace/*-referral-post.txt` と台帳 `~/workspace/site-migration-inventory.md` §4.1 で照合すること。
- **注意：ワラウの紹介URLは `https://www.warau.jp/friend/reg/bEs5`、コードは `bEs7`。公式バナーHTMLの `/boav` は別物で使わないこと。**
- ワラウのレートは公式確認で **1pt＝1円**（ワラウコインは別物で10コイン＝1pt）。
- トクエルのファイル名は `tokueru.md` が正綴り（公式ドメイン tokueru.jp）。`tokueu.md` は誤り。

## 広告

- 忍者AdMaxの同期タグ2枠（SP ID 1239768・PC ID 1239769）を `src/components/AdSlot.astro` で3箇所（トップページ）・2箇所（記事ページ）に配置。同一タグの複数箇所流用は公式未確認のため、PCで表示されない場合は箇所ごとに枠を作り直すこと。

## GA4（未設定）

- 測定IDは `src/data/site.ts` の `gaMeasurementId` に入れる。空のままならGA4スクリプトは出力されない。GA4プロパティの作成はユーザーのGoogleアカウントでの操作が必要。

## 画像について

- 画像6ファイル（`public/images/`）はGitHub連携の `push_files`（UTF-8テキストのみ対応）ではプッシュできないため、GitHub Web UIで別途アップロードすること。

## 開発・ビルド

```bash
npm install
npm run dev      # 開発サーバー
npm run build    # 静的HTMLを dist/ に出力
npm run preview  # ビルド結果の確認
```
