import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { normalizeEvent, getFallbackImage } = require('../../server/events/normalizeEvent.js');
const { dedupeEvents, eventSimilarity } = require('../../server/events/eventAggregator.js');

test('normalizeEvent maps raw source event to standard model with image fallback', () => {
  const event = normalizeEvent({ title: 'Caz Akşamı', category: 'konser', city: 'İstanbul', startDate: '2026-06-21T20:00:00Z' }, { name: 'Biletix' });
  assert.equal(event.category, 'Konser');
  assert.equal(event.city, 'İstanbul');
  assert.ok(event.imageUrl.includes('images.unsplash.com'));
  assert.ok(event.sourceLogo.includes('/assets/events/sources/'));
});

test('fallback image returns category-specific professional image', () => {
  assert.ok(getFallbackImage('Tiyatro').includes('images.unsplash.com'));
  assert.ok(getFallbackImage('Bilinmeyen').includes('images.unsplash.com'));
});

test('dedupeEvents merges same event from different ticket sources and keeps different event separate', () => {
  const raw = [
    normalizeEvent({ title: 'Yalın Parça Pinçik Akustik', category: 'Konser', city: 'İstanbul', venueName: 'Zorlu PSM', startDate: '2026-06-21T20:00:00Z', ticketUrl: 'https://biletix.com/a' }, { name: 'Biletix' }),
    normalizeEvent({ title: 'Yalın - Parça Pinçik Akustik Konseri', category: 'Konser', city: 'İstanbul', venueName: 'Zorlu PSM', startDate: '2026-06-21T21:00:00Z', ticketUrl: 'https://bubilet.com/a' }, { name: 'Bubilet' }),
    normalizeEvent({ title: 'Fenerbahçe Galatasaray', category: 'Spor', city: 'İstanbul', venueName: 'Ülker Stadyumu', startDate: '2026-06-21T20:00:00Z' }, { name: 'Passo' })
  ];
  const clusters = dedupeEvents(raw);
  assert.equal(clusters.length, 2);
  const concert = clusters.find((item) => item.title.includes('Yalın'));
  assert.equal(concert.sourceCount, 2);
});

test('eventSimilarity is high for same title/date/venue and lower for unrelated event', () => {
  const a = normalizeEvent({ title: 'Hayal Fest 2024', category: 'Festival', city: 'İstanbul', venueName: 'Parkorman', startDate: '2026-06-21T16:00:00Z' }, { name: 'Passo' });
  const b = normalizeEvent({ title: 'Hayal Festivali 2024', category: 'Festival', city: 'İstanbul', venueName: 'Parkorman', startDate: '2026-06-21T18:00:00Z' }, { name: 'Biletix' });
  const c = normalizeEvent({ title: 'Bir Delinin Hatıra Defteri', category: 'Tiyatro', city: 'İstanbul', venueName: 'DasDas', startDate: '2026-06-21T20:30:00Z' }, { name: 'Bubilet' });
  assert.ok(eventSimilarity(a, b) >= 0.72);
  assert.ok(eventSimilarity(a, c) < 0.72);
});

test('smart event source catalog includes Etkinlik.io, Biletix, Biletinial, Passo and culture sources', () => {
  const { SMART_EVENT_SOURCES, EVENT_CATEGORY_MAP, getEventSourceSummary } = require('../../server/events/eventSources.js');
  const names = SMART_EVENT_SOURCES.map((item) => item.name);
  assert.ok(SMART_EVENT_SOURCES.length >= 35);
  assert.ok(names.includes('Etkinlik.io Tüm Etkinlikler'));
  assert.ok(names.includes('Biletix Türkiye'));
  assert.ok(names.includes('Biletinial Türkiye'));
  assert.ok(names.includes('Passo Türkiye'));
  assert.ok(names.includes('Kültür Yolu Festivali'));
  assert.ok(Array.isArray(EVENT_CATEGORY_MAP.konser));
  assert.ok(Array.isArray(EVENT_CATEGORY_MAP.kultur_sanat));
  const summary = getEventSourceSummary();
  assert.equal(summary.total, SMART_EVENT_SOURCES.length);
  assert.ok(summary.byType.rss >= 1);
  assert.ok(summary.byType.html >= 1);
});

test('normalizeEvent recognizes expanded event categories and source logos', () => {
  const workshop = normalizeEvent({ title: 'Çocuk Atölyesi', category: 'atölye', city: 'Ankara' }, { name: 'Etkinlik.io Atölye' });
  assert.equal(workshop.category, 'Atölye');
  assert.ok(workshop.sourceLogo.includes('/assets/events/sources/'));
  const talk = normalizeEvent({ title: 'Yazar Söyleşisi', category: 'söyleşi', city: 'İstanbul' }, { name: 'İKSV Etkinlikler' });
  assert.equal(talk.category, 'Söyleşi');
  const fair = normalizeEvent({ title: 'Kitap Fuarı', category: 'fuar', city: 'İzmir' }, { name: 'Etkinlik.io Fuar' });
  assert.equal(fair.category, 'Fuar');
});
