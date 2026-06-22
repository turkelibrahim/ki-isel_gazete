# SmartNewspaper — Orta Ana Akış Stabilizasyon Raporu

## Kısa özet

Ana sayfadaki orta **“Öne Çıkan & Son Haberler”** alanı `HeroSlider` component’i ile render ediliyordu. Sol Trend Radarı ve sağ Kaynak Haberleri veri gösterebildiği halde orta alanın boş kalmasının temel nedeni, hero slider’ın ana feed render akışıyla güvenli şekilde senkronize edilmemesi ve boş veri durumunda counter’ın eski/sabit `01 / 05` metnini koruyabilmesiydi.

Bu düzeltmede `HeroSlider` artık backend feed response alanlarını (`image_url`, `source_name`, `published_at`, `news_id`, `source_count`) normalize ediyor, featured haber yoksa normal feed haberlerine düşüyor ve ana feed render edildiğinde yeniden besleniyor.

## Değiştirilen dosyalar

- `index.html`
- `js/app.js`
- `js/components/heroSlider.js`
- `css/style.css`
- `dist/app.min.js`
- `dist/app.min.js.map`
- `dist/style.min.css`
- `dist/components/heroSlider.js`

## Eklenen dosyalar

- `js/tests/hero-slider-main-feed.test.mjs`
- `MAIN_FEED_CENTER_STABILIZATION_REPORT.md`

## Frontend düzeltmeleri

### appState / ana feed seçimi

- Orta alan için `buildMainFeedArticles()` eklendi.
- `featuredArticles` boşsa normal haberlerden fallback yapılıyor.
- `headline_score`, `trend_score`, `importance_score`, `is_featured`, `breaking`, `urgent` yok diye haberler gizlenmiyor.
- `getMainFeedFallbackArticles()` ile `articles`, `trendArticles`, `sourceArticles`, `last24` ve demo fallback sırası güvenli hale getirildi.

### loadBackendData / render akışı

- Feed geldikten sonra `renderArticles()` içinde orta hero slider da senkronize ediliyor.
- `Taze Haberleri Getir` sonrası `startLiveNews()` mevcut akışı koruyarak orta alanı yeniden dolduruyor.
- Auth/onboarding arkasında ön yüklenen haberler slider’a da düşebilecek şekilde güvenli hale getirildi.

### buildMainFeedArticles

- Önce gerçek featured/trend/önemli haberleri seçiyor.
- Bu liste boşsa normal haberleri kullanıyor.
- En azından eldeki güncel haberlerin orta alanda görünmesini garanti ediyor.

### renderMainFeed / HeroSlider

- `HeroSlider` artık `normalizeHeroArticle()` ile farklı backend field adlarını tek UI modeline çeviriyor.
- `selectHeroArticles()` normal haberleri de seçebiliyor; sadece explicit featured beklemiyor.
- Slider boşsa counter `00 / 00` oluyor, oklar disabled oluyor, dots temizleniyor.
- HTML default counter `01 / 05` yerine `00 / 00` yapıldı; böylece sahte pagination görünmüyor.

### Card normalize

Aşağıdaki alanlar güvenli şekilde normalize ediliyor:

- `id / news_id / articleId`
- `title / headline / displayTitle`
- `summary / description / content / fullText`
- `source / sourceName / source_name`
- `imageUrl / image_url / image / urlToImage`
- `publishedAt / published_at / pubDate`
- `sourceCount / source_count`
- `sources`

### Empty / loading / error state

- Slider boş kalırsa artık boş beyaz kutu yerine açıklayıcı empty state gösteriliyor.
- Counter eski `01 / 05` değerini korumuyor.
- CSS ile stage/card görünürlüğü garanti altına alındı.

## Backend kontrolü

`GET /api/feed` manuel olarak kontrol edildi.

Örnek kontrol çıktısı:

```json
{
  "success": true,
  "count": 12,
  "source": "cache",
  "articles": 12,
  "first": "NHK World kaynağından Sağlık haberi"
}
```

Backend feed kararlı JSON döndürüyor ve orta alan sorunu frontend render/senkronizasyon katmanında düzeltilmiştir.

## Dedupe ve kaynak ikonları kontrolü

- `clusterId`, `sources`, `sourceCount`, `sourceName/source` alanları korunuyor.
- `HeroSlider` içinde `_similarSources` mantığı korunarak çok kaynaklı haber bilgisi bozulmadı.
- Ana kart, trend, kaynak paneli, e-gazete ve PDF akışlarına müdahale edilmedi.

## Test sonuçları

```txt
npm test
# tests 164
# pass 164
# fail 0
```

Yeni eklenen testler:

- Backend feed field adları hero slider modeline normalize ediliyor.
- Featured flag yoksa normal haberler orta alana seçiliyor.

## Build sonucu

```txt
npm run build
Fallback build tamamlandı.
```

Not: Bu ortamda `esbuild` native çalıştırılamadığı için projenin mevcut `build.js` güvenli fallback build üretti. Komut hata vermedi.

## Çalıştırma komutları

```bash
npm install
npm test
npm run build
npm start
```

## Son kontrol

- Ana akışta orta haber kartları görünür hale getirildi.
- `01 / 05` gibi sahte pagination/counter boş veri durumunda kalmıyor.
- Sol Trend Radarı ve sağ Kaynak Haberleri bozulmadı.
- Taze Haberleri Getir sonrası orta alan yeniden besleniyor.
- Kaynak/dedupe alanları korunuyor.
- Mobil görünüm için stage min-height güvenliği eklendi.
