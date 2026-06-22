# SmartNewspaper RSS Source Expansion Report

## Amaç

Proje sahibinin sağladığı 40 Türkçe + 10 yabancı RSS kaynağı SmartNewspaper feed sistemine mevcut akışı bozmadan eklendi.

## Eklenen Kaynak Paketi

`server.js` içine `SMARTNEWSPAPER_CURATED_RSS_SOURCES` kataloğu eklendi.

Kapsam:

- 40 Türkçe RSS feed
  - TRT Haber
  - Sözcü
  - Ensonhaber
  - Habertürk
- 10 yabancı RSS feed
  - BBC News
  - The Guardian
  - Reuters
  - Al Jazeera English
  - AP News

## Backend Uyum Düzeltmeleri

`getUnifiedRssSourceCatalog()` artık şu alanları destekliyor:

- `url`
- `lang`
- `country`
- `rssUrl`
- `directRss`
- `fallbackRss`

Böylece yeni kaynak listesi doğrudan eski backend kaynak modeliyle uyumlu hale geldi.

## Kategori Normalizasyonu

Yeni RSS kategorileri frontend/backend kategori sistemine map edildi:

- `son_dakika` → `Gündem`
- `gundem` → `Gündem`
- `turkiye` → `Gündem`
- `dunya` → `Dünya`
- `ekonomi` → `Ekonomi`
- `spor` → `Spor`
- `yasam` → `Yaşam`
- `saglik` → `Sağlık`
- `kultur_sanat` → `Kültür/Sanat`
- `teknoloji` → `Teknoloji`
- `magazin` → `Eğlence`
- `manset` → `Gündem`
- `siyaset` / `politika` → `Siyaset`
- `world` → `Dünya`
- `business` → `Ekonomi`
- `technology` → `Teknoloji`
- `science` → `Bilim`
- `general` → `Gündem`

## Country / Language Normalizasyonu

Yeni kaynakların `country: "TR"`, `country: "GB"`, `country: "US"`, `country: "QA"` formatı korunarak backend alanlarına çevrildi:

- `countryCode`
- `country`
- `language`
- `region`

Türkiye kaynakları otomatik `region: turkey`, yabancı kaynaklar otomatik `region: global` olarak işaretlenir.

## Duplicate Feed Koruması

Aynı RSS feed’in `http` ve `https` varyasyonu iki kez fetch edilmesin diye katalog anahtarı normalize edildi:

- `http://...` ve `https://...` aynı feed kabul edilir.
- Sondaki `/` karakteri duplicate karşılaştırmasında yok sayılır.
- Duplicate kontrolü kategori bazlı korunur.

## API Kontrolü

Manuel kontrol:

```bash
GET /api/news/sources
```

Sonuç:

```json
{
  "sourceCount": 139,
  "normalizedDuplicateCount": 0,
  "hasCuratedSources": true
}
```

Örnek doğrulanan kaynaklar:

- TRT Haber Son Dakika
- Sözcü Magazin
- Habertürk Teknoloji
- BBC World
- AP News

## Test Sonucu

```bash
npm test
```

```txt
# tests 160
# pass 160
# fail 0
```

## Build Sonucu

```bash
npm run build
```

```txt
Fallback build tamamlandı.
```

Not: Ortamda `esbuild` native çalışmadığı için mevcut `build.js` güvenli fallback build üretti.

## Değiştirilen Dosyalar

- `server.js`
- `dist/app.min.js`
- `dist/style.min.css`

## Eklenen Dosyalar

- `RSS_SOURCE_EXPANSION_REPORT.md`

## Son Kontrol

- Yeni 50 RSS kaynak paketi backend kataloguna eklendi.
- `/api/news/sources` yeni kaynakları listeliyor.
- Kategori eşleşmeleri ana akışı bozmayacak şekilde normalize edildi.
- Dil/ülke alanları TR/EN haber akışıyla uyumlu hale getirildi.
- Duplicate feed fetch riski azaltıldı.
- Ana akış, önerilenler, dedupe, kaynak ikonları, e-gazete ve PDF sistemlerine dokunulmadı.
