# SmartNewspaper Feed Stabilization Report

## Kısa özet
Ana akışın boş kalma ihtimali üç ana noktadan geliyordu:

1. Frontend ilk açılışta `showPage("feed")` akışını veri yükleme tamamlanmadan çalıştırabiliyordu.
2. Auth/onboarding ekranı açıkken `init()` erken `return` yaptığı için feed arka planda yüklenmiyordu.
3. Backend bazı hata/boş veri yollarında gerçek feed yerine boş response döndürebiliyordu; ayrıca senkron çeviri istekleri feed response süresini gereksiz uzatabiliyordu.

Bu paketle `/api/feed` daha güvenli fallback davranışına alındı, frontend state yazımı normalize edildi, auth/onboarding arkasında feed ön yükleme eklendi ve haber kartları eksik alanlarda kırılmayacak hale getirildi.

## Değiştirilen dosyalar
- `server.js`
- `js/app.js`
- `dist/app.min.js`
- `dist/app.min.js.map`

## Eklenen dosyalar
- `FEED_STABILIZATION_REPORT.md`

## Backend düzeltmeleri
- `/api/feed` artık local/cache veriyi hızlı döndürür; local veri yoksa demo fallback üretir.
- DB okunamazsa boş/bozuk JSON yerine demo fallback haberleri döndürür.
- `buildFeedPayload()` içine `source` ve `message` alanları eklendi.
- Global region default davranışı ana akışı gizlemeyecek şekilde düzeltildi.
- Dedupe/cluster sonucu yanlışlıkla 0 haber üretirse raw haberlerden güvenli fallback kullanılır.
- `/api/health` içine prompttaki `feed` debug objesi eklendi: `cached_articles`, `db_articles`, `last_refresh_at`, `cache_age_seconds`, `rss_sources_count`.
- Feed response artık dış çeviri servislerini beklemiyor; senkron çeviri default kapalı, localize fallback metni kullanılıyor. Canlı çeviri işi response’u kilitlemez.

## Frontend düzeltmeleri
- `initAppData()` artık önce loading state gösterir, sonra `loadBackendData()` await eder, daha sonra `showPage("feed")` ve `renderArticles()` çalışır.
- `init()` içinde auth/register veya onboarding açık olsa bile `preloadFeedBehindAuth()` ile feed arka planda yüklenir.
- `loadBackendData()` artık `feed.articles`, `feed.data.articles`, `feed.data` ve `feed.items` formatlarını güvenli okur.
- API boş/hatalı dönerse `window.newspaperMockData` üzerinden fallback haberler state’e yazılır.
- Haber normalize işlemi `title`, `summary`, `source`, `image`, `publishedAt`, `source_count`, `clusterId` gibi eksik alanlarda güvenli fallback kullanır.
- Loading, empty ve error state’leri görünür hale getirildi; sonsuz loading/boş beyaz ekran engellendi.

## Dedupe / kaynak gruplama kontrolü
- `buildClusteredFeedPayload()` içinde dedupe çıktısı 0 olursa işlem durdurulup raw haberler güvenli cluster shape ile gösterilir.
- `sources`, `sourceCount`, `clusterId`, `mainArticleId` alanları korunur.

## Kategori dropdown uyumu
- Mevcut `js/utils/categoryFilter.js` korunmuştur.
- Politika → Siyaset, Magazin → Eğlence eşleşmeleri bozulmadı.
- Gündem özel filtre davranışı korunur; metrik yoksa haberleri boşaltmaz.

## Test sonuçları
```txt
npm test
# tests 158
# pass 158
# fail 0
```

```txt
npm run build
Fallback build tamamlandı.
```

Not: Ortamda `esbuild` çalıştırılamadığı için mevcut `build.js` güvenli fallback build üretmiştir. Build komutu hata ile bitmedi.

## Manuel API kontrolü
Local test komutu:

```bash
PORT=3131 LOG_LEVEL=error FEED_SYNC_TRANSLATIONS=0 node server.js
curl http://localhost:3131/api/feed?lang=tr\&region=global
curl http://localhost:3131/api/health
```

Örnek `/api/feed` özeti:

```json
{
  "success": true,
  "count": 12,
  "source": "cache",
  "message": "Haberler başarıyla yüklendi.",
  "articles": 12
}
```

Örnek `/api/health` feed özeti:

```json
{
  "status": "ok",
  "feed": {
    "cached_articles": 12,
    "db_articles": 3,
    "last_refresh_at": null,
    "cache_age_seconds": 4,
    "rss_sources_count": 108
  }
}
```

## Çalıştırma komutları
```bash
npm install
npm test
npm run build
npm start
```

## Son kontrol
- Ana akış ilk açılışta haber gösterecek şekilde düzenlendi.
- Filtre yokken haberler global default yüzünden gizlenmiyor.
- Auth/onboarding açıkken feed arka planda yükleniyor.
- Refresh hata verirse mevcut/fallback haberler ekranda kalıyor.
- Kaynak ikonları, cluster kaynakları, e-gazete/PDF akışı kaldırılmadı.
- Mobil görünüm dosyalarına kırıcı değişiklik yapılmadı.
