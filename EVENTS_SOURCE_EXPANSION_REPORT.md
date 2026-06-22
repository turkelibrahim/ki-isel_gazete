# SmartNewspaper Etkinlik Kaynakları Genişletme Raporu

## Özet
Etkinlikler modülüne Etkinlik.io RSS omurgası, Etkinlik.io sanal şehir/tür kaynakları, Biletix, Biletinial, Passo, Kültür Yolu, AKM, İBB/Kültür İstanbul, Kadıköy Kültür Sanat, İKSV ve Biletix Blog kaynakları eklendi. Mevcut etkinlik, takvim, hatırlatıcı, kaynak ikonları ve dedupe altyapısı korunarak genişletildi.

## Değiştirilen dosyalar
- `server/events/eventSources.js`
- `server/events/eventAggregator.js`
- `server/events/normalizeEvent.js`
- `server.js`
- `index.html`
- `js/app.js`
- `js/tests/event-aggregator.test.mjs`
- `dist/app.min.js`
- `dist/style.min.css`

## Eklenen dosyalar
- `server/events/sources/curatedEventSourcesAdapter.js`
- `EVENTS_SOURCE_EXPANSION_REPORT.md`

## Backend
- `SMART_EVENT_SOURCES` birleşik katalog olarak eklendi.
- `EVENT_RSS_SOURCES`, `EVENT_IO_RSS_VIRTUAL_SOURCES`, `EVENT_HTML_SOURCES`, `EVENT_BLOG_SOURCES` ayrı ayrı tanımlandı.
- `EVENT_CATEGORY_MAP` eklendi.
- `GET /api/events/sources` endpoint'i eklendi.
- Etkinlik filtreleri yeni şehir/kategori/tarih seçenekleriyle genişletildi.
- Etkinlik dedupe/source grouping akışı korundu.
- Kaynak hataları tek kaynağın sistemi çökertmeyeceği şekilde mevcut `Promise.allSettled` yapısıyla korunuyor.

## Frontend
- Etkinlik şehir filtresine Muğla, Eskişehir ve Kocaeli eklendi.
- Kategori filtresine Atölye, Fuar, Söyleşi ve Kültür Sanat eklendi.
- Tarih filtresine Yarın eklendi.
- Görsel fallback güvenli hale getirildi.
- Kaynak chip fallback listesi yeni ana kaynaklarla güncellendi.

## Testler
- `npm test`: 162 test geçti.
- `npm run build`: Fallback build tamamlandı.

## Manuel API kontrolleri
- `GET /api/events/sources` sonucu: 52 etkinlik kaynağı.
- Kaynak tipleri: 18 RSS, 21 HTML, 8 HTML adapter, 1 HTML sitemap adapter, 3 API, 1 RSS/JSON/XML.
- `GET /api/events?city=TURKIYE&category=Tümü&date=Tümü&limit=5` sonucu: etkinlik listesi döndü, örnek kartta 37 kaynak gruplandı.

## Çalıştırma
```bash
npm install
npm test
npm run build
npm start
```
