# SmartNewspaper Çok Dil Destekli NLP Pipeline Entegrasyonu

Bu paket, yüklenen master prompttaki çok dil destekli haber işleme, preprocessing, TR/EN alan üretimi ve e-gazete formatlama hedeflerini mevcut SmartNewspaper yapısını bozmadan entegre eder.

## Eklenen Ana Özellikler

- Dil algılama: Türkçe, İngilizce ve generic fallback.
- Türkçe karakterleri koruyan tokenizer / normalization.
- Orijinal haber alanlarını koruma.
- `title_tr`, `title_en`, `content_tr`, `content_en`, `original_lang`, `detected_lang` alanları.
- Keyword/entity çıkarımı.
- URL canonicalization.
- Dedupe key ve cluster id üretimi.
- E-Gazete/PDF için `newspaper_title`, `newspaper_summary`, `newspaper_excerpt`, `importance_score` alanları.
- spaCy/langdetect/langid yoksa sistemin çökmesini engelleyen fallback.

## Node Entegrasyonu

Yeni dosyalar:

- `services/newsProcessingService.js`
- `routes/nlp.js`
- `js/tests/nlp-processing.test.mjs`

Yeni endpointler:

```bash
GET  /api/nlp/health
POST /api/nlp/process
POST /api/nlp/process-batch
```

`/api/feed` response üretiminde her haber `NewsProcessingService.enrichFeedArticle(...)` ile zenginleştirilir. Mevcut feed, clustered feed, e-gazete ve kaynak ikonları korunur.

## Python Worker Dosyaları

- `backend/nlp/models.py`
- `backend/nlp/language_processor.py`
- `backend/nlp/translation_service.py`
- `backend/nlp/dedupe_service.py`
- `backend/nlp/newspaper_formatter.py`
- `backend/nlp/pipelines/turkish.py`
- `backend/nlp/pipelines/english.py`
- `backend/nlp/pipelines/generic.py`
- `backend/nlp/app.py`
- `backend/nlp/tests/*`

## Fallback Politikası

- spaCy modeli yoksa generic pipeline çalışır.
- Çeviri provider yoksa `translation_status="skipped"` olur.
- Haber kaynağı bozuksa ham haber korunur.
- Boş veya kısa metinlerde dil `unknown`, pipeline `generic` olur.

## Test Sonuçları

- `npm test` → 79/79 passed
- `python -m compileall -q backend` → başarılı
- `npm run build` → başarılı
- `node --check server.js services/newsProcessingService.js routes/nlp.js` → başarılı
