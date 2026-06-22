import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { canonicalizeUrl, dedupeArticles } = require('../../services/dedupeService.js');

function sample(id, title, fullText, sourceName, sourceUrl = `https://example.com/${id}?utm_source=x`) {
  return {
    id,
    title,
    fullText,
    summary: fullText.slice(0, 160),
    sourceName,
    sourceLogo: `/assets/sources/${sourceName.toLowerCase()}.svg`,
    sourceUrl,
    publishedAt: `2026-06-22T09:0${id}:00Z`,
    category: 'Gündem',
    trustScore: 60
  };
}

test('dedupe service canonicalizes tracking URLs', () => {
  assert.equal(
    canonicalizeUrl('https://www.hurriyet.com.tr/haber?id=42&utm_source=x&fbclid=y#giris'),
    'https://hurriyet.com.tr/haber?id=42'
  );
});

test('dedupe service merges near duplicate sources with card-compatible payload', () => {
  const clusters = dedupeArticles([
    sample(1, 'Bakanlık yeni destek paketini açıkladı', 'Bakanlık küçük işletmeler için yeni destek paketini açıkladı. Paket başvuruları temmuz ayında başlayacak.', 'AA'),
    sample(2, 'Bakanlık destek paketini duyurdu', 'Bakanlık küçük işletmeler için yeni destek paketini duyurdu. Başvuruların temmuz ayında başlayacağı bildirildi.', 'Hürriyet')
  ]);
  assert.equal(clusters.length, 1);
  assert.equal(clusters[0].source_count, 2);
  assert.equal(clusters[0].sourceCount, 2);
  assert.equal(clusters[0].dedupe_status, 'merged');
  assert.ok(clusters[0].cluster_id);
  assert.ok(clusters[0].sources[0].source_name);
  assert.ok(clusters[0].sources[0].sourceIcon);
});

test('dedupe service keeps same title with different body as separate stories', () => {
  const clusters = dedupeArticles([
    sample(1, 'Son dakika gelişmesi', "Ankara'da ulaşımla ilgili yeni metro hattı çalışmaları bugün başladı ve belediye takvimi duyurdu.", 'AA'),
    sample(2, 'Son dakika gelişmesi', "İstanbul'da etkili olan sağanak yağış nedeniyle bazı vapur seferleri geçici olarak iptal edildi.", 'TRT')
  ]);
  assert.equal(clusters.length, 2);
});
