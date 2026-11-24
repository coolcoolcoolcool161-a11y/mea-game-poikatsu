// S07 ポイ活ゲーム攻略Wiki 共通スクリプト
// ・ゲーム一覧は scripts/build_site.py で静的HTML化するため、実行時データ取得は行わない。
// ・ゲーム名検索は、このページの静的HTMLに存在するゲームカードを絞り込む方式（外部通信なし）。
//   絞り込みはゲーム名のみ。ジャンル・難易度・OS等の追加フィルタは仕様外のため実装しない。
// ・referral_click 計測：案件CTA（data-ref-service / data-ref-placement 属性付きリンク）の
//   クリックを GA4 イベントとして送信する。site_id は 's07' で統一する。
(function () {
  'use strict';

  function normalize(s) {
    return (s || '').toLowerCase().replace(/\s+/g, '');
  }

  function applyFilter(form) {
    var input = form.querySelector('input[name="q"], input[type="search"]');
    var scope = form.closest('main') || document;
    var cards = scope.querySelectorAll('.game-card');
    if (!input || !cards.length) return;
    var q = normalize(input.value);
    var shown = 0;
    cards.forEach(function (card) {
      var name = normalize(card.getAttribute('data-name') || card.textContent);
      var hit = !q || name.indexOf(q) !== -1;
      card.hidden = !hit;
      if (hit) shown++;
    });
    var count = scope.querySelector('[data-search-count]');
    if (count) count.textContent = q ? '該当 ' + shown + '件 / 全' + cards.length + '件' : '全' + cards.length + '件';
    var empty = scope.querySelector('[data-search-empty]');
    if (empty) empty.hidden = shown !== 0;
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[data-game-search]').forEach(function (form) {
      var input = form.querySelector('input');
      form.addEventListener('submit', function (ev) {
        // 同一ページ内にカードがある場合はページ遷移せず絞り込む
        if (document.querySelector('.game-card')) {
          ev.preventDefault();
          applyFilter(form);
        }
      });
      if (input) {
        input.addEventListener('input', function () { applyFilter(form); });
      }
      // ゲーム一覧へ ?q= 付きで遷移してきた場合は初期状態で絞り込む
      var q = new URLSearchParams(location.search).get('q');
      if (q && input) {
        input.value = q;
        applyFilter(form);
      }
    });
  });

  // referral_click 計測（GA4）
  document.addEventListener('click', function (ev) {
    var t = ev.target;
    var a = t && t.closest ? t.closest('a[data-ref-service]') : null;
    if (!a) return;
    if (typeof window.gtag === 'function') {
      window.gtag('event', 'referral_click', {
        service: a.getAttribute('data-ref-service') || '',
        placement: a.getAttribute('data-ref-placement') || '',
        site_id: 's07'
      });
    }
  });
})();
