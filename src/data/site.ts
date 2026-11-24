// サイト共通の設定。GA4測定IDはユーザーから提供され次第ここに入れる。
// 空のままならGA4スクリプトは出力されない。
export const SITE = {
  name: 'ポイゲークエスト',
  operator: 'メア',
  siteUrl: 'https://mea-poikatsu.github.io/mea-game-poikatsu',
  description:
    'ゲームをプレイしてポイントが貯まる「ゲームポイ活」に使える紹介コード・招待コードを、全19サービスぶんクエスト形式でまとめました。Freecash 3BQLXB（初回DLで1,430円分）、ポケカツ初回チャージ90%OFF、ワラウ最大2,500pt、モッピー最大7,000P、楽天モバイル最大13,000ポイントなど、特典額・条件・登録リンク・コピーボタン付きで攻略できます。',
  dateModified: '2026-11-21',
  gaMeasurementId: 'G-8BB8V3DRW8',
  xAccount: 'https://x.com/pppppuririn',
  hubUrl:
    'https://mea-poikatsu.github.io/mea-poikatsu-media/',
} as const;

// Astro 5ではcontent collectionのentry.idに拡張子（.md）が付くため、URL用スラッグに変換する
export const slugOf = (id: string) => id.replace(/\.md$/, '');

export const CATEGORIES = [
  { slug: 'game-gacha', name: 'ゲーム・ガチャ・買い物' },
  { slug: 'point-sites', name: 'ポイントサイト' },
  { slug: 'sns-video', name: '動画・SNS' },
  { slug: 'payment-bank', name: '決済・銀行・通信' },
  { slug: 'walking-apps', name: '歩数・CM・予想アプリ' },
  { slug: 'ai', name: 'AIアシスタント' },
] as const;

export type CategorySlug = (typeof CATEGORIES)[number]['slug'];

export const CATEGORY_NAMES: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.slug, c.name]),
);

// 報酬ランキング（旧サイトの表と同じ順序・金額で移行）
export const RANKING = [
  { rank: 1, slug: 'rakuten-mobile', name: '楽天モバイル', benefit: '最大13,000pt', code: 'リンク型' },
  { rank: 2, slug: 'moppy', name: 'モッピー', benefit: '最大7,000P', code: '7xaGA123' },
  { rank: 3, slug: 'tiktok', name: 'TikTok', benefit: '6,000円分', code: '284097117' },
  { rank: 4, slug: 'warau', name: 'ワラウ', benefit: '最大2,500pt', code: 'bEs7' },
  { rank: 5, slug: 'hapitas', name: 'ハピタス', benefit: '最大2,300P', code: 'INXAHV' },
  { rank: 6, slug: 'olive', name: 'SMBC Olive', benefit: 'Vポイント1,000円相当', code: 'FF89103-3439377' },
  { rank: 7, slug: 'freecash', name: 'Freecash ★メイン', benefit: '初回DLで1,430円分', code: '3BQLXB' },
  { rank: 8, slug: 'tiktok-lite', name: 'TikTok Lite', benefit: '1,400円分', code: '890270647' },
  { rank: 9, slug: 'pokekatsu', name: 'ポケカツ', benefit: '初回チャージ90%OFF', code: '2BGZ325P' },
  { rank: 10, slug: 'mercari', name: 'メルカリ', benefit: '500円分', code: 'HKRDNM' },
  { rank: 11, slug: 'paypay', name: 'PayPay', benefit: '300pt', code: '02-49XLFP8' },
  { rank: 12, slug: 'airwallet', name: 'エアウォレット', benefit: '300円分', code: '6nzih9k' },
  { rank: 13, slug: 'orikuji', name: 'オリくじ', benefit: '500ptプレゼント', code: 'AZ3pOY' },
] as const;

// 姉妹ブログ（旧muse.ai URL。2026-11-21にGitHub Pagesの新URLへ更新済み）
export const SISTER_BLOGS = [
  {
    name: 'ポイ活レビュー帖',
    note: '総合版。王道レイアウトで全サービスを特集＋ランキングで紹介。',
    url: 'https://mea-poikatsu.github.io/mea-poikatsu-blog/',
  },
  {
    name: 'ポイランク',
    note: 'メアのポイランク特化。おすすめ順に一気に見比べられます。',
    url: 'https://mea-poikatsu.github.io/mea-ranking/',
  },
  {
    name: 'コードサーチ',
    note: '検索・絞り込み特化。目的のコードを最速で探せるデータベース風。',
    url: 'https://mea-poikatsu.github.io/mea-code-search/',
  },
  {
    name: 'ポイレーダー',
    note: '読み物スタイル。記事を読みながらゆっくり選べるマガジン風。',
    url: 'https://mea-poikatsu.github.io/mea-poikatsu-magazine/',
  },
  {
    name: 'ポイ活のトリセツ',
    note: 'シンプル案内版。大きな文字とボタンで迷わず登録できます。',
    url: 'https://mea-poikatsu.github.io/mea-kantan-guide/',
  },
] as const;

export const FAQS = [
  {
    q: 'ゲームポイ活とは何ですか？',
    a: 'ゲームをプレイしたり、ゲーム案件のあるポイントサイトを利用したりしてポイントを貯める活動です。このブログでは、メアが紹介コード・招待コードを使って通常登録よりお得に始められるサービスをまとめているよ。',
  },
  {
    q: 'Freecashの紹介コードはどこで使いますか？',
    a: '紹介リンク（https://freecash.com/r/3BQLXB）から登録すると紹介コード3BQLXBが適用されます。招待コードを入力して初回DLすると1,430円分がもらえます。',
  },
  {
    q: 'ポケカツの招待コードはいつ入力しますか？',
    a: 'ポケカツ登録時（またはマイページの招待コード入力欄）に招待コード2BGZ325Pを入力してください。登録は無料、初回チャージは90%OFFです。',
  },
  {
    q: '紹介コードは後から入力できますか？',
    a: 'ほとんどのサービスで紹介コードの入力は新規登録時のみ有効で、後からの入力では特典が付きません。まだ登録していないサービスから優先して、このページ経由で登録するのがメアのおすすめだよ。',
  },
  {
    q: '特典は本当に無料でもらえますか？',
    a: '登録自体は全サービス無料だよ。特典には条件（広告利用・支払い・口座残高など）がある場合があり、各クエストの条件欄に明記しています。条件を満たせば追加費用なしで特典がもらえるサービスがほとんどです♪',
  },
  {
    q: 'このページから登録すると、メアにも報酬が入るのですか？',
    a: 'はい、その通りです♪ このページ経由で登録し条件が満たされると、あなたに特典が付与されるとともに、紹介者であるメアにも各サービスから紹介報酬が付与される場合があります。あなたの特典が減ったり、利用料金が上乗せされたりすることはありません。詳しくは「広告・紹介報酬に関する表記」をご覧ください。',
  },
] as const;
