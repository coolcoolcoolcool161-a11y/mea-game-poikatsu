#!/usr/bin/env bash
# 既存の GitHub Pages ワークフロー（npm ci → npm run build → ./dist を配信）から呼ばれるビルド本体。
# ワークフローファイル自体は GitHub App の権限の都合で変更できないため、実処理はここに集約する。
set -euo pipefail
export S07_SITE_BASE_URL=https://mea-poikatsu.github.io

python3 scripts/build_site.py
python3 scripts/audit_site.py

rm -rf dist
mkdir -p dist
cp index.html sitemap.xml robots.txt dist/
cp -r games about editorial-policy how-to-read assets dist/
# ファビコン・ロゴ（リポジトリ直下に Web UI で配置したバイナリ）をサイトルートへ
for f in favicon.ico favicon-16.png favicon-32.png favicon-180.png favicon-192.png favicon-512.png logo-symbol.png; do
  if [ -f "$f" ]; then cp "$f" dist/; else echo "WARN: $f がリポジトリ直下にありません" >&2; fi
done
# GSC所有権確認ファイルは監査（*.html走査）対象外にするため repo 内では .txt 付きで保持し、ここで本来の名前に戻す
cp static/google3ee751214639f822.html.txt dist/google3ee751214639f822.html
cp static/ee3206d3bc3c40a990d1906f880a07df.txt dist/
ls -la dist/
