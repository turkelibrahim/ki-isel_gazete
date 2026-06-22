import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const {
  classifyArticle,
  classifyArticles,
  groupArticlesByCategory,
  sortArticlesForPersonalNewspaper,
  CATEGORY_CONFIG
} = require('../../services/categoryService.js');

function article(title, summary = '', content = '') {
  return { title, summary, content, fullText: content, publishedAt: '2026-06-22T09:00:00Z' };
}

test('category service classifies sports, economy and technology', () => {
  assert.equal(classifyArticle(article('Galatasaray derbide Fenerbahçe ile karşılaştı', 'Süper Lig maçında gol ve transfer gündemi vardı.')).category, 'Spor');
  assert.equal(classifyArticle(article('Merkez Bankası faiz kararını açıkladı', 'Dolar, euro ve enflasyon beklentisi piyasaları etkiledi.')).category, 'Ekonomi');
  assert.equal(classifyArticle(article('OpenAI yeni yapay zeka modelini tanıttı', 'Yazılım ve teknoloji ekipleri için ChatGPT API yenilendi.')).category, 'Teknoloji');
});

test('category service separates politics from agenda', () => {
  const politics = classifyArticle(article('TBMM yeni yasa teklifini görüşüyor', 'Parti grupları ve milletvekilleri mecliste seçim sonrası düzenlemeyi tartıştı.'));
  const agenda = classifyArticle(article('İstanbul’da zincirleme trafik kazası yaşandı', 'Polis ve belediye ekipleri bölgede güvenlik önlemi aldı.'));
  assert.equal(politics.category, 'Siyaset');
  assert.equal(agenda.category, 'Gündem');
});

test('category service detects English economy article', () => {
  const pred = classifyArticle(article('Central bank holds interest rates as inflation cools', 'Markets and stocks reacted after the economy report was published.'));
  assert.equal(pred.detected_lang, 'en');
  assert.equal(pred.category, 'Ekonomi');
});

test('category service returns Other for empty or too short content', () => {
  const empty = classifyArticle(article('', '', ''));
  const short = classifyArticle(article('Zam'));
  assert.equal(empty.category, 'Diğer');
  assert.equal(short.category, 'Diğer');
  assert.equal(short.is_category_reliable, false);
});

test('category service handles 100 article batch and card payload fields', () => {
  const batch = Array.from({ length: 100 }, (_, i) => article(`OpenAI yapay zeka platformunu güncelledi ${i}`, 'Teknoloji ve yazılım geliştiricileri için yeni API açıklandı.'));
  const enriched = classifyArticles(batch);
  assert.equal(enriched.length, 100);
  assert.equal(enriched[0].category, 'Teknoloji');
  assert.ok('category_confidence' in enriched[0]);
  assert.ok('category_source' in enriched[0]);
  assert.ok('is_category_reliable' in enriched[0]);
  assert.ok('detected_lang' in enriched[0]);
});

test('category service groups e-gazete/PDF sections and personal interests can rank technology first', () => {
  const items = [
    article('Merkez Bankası faiz kararını açıkladı', 'Dolar ve enflasyon piyasayı etkiledi.'),
    article('Galatasaray transfer görüşmelerine başladı', 'Süper Lig ekibi yeni futbolcu arıyor.'),
    article('OpenAI yeni yapay zeka aracını yayınladı', 'Teknoloji dünyasında yazılım geliştiricileri için yenilik.')
  ];
  const groups = groupArticlesByCategory(items);
  assert.ok(groups.Ekonomi.length >= 1);
  assert.ok(groups.Spor.length >= 1);
  assert.ok(groups.Teknoloji.length >= 1);
  const sorted = sortArticlesForPersonalNewspaper(items, { interests: ['Teknoloji'] });
  assert.equal(sorted[0].category, 'Teknoloji');
  assert.deepEqual(CATEGORY_CONFIG.sectionOrder.slice(0, 5), ['Gündem', 'Siyaset', 'Ekonomi', 'Spor', 'Teknoloji']);
});
