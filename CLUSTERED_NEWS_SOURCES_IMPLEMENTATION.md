# SmartNewspaper — Clustered Sources / Tek Haber Kartı Sistemi

Bu paket, aynı olayın farklı haber kaynaklarında yayınlanan versiyonlarını tek kart altında toplamak için backend + frontend entegrasyonu içerir.

## Eklenen kaynak katalogları

- `js/data/newsProviderCatalog.js`
  - `NEWS_API_PROVIDERS`
  - `TURKEY_NEWS_SOURCES`
  - `SOURCE_META`
  - `DEFAULT_SOURCE_ICON`
- `server.js` içinde aynı kataloglar canlı RSS/API fetch sistemine entegre edildi.
- Logo bulunamazsa `/assets/sources/default-news.svg` fallback olarak kullanılır.

## Backend cluster mantığı

Yeni sistem haberleri şu sinyallerle cluster eder:

- Canonical URL eşleşmesi
- Türkçe karakterleri koruyan başlık normalize etme
- Başlık token benzerliği
- Ortak keyword / entity benzerliği
- Kategori benzerliği
- Yayın tarihi yakınlığı
- Kaynak güven skoru
- Görsel/özet kalitesi

Eşikler:

- `EXACT_DUPLICATE_THRESHOLD = 0.92`
- `SAME_STORY_THRESHOLD = 0.72`
- `POSSIBLE_RELATED_THRESHOLD = 0.55`

## Yeni/entegre endpointler

```http
GET /api/feed?clustered=true
GET /api/articles/clusters/:clusterId
GET /api/articles/:articleId
```

`GET /api/feed?clustered=true` response alanları:

```json
{
  "success": true,
  "mode": "clustered",
  "totalClusters": 80,
  "totalArticles": 240,
  "articles": []
}
```

Her cluster kartında:

- `clusterId`
- `mainArticle`
- `sources`
- `sourceCount`
- `allTitles`
- `lastUpdatedAt`

bulunur.

## Frontend kullanıcı deneyimi

Ana haber kartında:

- “Bu haberi X kaynak yazdı” bilgisi gösterilir.
- İlk 5 kaynak ikon olarak görünür.
- Fazla kaynak varsa `+N kaynak` butonu çıkar.
- Kaynak ikonuna basınca kart aynı haberin seçilen kaynak versiyonuna döner.
- Detay modalında kaynak sekmeleri ve “Kaynak Karşılaştırması” alanı görünür.
- Kullanıcı sistemden çıkmadan kaynaklar arasında geçiş yapabilir.

## Korunan sistemler

- Mevcut haber çekme sistemi
- RSS/API kaynakları
- Taze Haberleri Getir butonu
- E-Gazete modu
- PDF export
- Haber paylaşma sistemi
- Kategori filtreleri
- TR/EN dil desteği
- Lazy loading
- No-cache düzeni
- 23 saatlik otomatik yenileme
- 2 günlük eski haber temizleme

## Kabul testi

Mock veri:

- TRT Haber: “Merkez Bankası faiz kararını açıkladı”
- Sözcü: “TCMB faiz kararını duyurdu”
- NTV: “Piyasaların beklediği faiz kararı açıklandı”
- Habertürk: “Galatasaray yeni transferini açıkladı”

Beklenen:

- Ekonomi haberleri aynı cluster altında toplanır.
- Spor haberi ayrı cluster olur.
