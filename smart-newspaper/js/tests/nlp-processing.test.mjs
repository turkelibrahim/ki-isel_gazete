import test from 'node:test';
import assert from 'node:assert/strict';
import NewsProcessingService from '../../services/newsProcessingService.js';

test('NLP detects Turkish and selects Turkish pipeline', () => {
  const result = NewsProcessingService.detectLanguage('Türkiye ekonomisi bugün önemli bir açıklama yaptı ve piyasalar bunu yakından izliyor.');
  assert.equal(result.detected_lang, 'tr');
  assert.equal(NewsProcessingService.selectPipeline(result), 'turkish');
});

test('NLP detects English and selects English pipeline', () => {
  const result = NewsProcessingService.detectLanguage('The government announced new market rules and the economy is growing this year.');
  assert.equal(result.detected_lang, 'en');
  assert.equal(NewsProcessingService.selectPipeline(result), 'english');
});

test('NLP empty text is unknown and generic', () => {
  const result = NewsProcessingService.detectLanguage('');
  assert.equal(result.detected_lang, 'unknown');
  assert.equal(NewsProcessingService.selectPipeline(result), 'generic');
});

test('NLP processArticle adds TR/EN and newspaper fields', () => {
  const article = {
    id: '1',
    title: 'Merkez Bankası faiz kararını açıkladı',
    summary: 'TCMB politika faizini açıkladı.',
    content: 'Türkiye Cumhuriyet Merkez Bankası piyasaların beklediği faiz kararını açıkladı.',
    sourceName: 'Demo Kaynak',
    category: 'Ekonomi',
    url: 'https://example.com/news?utm_source=x'
  };
  const enriched = NewsProcessingService.enrichFeedArticle(article);
  assert.equal(enriched.detected_lang, 'tr');
  assert.ok(enriched.title_tr);
  assert.ok(enriched.newspaper_title);
  assert.ok(enriched.dedupe_key);
  assert.ok(enriched.cluster_id);
});

test('NLP canonicalizeUrl removes tracking params', () => {
  const url = NewsProcessingService.canonicalizeUrl('http://example.com/path/?utm_source=x&fbclid=y&id=1#section');
  assert.ok(!url.includes('utm_source'));
  assert.ok(!url.includes('fbclid'));
  assert.ok(!url.includes('#'));
});
