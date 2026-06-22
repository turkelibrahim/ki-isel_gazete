import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeHeroArticle, selectHeroArticles } from '../components/heroSlider.js';

test('HeroSlider normalizes backend feed field names for the center main feed', () => {
  const article = normalizeHeroArticle({
    news_id: 'n1',
    headline: 'Orta akış haberi',
    description: 'Özet',
    source_name: 'TRT Haber',
    published_at: '2026-06-22T10:00:00+03:00',
    image_url: '/assets/news-placeholder.jpg',
    labels: ['Gündem'],
    source_count: 3,
    sources: [{ sourceName: 'AA' }, { sourceName: 'TRT Haber' }]
  });

  assert.equal(article.id, 'n1');
  assert.equal(article.title, 'Orta akış haberi');
  assert.equal(article.source, 'TRT Haber');
  assert.equal(article.category, 'Gündem');
  assert.equal(article.imageUrl, '/assets/news-placeholder.jpg');
  assert.equal(article.sourceCount, 3);
  assert.equal(article.sources.length, 2);
});

test('HeroSlider uses regular articles when no explicit featured flags exist', () => {
  const selected = selectHeroArticles([
    { id: 'a1', title: 'Normal haber 1', summary: 'Özet', source: 'Kaynak' },
    { id: 'a2', title: 'Normal haber 2', summary: 'Özet', source: 'Kaynak' }
  ], 5);

  assert.equal(selected.length, 2);
  assert.equal(selected[0].title, 'Normal haber 1');
});
