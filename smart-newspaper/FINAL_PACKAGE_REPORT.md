# Modül 1 — Data Collection Genel Akış

Bu bölüm, haber toplama katmanının sistem içinde uçtan uca nasıl çalışacağını özetler.

## Sistem nasıl çalışacak?

1. Sistem aktif haber kaynaklarını `sources` tablosundan okur.
2. Kaynak RSS ise `rss_service` çalışır.
3. Kaynak API ise `news_api_service` çalışır.
4. Kaynak HTML crawl istiyorsa `spider_manager` çalışır.
5. Gelen haber normalize edilir.
6. URL bazlı duplicate için PostgreSQL `ON CONFLICT DO NOTHING` uygulanır.
7. Dil tespiti yapılır.
8. Kaynak metadata bilgisi çıkarılır.
9. MinHash + LSH ile benzer haber kontrol edilir.
10. Haber `articles` tablosuna kaydedilir.
11. Duplicate ise `is_duplicate=True` olur.
12. Celery Beat bu işlemleri belirlenen aralıklarla otomatik tekrarlar.

## Kurulum Komutları — Modül 1 Toplu

```bash
pip install httpx beautifulsoup4 lxml
pip install feedparser langdetect python-dateutil
pip install celery[redis] redis
pip install arrow
pip install datasketch
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Kontrol Listesi

- [x] `POST /api/crawl/run` route import ve FastAPI wiring çalışıyor.
- [~] RSS kaynaklarından haber gelmesi canlı kaynak ve veritabanı bağlantısı gerektirir; `RSSService` aktif kaynakları okuyup normalize edecek şekilde hazır.
- [x] NewsAPI rate limit `NEWSAPI_RATE_LIMIT_SECONDS=36` ile istekten önce bekliyor.
- [x] Celery worker ve beat task import/schedule wiring hazır.
- [x] Dil tespiti `language` alanını `save_article()` içinde dolduruyor.
- [x] Citation endpoint kaynak bilgisini döndürecek şekilde eklendi: `GET /api/articles/{article_id}/citation`.
- [x] Aynı URL iki kez kaydedilmesin diye PostgreSQL `ON CONFLICT DO NOTHING` kullanılıyor.
- [x] Farklı URL ama aynı içerik MinHash + LSH + Jaccard ile duplicate yakalanıyor.
- [x] `main.py` sadece FastAPI app oluşturma ve router import/include wiring için kullanılıyor.
- [x] `database.py` değiştirilmedi.

## Sonraki Parça

Sıradaki geliştirme paketi: **Parça 2 — News Classification**.


---

# Modül 2 — News Classification

Bu paketle Prompt 07 kapsamındaki NB + SVM + Ensemble classification katmanı eklendi.

## Genel Akış

1. Haber `articles` tablosuna kaydedilir.
2. `ClassificationService` haberi alır.
3. Naive Bayes ve SVM modelleri TF-IDF metin özellikleriyle çalışır.
4. SVM güveni `>= 0.85` ise sonuç doğrudan kabul edilir.
5. SVM güveni düşükse NB ile çapraz kontrol yapılır.
6. Modeller aynı kategori diyorsa ensemble sonucu kabul edilir.
7. Modeller farklı kategori diyorsa haber `moderation_queue` içine gönderilir.
8. Admin/human label ileride `is_human_label=True` ile kaydedilebilir.
9. 50+ insan etiketi birikince `POST /api/classification/train` gerçek etiketlerle yeniden eğitim yapar.
10. Modeller `models/nb.pkl` ve `models/svm.pkl` olarak saklanır.

## Endpointler

- `POST /api/classification/train`
- `POST /api/classification/articles/{article_id}/classify`
- `POST /api/classification/batch?limit=50`
- `GET /api/classification/models/status`

## Kurulum

```bash
pip install scikit-learn joblib
```

## Veritabanı

Yeni migration:

- `backend/migrations/20260621_add_classification_tables.sql`

Yeni tablolar:

- `categories`
- `article_categories`
- `moderation_queue`

---

# Smart Newspaper — Final Unified Package Report

Bu paket, önceki patch ZIP karmaşası yerine tek kök klasörlü final proje paketidir.

## Dahil edilen güncellemeler

- P01 Automated Web Crawling
  - `BaseSpider` Template Method Pattern
  - robots.txt kontrolü
  - User-Agent rotasyonu
  - rastgele rate limit
  - async HTTP request yönetimi
  - PostgreSQL URL duplicate önleyici upsert
  - `POST /api/crawl/run` ve `GET /api/crawl/status`

- P03 Celery Beat Scheduled Data Fetching
  - Celery + Redis + Celery Beat yapılandırması
  - 5 dakikada bir breaking news task
  - saat başı RSS fetch task
  - her sabah 06:00 Europe/Istanbul full crawl task
  - `max_retries=3`, `default_retry_delay=60`

- P04 Multi-Language Support
  - `langdetect` tabanlı dil tespiti
  - `DetectorFactory.seed = 42`
  - 500 karakterlik analiz sınırı
  - kısa metinlerde güvenli `unknown` fallback
  - kullanıcı `language_preference` filtre servisi

- P05 Source Tracking & Citation
  - Open Graph / Twitter / Dublin Core metadata extractor
  - yayıncı, tarih, yazar ve trust badge çıkarımı
  - `GET /api/articles/{article_id}/citation`

- P07 NB + SVM + Ensemble Classification
  - TF-IDF + MultinomialNB baseline classifier
  - TF-IDF + calibrated LinearSVC classifier
  - SVM confidence `>= 0.85` direct accept policy
  - NB/SVM disagreement moderation queue
  - `POST /api/classification/train`, classify, batch and status endpoints

- P06 Duplicate Detection / MinHash + LSH
  - `datasketch.MinHash(num_perm=128)` imza üretimi
  - `MinHashLSH(threshold=0.8)` aday bulma
  - final Jaccard doğrulama `>= 0.8`
  - duplicate haberleri silmeden `is_duplicate=True` işaretleme
  - non-duplicate haberleri LSH index'e ekleme
  - FastAPI startup index warm-up
  - günlük Celery dedup rebuild task

## Temizlik

- Eski iki kopyalı ZIP yapısı tek klasöre indirildi: `smart-newspaper/`
- Patch/script/test-output/log/screenshot kalıntıları temizlendi.
- Gerçek `.env` dosyası güvenlik için paketten çıkarıldı.
- `.env.example` içinde Redis/Celery değişkenleri eklendi.

## Doğrulama

Çalıştırılan kontroller:

- `npm test` → 70/70 passed
- `npm run build` → passed
  - Bu ortamda `esbuild` kurulu olmadığı için `build.js` güvenli fallback build üretir.
  - `npm install` sonrası aynı komut gerçek esbuild minify yapar.
- `python -m compileall -q backend` → passed
- FastAPI route smoke check → passed
- MetadataExtractor smoke check → passed
- DuplicateDetector MinHash/LSH smoke check → passed
- Celery dedup task import check → passed
- Node server health check → passed

## Çalıştırma

Node web server:

```bash
npm install
npm start
```

Python backend:

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Celery Worker:

```bash
celery -A backend.celery_app worker --loglevel=info
```

Celery Beat:

```bash
celery -A backend.celery_app beat --loglevel=info
```

Redis lokal örnek:

```bash
redis-server
```


## P08/P09 Güncellemesi

- P08 Multi-Label Classification eklendi.
- Binary Relevance + 5 zincirli ClassifierChain desteği eklendi.
- `threshold=0.40` üstündeki tüm kategoriler `article_categories` tablosuna ayrı satır olarak yazılır.
- P09 TF-IDF + RAKE + YAKE ensemble keyword extraction eklendi.
- `article_keywords` tablosu ve keyword API endpointleri eklendi.
- UI/CSS/HTML tarafına dokunulmadı.


## P10/P11 — Zero-Shot NLI + Active Learning

- Zero-shot NLI sınıflandırıcı eklendi: `backend/app/ml/zero_shot_classifier.py`.
- `facebook/bart-large-mnli` modeli lazy singleton olarak yüklenir.
- `POST /api/ai/add-label` ve `GET /api/ai/labels` endpointleri eklendi.
- Ensemble model eksik veya düşük güvenliyse zero-shot fallback devreye girer.
- `confidence < 0.65` sonuçlar active learning için `moderation_queue` içine düşer.
- Admin manuel düzeltmeleri `is_human_label=True`, `confidence=1.0` olarak kaydedilir.
- Manuel değişiklikler `audit_log` tablosuna yazılır.
- 50+ insan etiketi birikince timestamp dosyalarıyla retrain yapılabilir.
- `database.py` dosyasına dokunulmadı.

---

<!-- MODULE_2_FINAL_CHECKLIST -->

# Modül 2 — Toplu Kurulum ve Kontrol Listesi

Bu doküman, **MODÜL 2 — News Classification** kapsamındaki P07, P08, P09, P10 ve P11 parçalarının tek yerden kurulması ve doğrulanması için hazırlandı.

## Modül 2 Toplu Kurulum

```bash
pip install scikit-learn joblib
pip install rake-nltk yake nltk
pip install transformers torch
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Modül 2 Genel Akış

1. Haber `articles` tablosuna kaydedilir.
2. `ClassificationService` haberi alır.
3. Önce klasik ML modeli çalışır:
   - Naive Bayes
   - SVM
   - Ensemble karar mekanizması
4. Haber birden fazla kategoriye uyuyorsa Multi-Label classifier çalışır.
5. Anahtar kelimeler TF-IDF + RAKE + YAKE ile çıkarılır.
6. Eğitim verisi yetmediği durumlarda Zero-Shot NLI fallback kullanılır.
7. Düşük güvenli tahminler `moderation_queue` içine atılır.
8. Admin doğru kategoriyi seçerse `is_human_label=True` olarak kaydedilir.
9. 50+ insan etiketi birikince model yeniden eğitilir.
10. Yeni model timestamp ile kaydedilir, eski model rollback için tutulur.

## Modül 2 Kontrol Listesi

- [x] NB modeli eğitiliyor ve `models/nb.pkl` oluşuyor.
- [x] SVM modeli eğitiliyor ve `models/svm.pkl` oluşuyor.
- [x] SVM confidence `>= 0.85` ise otomatik kabul var.
- [x] NB ve SVM farklıysa `moderation_queue` kaydı oluşacak servis akışı var.
- [x] Multi-label classification birden fazla kategori yazabiliyor.
- [x] Keyword extraction en fazla 15 keyword çıkarıyor.
- [x] `article_keywords` tablosuna `keyword + score` kaydediliyor.
- [x] Zero-shot model singleton/lazy-load olarak yalnızca ilk tahminde yükleniyor.
- [x] GPU varsa `device=0`, yoksa CPU fallback `device=-1` çalışacak şekilde ayarlandı.
- [x] `confidence < 0.65` kayıtlar admin kuyruğuna düşüyor.
- [x] Admin düzeltmesi `is_human_label=True` yapıyor.
- [x] 50+ insan etiketi olmadan retrain başlamıyor.
- [x] Yeni model timestamp ile kaydediliyor.
- [x] `database.py` değiştirilmedi.
- [x] `main.py` sadece router import/include için değişti.

## Endpoint Özeti

### P07 — NB + SVM + Ensemble

```bash
POST /api/classification/train
POST /api/classification/articles/{article_id}/classify
POST /api/classification/batch?limit=50
GET  /api/classification/models/status
```

### P08 — Multi-Label Classification

```bash
POST /api/multilabel/train
POST /api/multilabel/articles/{article_id}/classify
POST /api/multilabel/batch
GET  /api/multilabel/status
```

### P09 — Keyword Extraction

```bash
POST /api/articles/{article_id}/keywords
POST /api/keywords/batch
GET  /api/articles/{article_id}/keywords
```

### P10 — Zero-Shot NLI

```bash
GET  /api/ai/labels
POST /api/ai/add-label
```

### P11 — Active Learning / Moderation

```bash
GET  /api/moderation/pending?admin_user_id=<ADMIN_ID>
POST /api/moderation/{id}/approve
POST /api/moderation/{id}/reclassify
POST /api/moderation/{id}/reviewed
POST /api/moderation/retrain
GET  /api/moderation/stats?admin_user_id=<ADMIN_ID>
```

## Notlar

- `database.py` dosyasına dokunulmadı.
- UI/CSS/HTML dosyalarına dokunulmadı; ekran kayması oluşturacak tasarım değişikliği yapılmadı.
- Zero-shot modeli büyük olduğu için import sırasında yüklenmez; ilk gerçek tahminde yüklenir.
- Gerçek BART modeli ilk kullanımda internet/cache durumuna göre indirilebilir veya cache’den çalışır.


---

# Modül 3 — Personal Newspaper / P12 Hybrid Recommender

Bu güncelleme, kişisel haber akışı için hibrit öneri motorunu ekler.

## Genel Akış

1. Kullanıcının okuduğu haberler `user_events` tablosundan alınır.
2. Kullanıcının okuduğu haberlerden TF-IDF ortalama vektörü çıkarılır.
3. Content-Based öneri skoru hesaplanır.
4. Benzer kullanıcıların okuduğu haberlerden Collaborative Filtering skoru hesaplanır.
5. CB `%60` + CF `%40` hibrit skor üretilir.
6. Cold start kullanıcı için `user_interests` + popüler haber fallback uygulanır.
7. Kullanıcı filtreleriyle haber listesi daraltılır.
8. Duplicate haberler öneriden çıkarılır.
9. Kullanıcının `language_preference` değeri uygulanır.
10. Redis ile 5 dakikalık cache desteklenir.
11. `newspaper_editions` tablosu sonraki Modül 4 PDF akışı için hazırdır.

## Eklenen Dosyalar

- `backend/app/ml/recommenders/content_based.py`
- `backend/app/ml/recommenders/user_cf.py`
- `backend/app/ml/recommenders/hybrid_recommender.py`
- `backend/app/services/recommendation_service.py`
- `backend/app/routers/personal_feed.py`
- `backend/MODULE_3_PERSONAL_NEWSPAPER.md`
- `backend/migrations/20260621_add_personal_newspaper_tables.sql`

## Endpointler

```bash
GET  /api/personal/feed?user_id=<USER_ID>&limit=30
GET  /api/personal/feed/{user_id}?limit=30
POST /api/personal/rebuild-index?language=tr
GET  /api/personal/recommendation-debug?user_id=<USER_ID>
```

## Kurulum

```bash
pip install scikit-learn scipy numpy redis
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Kontrol Listesi

- [x] Okuma geçmişi olan kullanıcı için hibrit öneri dönmesi için servis/router hazır.
- [x] Okuma geçmişi olmayan kullanıcı için cold start fallback hazır.
- [x] Okunmuş haberler tekrar önerilmez.
- [x] Duplicate haberler önerilmez.
- [x] Dil tercihi uygulanır.
- [x] CB `%60`, CF `%40` ağırlığı korunur.
- [x] `database.py` değiştirilmedi.
- [x] `main.py` sadece router import/include için değişti.
- [x] UI/CSS/HTML dosyalarına dokunulmadı.

---

## MODÜL 3 / PROMPT 13 — Article Filtering

Eklenenler:
- Composite index SQL script’i: `backend/sql/performance_indexes.sql`
- Pydantic filter schema: `FilterParams`
- Dinamik SQL filter service
- Pagination response: `items`, `page`, `page_size`, `total`, `has_next`, `filters_applied`
- `GET /api/articles` filtre endpoint’i
- Duplicate haberleri varsayılan dışlama: `is_duplicate=False`

Doğrulama:
- `database.py` değiştirilmedi.
- `main.py` sadece router import/include için güncellendi.
- UI/CSS/HTML dosyalarına dokunulmadı.


## MODÜL 3 — P14 Layout Generation Güncellemesi

- Jinja2 tabanlı kişisel gazete HTML üretimi eklendi.
- CSS Grid gazete düzeni, print uyumluluğu, empty state, citation/source alanları ve etkinlik kutusu eklendi.
- Yeni endpoint: `POST /api/newspaper/preview-html`.
- `database.py` dosyasına dokunulmadı.
- UI/CSS/HTML frontend tarafına dokunulmadı; layout sadece backend template olarak eklendi.

## P15 — Headline Prioritization / Temporal Decay

- Kişisel gazete manşet sıralaması için `PrioritizationService` eklendi.
- Temporal decay formülü: `recency = exp(-0.05 * hours_old)`.
- Popülerlik `log10(1 + view_count)` ile normalize edilir.
- Final skor: `0.40 * relevance + 0.30 * recency + 0.20 * pop_norm + 0.10 * trust`.
- Kullanıcı profili yoksa relevance `0.5` fallback çalışır.
- `source.trust_score` yoksa trust `0.5` fallback çalışır.
- Yeni endpointler: `POST /api/newspaper/rank-headlines`, `GET /api/articles/top-headlines`.
- `POST /api/newspaper/preview-html` artık layout render öncesi haberleri priority score ile sıralar.
- `database.py` değiştirilmedi; `main.py` sadece router include için güncellendi.

## Modül 3 / P16 — Citation Service for Personal Newspaper

- `backend/app/services/citation_service.py` eklendi.
- `backend/app/routers/newspaper_citations.py` eklendi.
- Kişisel gazete layout içinde her haberin altında `citation_text` render edilir.
- Trust badge: güvenilir / orta / düşük.
- `database.py` değiştirilmedi; `main.py` sadece router include için güncellendi.
## P17 — Personal Newspaper Edition Pipeline

- `EditionPipelineService` eklendi.
- Kişisel feed + filtre + manşet sıralama + citation + Jinja2 HTML üretimi tek akışa bağlandı.
- `newspaper_editions` tablosuna `html_content` kaydı yapılır.
- Aynı kullanıcı aynı gün tekrar üretirse günlük edisyon güncellenir.
- Celery Beat ile her sabah 07:00'de `generate_daily_editions` task'ı planlandı.
- PDF üretimi yapılmaz; HTML Modül 4 PDF export için hazır tutulur.

Endpointler:

```bash
POST   /api/newspaper/editions/generate
GET    /api/newspaper/editions/me
GET    /api/newspaper/editions/{edition_id}
DELETE /api/newspaper/editions/{edition_id}
```
---

# Modül 3 — Personal Newspaper Toplu Kurulum ve Kontrol Listesi

## Modül 3 Toplu Kurulum

```bash
pip install scikit-learn scipy numpy redis
pip install jinja2 arrow
pip install celery[redis] redis
```

## Kontrol Listesi

- [x] Hybrid recommender CB `%60` + CF `%40` çalışıyor.
- [x] Okunmuş haberler öneriden çıkarılıyor.
- [x] Cold start `user_interests` + popüler haber fallback hazır.
- [x] Article filtering category/source/date/language destekliyor.
- [x] Pagination doğru çalışıyor.
- [x] Duplicate haberler filtreleniyor.
- [x] Jinja2 `daily.html` gazete layout üretiyor.
- [x] Manşet `articles[0]` olarak en yüksek priority skorlu haber seçiliyor.
- [x] Temporal decay eski haberleri aşağı çekiyor.
- [x] Citation bilgisi her haber altında görünüyor.
- [x] Edition pipeline `html_content` üretiyor.
- [x] `newspaper_editions` tablosuna kayıt atılıyor.
- [x] Celery daily edition task tanımlandı.
- [x] `database.py` değişmedi.
- [x] `main.py` sadece router include için değişti.

---

# Modül 4 — PDF Export

## Genel Akış

1. `newspaper_editions` tablosundan `html_content` alınır.
2. Kullanıcının seçtiği PDF template belirlenir: `A4`, `TABLOID`, `BOOKLET`.
3. `TemplateService` ilgili `@page` CSS ayarlarını üretir.
4. `print.css` ile gazete sütunları, manşet, sayfa kırılmaları ve baskı stilleri uygulanır.
5. `PdfService`, WeasyPrint ile HTML'i PDF bytes'a çevirir.
6. PDF dosyası `storage/pdf/editions/` klasörüne kaydedilir.
7. `newspaper_editions.pdf_path` alanı güncellenir.
8. Preview/download router endpointleri sonraki promptlarda eklenecektir.
9. Hatalar loglanır, kontrollü exception döner.
10. `database.py` değişmez; P18 kapsamında `main.py` de değişmez.

## P18 — PDF Export With WeasyPrint

Eklenenler:

- `backend/app/services/pdf_service.py`
- `backend/templates/newspaper/print.css`
- `backend/storage/pdf/editions/.gitkeep`
- `backend/MODULE_4_P18_PDF_EXPORT.md`

Kurulum:

```bash
apt-get install libpango-1.0-0 libpangoft2-1.0-0
pip install weasyprint
```

Notlar:

- `PdfService.generate_pdf_bytes()` WeasyPrint importunu lazy yapar.
- HTML boşsa 400 döner.
- WeasyPrint/native dependency hatasında uygulama import aşamasında çökmez.
- PDF kaydı `backend/storage/pdf/editions/` altına yapılır.
- DB'ye relative path yazılır: `storage/pdf/editions/...pdf`.



## Modül 4 / P19 — PDF Template System

- `TemplateService` ayrı servis olarak eklendi.
- A4, TABLOID ve BOOKLET PDF template desteği sağlandı.
- Template-specific `@page`, kolon sayısı ve font boyutu CSS'i dinamik üretilir.
- Geçersiz template değeri güvenli şekilde `A4` fallback kullanır.
- `PdfService` artık template CSS'i `TemplateService().get_template_css(template)` ile alır.
- `print.css` genel baskı stillerini taşır; template CSS bu dosyayı tamamlar.
- Router eklenmedi; `main.py` değişmedi.
- `database.py` değişmedi.


## Modül 4 / P21 — Print Router / Preview / Download

- `backend/app/routers/print_router.py` eklendi.
- `backend/app/services/preview_service.py` eklendi.
- `GET /api/print/templates` template listesini döndürür.
- `GET /api/print/preview/{edition_id}?template=A4` HTML preview döndürür; PDF üretmez.
- `POST /api/print/generate/{edition_id}?template=A4` PDF üretir ve `newspaper_editions.pdf_path` alanını günceller.
- `GET /api/print/download/{edition_id}?template=A4&mode=attachment` PDF'i `StreamingResponse` ile indirir.
- `mode=inline` tarayıcıda açma header'ı üretir.
- Geçici yetki kontrolü `user_id` query parametresiyle owner/admin kuralını uygular; auth bağlandığında TODO helper `current_user` ile değiştirilebilir.
- `database.py` değişmedi.
- `main.py` sadece `print_router` import/include için değişti.
---

<!-- MODULE_4_FINAL_CHECKLIST -->

# Modül 4 — Toplu Kurulum, Endpoint Özeti ve Kontrol Listesi

## Modül 4 Toplu Kurulum

### Linux / Ubuntu sistem paketleri

```bash
sudo apt-get update
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libffi-dev shared-mime-info
```

### Python paketleri

```bash
pip install weasyprint
pip install jinja2 arrow beautifulsoup4
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Modül 4 Endpoint Özeti

```bash
GET  /api/print/templates
GET  /api/print/preview/{edition_id}?template=A4
POST /api/print/generate/{edition_id}?template=A4
GET  /api/print/download/{edition_id}?template=A4&mode=attachment
GET  /api/print/download/{edition_id}?template=A4&mode=inline
```

## Modül 4 Kontrol Listesi

- [x] `backend/app/services/pdf_service.py` oluşturuldu.
- [x] `backend/app/services/template_service.py` oluşturuldu.
- [x] `backend/app/services/preview_service.py` oluşturuldu.
- [x] `backend/app/routers/print_router.py` oluşturuldu.
- [x] `backend/templates/newspaper/print.css` oluşturuldu.
- [x] A4 template çalışıyor.
- [x] TABLOID template çalışıyor.
- [x] BOOKLET template çalışıyor.
- [x] `@page` size/margin/page counter çalışıyor.
- [x] `column-count` ile gazete sütun düzeni uygulanıyor.
- [x] `column-span: all` ile manşet tam genişlik oluyor.
- [x] Preview endpoint `HTMLResponse` dönüyor.
- [x] Generate endpoint PDF dosyası üretiyor.
- [x] Download endpoint `StreamingResponse` kullanıyor.
- [x] `mode=attachment` indirme header’ı üretiyor.
- [x] `mode=inline` tarayıcıda gösterme header’ı üretiyor.
- [x] `newspaper_editions.pdf_path` güncelleniyor.
- [x] Boş `html_content` için `400` dönüyor.
- [x] Kayıt bulunamazsa `404` dönüyor.
- [x] Yetkisiz kullanıcı kendi olmayan PDF’i alamıyor.
- [x] `database.py` hiç değişmedi.
- [x] `main.py` sadece router include için değişti.
- [x] `python -m compileall -q backend` başarılı.
- [x] FastAPI route check başarılı.

## Notlar

- P18 ve P19 servis katmanı eklediği için `main.py` değiştirilmedi.
- P21 print router eklediği için `main.py` yalnızca `print_router` import/include aldı.
- `database.py` dosyasına dokunulmadı.
- Frontend UI/CSS/HTML tarafına dokunulmadı; ekran kayması oluşturacak değişiklik yok.
---
---

# Modül 5 — Events & Reminders / P22-P23

Bu paketle Modül 5'in ilk iki parçası eklendi:

- **P22 — Event Detection / NER + Regex**
- **P23 — Event Categorization / Keyword Score**

## Genel Akış

1. Haber veya duyuru metni sisteme gelir.
2. `EventDetector` metni cümlelere böler.
3. spaCy NER ile `DATE` entity aranır.
4. Regex ile tarih/saat formatları aranır.
5. `EVENT_KW` keyword listesiyle etkinlik kelimeleri aranır.
6. Hem tarih hem etkinlik keyword varsa event candidate oluşur.
7. `EventCategoryClassifier` keyword puan sistemiyle kategori belirler.
8. `EventDetector.detect_events()` çıktısı kategori bilgileriyle birlikte döner.

## Eklenen dosyalar

- `backend/app/ml/event_detector.py`
- `backend/app/ml/event_category_classifier.py`
- `backend/MODULE_5_EVENTS_AND_REMINDERS.md`

## P23 Kategori Mantığı

Desteklenen kategoriler:

- `EXAM`
- `DEADLINE`
- `ACADEMIC`
- `MEETING`
- `SOCIAL`
- `OTHER`

Eşitlik önceliği:

`EXAM > DEADLINE > ACADEMIC > MEETING > SOCIAL > OTHER`

## Kurulum

```bash
pip install spacy dateparser python-dateutil
python -m spacy download xx_ent_wiki_sm
```

## Kontroller

- Tarih + etkinlik keyword olan cümle event döndürür.
- Sadece tarih veya sadece keyword olan cümle event döndürmez.
- Confidence `0.65`, `0.85`, maksimum `0.95` mantığı uygulanır.
- `final sınavı 21 Haziran’da` metni `EXAM` kategorisi alır.
- `son başvuru tarihi yarın` metni `DEADLINE` kategorisi alır.
- `webinar ve seminer yapılacak` metni `ACADEMIC` kategorisi alır.
- Eşitlik durumunda sabit öncelik sırası uygulanır.
- `database.py` değişmedi.
- `main.py` değişmedi; P22/P23 router istemiyor.

## Modül 5 / P24 — Event Service + CRUD API

- `EventService` eklendi.
- `backend/app/schemas/events.py` Pydantic şemaları eklendi.
- `/api/events` router eklendi.
- Manuel etkinlik oluşturma, metinden etkinlik çıkarma, listeleme, upcoming listeleme, güncelleme ve soft delete desteklendi.
- `remind_at` varsayılan olarak `event_date - 24 saat`; 24 saatten yakın etkinliklerde `now()` fallback.
- Geçmiş etkinlikler kontrollü `400` ile reddedilir.
- Aynı `title + event_date` aktif event duplicate kayıt oluşturmaz.
- `events.is_notified` için güvenli migration dosyası eklendi.
- `database.py` değişmedi; `main.py` sadece events router import/include için güncellendi.

## Modül 5 / P25 — Push + Email Notification Services

- `backend/app/services/push_service.py` eklendi.
- `backend/app/services/email_service.py` eklendi.
- FCM push bildirimi için `FCM_SERVER_KEY` env desteği eklendi.
- SMTP HTML email için `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` env desteği eklendi.
- FCM token veya SMTP bilgileri eksikse sistem çökmeden ilgili kanal atlanır.
- Push ve email hata yönetimi birbirinden bağımsızdır; bir kanal hata verirse diğer kanal çalışmaya devam eder.
- `database.py` değişmedi.
- `main.py` değişmedi; P25 router istemiyor.

## Modül 5 / P26 — Reminder Polling + Newspaper Integration

- `backend/app/tasks/reminder_task.py` eklendi.
- Celery Beat schedule eklendi: `send-event-reminders-every-15-minutes` / `crontab(minute="*/15")`.
- `send_event_reminders` task `max_retries=3`, `default_retry_delay=60` ile çalışır.
- Reminder logic DB polling kullanır; memory tabanlı `setTimeout` kullanılmaz.
- Due eventler `remind_at <= now + 15 dakika`, `event_date >= now`, `is_notified=False`, `is_active=True` filtresiyle bulunur.
- Kullanıcıya özel eventler sahibine, global eventler MVP olarak tüm kullanıcılara gönderilir.
- Push ve email kanalları bağımsız çalışır; en az biri başarılıysa `is_notified=True` yapılır.
- `POST /api/events/reminders/run-now` manuel test endpoint’i eklendi.
- `EditionPipelineService`, `EventService().get_upcoming_events(db, days=7)` ile önümüzdeki 7 günün etkinliklerini kişisel gazete HTML’ine ekler.
- `daily.html` etkinlik kategori bilgisini de render eder.
- PDF export `html_content` üzerinden çalıştığı için etkinlikler PDF’e otomatik dahil olur.
- `database.py` değişmedi.
- `main.py` bu adımda değişmedi; events router P24’te zaten eklenmişti.
---

## Modül 5 Complete — Events & Reminders Kurulum / Endpoint / Kontrol Listesi

Modül 5 complete dokümantasyonu eklendi:

- `backend/MODULE_5_SETUP_AND_CHECKLIST.md`
- Toplu kurulum komutları
- `/api/events` endpoint özeti
- P22 / P23 / P24 / P25 / P26 kontrol listesi
- `database.py` değişmedi notu
- `main.py` sadece router include için değişti notu
- Celery reminder polling `*/15` dakika notu
- Gazete HTML ve PDF entegrasyon notu
---

# Modül 6 — Search / Bookmark / Trending

Bu paketle **Prompt 27 — Keyword Search / BM25 Search Engine** kapsamı eklendi.

## Genel Akış

1. Duplicate olmayan haberler BM25 index’e alınır.
2. Her haber için `title + summary + content[:500]` tokenize edilir.
3. Türkçe karakterleri koruyan tokenizer noktalama ve stop word temizliği yapar.
4. Kullanıcı `/api/search` ile arama yaparsa BM25 skorları hesaplanır.
5. SQL ile Article kayıtları çekilir ve BM25 rank sırası korunur.
6. Duplicate haberler arama sonucuna girmez.
7. `database.py` değişmez, `main.py` sadece router include için değişir.

## Endpointler

- `GET /api/search?q=merkez+bankası&top=20`
- `POST /api/search/rebuild-index`
- `GET /api/search/status`

## Kurulum

```bash
pip install rank-bm25
```

## Eklenen Dosyalar

- `backend/app/ml/search/bm25_engine.py`
- `backend/app/ml/search/__init__.py`
- `backend/app/services/search_service.py`
- `backend/app/routers/search.py`
- `backend/MODULE_6_SEARCH_DISCOVERY.md`


---

## Modül 6 / P28 — Advanced Filters / BM25 + SQL Hybrid Search

Bu paketle gelişmiş hibrit arama sistemi eklendi.

### Eklenenler

- `SearchFilterParams` Pydantic schema.
- `AdvancedSearchService`.
- `advanced_search` router.
- BM25 + SQL hibrit arama.
- Kategori/kaynak/tarih/dil/bookmark filtreleri.
- `sort_by=relevance`, `date`, `popularity`, `trend`.
- Pagination response.
- Manuel performans index script’i.

### Endpoint

- `GET /api/search/advanced`

### Eklenen Dosyalar

- `backend/app/schemas/search_filters.py`
- `backend/app/services/advanced_search_service.py`
- `backend/app/routers/advanced_search.py`
- `backend/sql/search_filter_indexes.sql`
- `backend/MODULE_6_P28_ADVANCED_SEARCH.md`

### Korunan Şartlar

- `database.py` değişmedi.
- `main.py` sadece advanced search router import/include için değişti.
- Frontend UI/CSS/HTML tarafına dokunulmadı.

---

## Modül 6 / P29 — Bookmark CRUD / Optimistic Upsert

Bu paketle bookmark CRUD sistemi eklendi.

### Eklenenler

- `BookmarkService`
- Bookmark Pydantic şemaları
- `/api/bookmarks` router
- `UserBookmark` modeli
- `UNIQUE(user_id, article_id)` migration script’i
- Optimistic INSERT + `IntegrityError` duplicate yakalama
- `BOOKMARKED` / `UNBOOKMARKED` user event entegrasyonu

### Endpointler

- `GET /api/bookmarks?user_id=<USER_ID>`
- `POST /api/bookmarks/{article_id}?user_id=<USER_ID>`
- `DELETE /api/bookmarks/{article_id}?user_id=<USER_ID>`
- `POST /api/bookmarks/{article_id}/toggle?user_id=<USER_ID>`
- `GET /api/bookmarks/{article_id}/status?user_id=<USER_ID>`

### Korunan Şartlar

- `database.py` değişmedi.
- `main.py` sadece bookmark router import/include için değişti.
- Frontend UI/CSS/HTML tarafına dokunulmadı.

---

## Modül 6 / P30 — Trending Detection

Eklenenler:

- `TrendingService`
- Temporal decay trend score: `view_count × e^(-0.05 × hours_since_published)`
- Varsayılan 72 saat pencere
- Duplicate haberleri dışlama
- Redis varsa 5 dakika trend cache
- Celery Beat `*/10 dakika` trend cache refresh
- `/api/trending` endpointleri
- Advanced Search `sort_by=trend` ortak servis entegrasyonu

Endpointler:

```bash
GET  /api/trending
GET  /api/trending/category/{category_id}
POST /api/trending/refresh-cache
```

Kontroller:

- `database.py` değişmedi.
- `main.py` sadece trending router import/include için değişti.
- Frontend UI/CSS/HTML tarafına dokunulmadı.

---

## Modül 6 — Search / Bookmark / Trending Complete

Bu paketle Modül 6 kurulum, endpoint özeti ve kontrol listesi tamamlandı.

### Genel Akış

1. Duplicate olmayan haberler BM25 index’e alınır.
2. `title + summary + content[:500]` metni Türkçe tokenizer ile tokenize edilir.
3. Kullanıcı arama yaparsa `BM25Engine` query skorlarını hesaplar.
4. Arama skoru yüksek ilk 200 `article_id` SQL filtreleriyle daraltılır.
5. Bookmark ekleme optimistic insert + `IntegrityError` yakalama ile yapılır.
6. `UNIQUE(user_id, article_id)` duplicate bookmark’ı engeller.
7. Trend haberlerde son 72 saatteki haberler değerlendirilir.
8. `trend_score = view_count × e^(-0.05 × hours_since_published)` ile sıralama yapılır.
9. Search, advanced filter, bookmark ve trending endpointleri sonuç döndürür.
10. `database.py` değişmez, `main.py` sadece router include için değişir.

### Toplu Kurulum

```bash
pip install rank-bm25
pip install redis celery[redis]
```

### Endpoint Özeti

```bash
GET  /api/search?q=merkez+bankası&top=20
POST /api/search/rebuild-index
GET  /api/search/status

GET  /api/search/advanced?q=...&category_ids=1&language=tr&sort_by=relevance
GET  /api/search/advanced?sort_by=trend&language=tr

GET    /api/bookmarks
POST   /api/bookmarks/{article_id}
DELETE /api/bookmarks/{article_id}
POST   /api/bookmarks/{article_id}/toggle
GET    /api/bookmarks/{article_id}/status

GET  /api/trending
GET  /api/trending/category/{category_id}
POST /api/trending/refresh-cache
```

### Kontrol Listesi

- `backend/app/ml/search/bm25_engine.py` oluşturuldu.
- `backend/app/services/search_service.py` oluşturuldu.
- `backend/app/services/advanced_search_service.py` oluşturuldu.
- `backend/app/services/bookmark_service.py` oluşturuldu.
- `backend/app/services/trending_service.py` oluşturuldu.
- `backend/app/routers/search.py` oluşturuldu.
- `backend/app/routers/advanced_search.py` oluşturuldu.
- `backend/app/routers/bookmarks.py` oluşturuldu.
- `backend/app/routers/trending.py` oluşturuldu.
- Türkçe tokenizer `çğıöşü` karakterlerini koruyor.
- BM25 `k1=1.5` ve `b=0.75` ile kuruluyor.
- Duplicate haberler BM25 index’e alınmıyor.
- Advanced search `q` varsa BM25 top 200 ID kullanıyor.
- Advanced search `q` yoksa SQL-only filtre kullanıyor.
- Category/source/date/language filtreleri destekleniyor.
- `only_bookmarked` filtresi `user_bookmarks` join ile çalışıyor.
- Bookmark optimistic insert + `IntegrityError` yakalama kullanıyor.
- Bookmark eklenince `user_events` içine `BOOKMARKED` yazılıyor.
- Trend formülü `view_count × e^(-0.05 × hours)` olarak uygulanıyor.
- Trend `window_hours=72` varsayılan.
- `is_duplicate=True` haberler trend listesine girmiyor.
- `sort_by=trend` advanced search ile uyumlu.
- Redis yoksa trend sistemi cache olmadan çalışıyor.
- Celery `refresh_trending_cache` `*/10 dakika` planlandı.
- `database.py` değişmedi.
- `main.py` sadece router include için değişti.

### Sonraki Parça

Sıradaki geliştirme paketi: **Modül 7 — Analytics & Recommendation**.


---

# Modül 7 — Analytics & Recommendation / P31

Bu paketle kullanıcı davranışlarını implicit feedback sinyaline çeviren TrackingService eklendi.

## Eklenenler

- `TrackingService`
- `TrackEventRequest`, `TrackEventResponse`, `UserRatingResponse`, `ArticleStatsResponse`
- `/api/tracking` router
- `VIEWED`, `READ`, `BOOKMARKED`, `SHARED`, `SKIPPED`, `UNBOOKMARKED` event ağırlıkları
- `effective_rating = weight × min(scroll_percent / 100, 1.0)` formülü
- Scroll fallback değerleri
- `duration_seconds >= 30` ile READ güçlendirmesi
- `duration_seconds < 5` + `scroll_percent < 10` ile SKIPPED yorumu
- Aynı user/article için MAX signal aggregation
- `VIEWED` ve `READ` eventlerinde `Article.view_count` artırma
- Recommendation cache invalidation hook
- Adaptive ranking lazy hook

## Endpointler

- `POST /api/tracking/event`
- `POST /api/tracking/view/{article_id}`
- `POST /api/tracking/read/{article_id}`
- `POST /api/tracking/skip/{article_id}`
- `GET /api/tracking/user/{user_id}/ratings`
- `GET /api/tracking/article/{article_id}/stats`

## Doğrulama Notları

- `database.py` değişmedi.
- `main.py` sadece tracking router import/include için değişti.
- Recommendation tarafındaki user-CF aggregation artık tekrar eden eventleri toplamak yerine en güçlü sinyali kullanır.


## MODÜL 7 / P32 — IBCF + SVD Recommendation System

Eklenenler:

- IBCF recommender: `KNNWithMeans(k=20, user_based=False, min_support=3)`
- SVD recommender: `n_factors=50`, `n_epochs=20`, `lr_all=0.005`, `reg_all=0.02`
- `TrackingService.get_user_ratings_matrix(db)` ile implicit rating datası
- `Reader(rating_scale=(0, 2.0))`
- `cross_validate` ile RMSE/MAE değerlendirme
- Model kayıtları: `backend/models/recommenders/ibcf.pkl`, `backend/models/recommenders/svd.pkl`
- Analytics hybrid formül: `0.30 CB + 0.35 IBCF + 0.25 SVD + 0.10 Trending`
- Haftalık Celery training task: Pazar 03:00
- Yeni endpointler: `/api/recommendations/train`, `/status`, `/user/{user_id}`, `/debug/{user_id}`

Notlar:

- `database.py` değiştirilmedi.
- `main.py` sadece recommendations router import/include için değişti.
- `scikit-surprise` yoksa backend import aşamasında çökmez; kontrollü fallback döner.


## MODÜL 7 / P34 — Engagement Analytics / SQL Aggregation

Eklenenler:

- `AnalyticsService`
- `/api/analytics` router
- DAU hesaplama
- Top articles engagement score
- Category reads
- User analytics
- Source performance
- Overview dashboard metriği
- Redis varsa 5 dakika cache, Redis yoksa cache olmadan çalışma

Endpointler:

```http
GET /api/analytics/overview
GET /api/analytics/dau?days=30
GET /api/analytics/top-articles?days=7&limit=20
GET /api/analytics/categories?days=30
GET /api/analytics/user/{user_id}?days=30
GET /api/analytics/sources?days=30
```

Engagement score:

```text
VIEWED * 0.3 + READ * 1.0 + BOOKMARKED * 1.5 + SHARED * 2.0
```

Notlar:

- `database.py` değiştirilmedi.
- `main.py` sadece analytics router import/include için değişti.
- Auth altyapısı bağlanana kadar analytics permission noktalarına TODO bırakıldı.

## MODÜL 7 / P35 — Adaptive Ranking / Online Learning

Eklenenler:

- `AdaptiveRankingService`
- `/api/adaptive-ranking` router
- Online learning formülü:
  - Pozitif: `w_new = w + ALPHA * (1.0 - w)`
  - Negatif: `w_new = w - ALPHA * w`
  - `ALPHA = 0.1`
  - Clamp: `0.0 <= weight <= 1.0`
- Pozitif eventler: `READ`, `BOOKMARKED`, `SHARED`
- Negatif eventler: `SKIPPED`, `UNBOOKMARKED`
- Birden fazla kategori varsa tüm kategoriler güncellenir.
- Category confidence varsa `effective_alpha = ALPHA * confidence` uygulanır.
- `TrackingService` adaptive hook ile bağlandı.
- Adaptive update hatası tracking işlemini bozmaz.
- Recommendation service adaptive interest skorunu kişisel feed sıralamasına dahil eder.

Endpointler:

```http
GET  /api/adaptive-ranking/interests/{user_id}
POST /api/adaptive-ranking/update
POST /api/adaptive-ranking/reset/{user_id}
POST /api/adaptive-ranking/rank-preview/{user_id}
```

Notlar:

- `database.py` değiştirilmedi.
- `main.py` sadece adaptive ranking router import/include için değişti.
- Migration yapılmadı.

## Modül 7 Complete Güncellemesi

- Modül 7 toplu kurulum, endpoint özeti ve kontrol listesi eklendi:
  - `backend/MODULE_7_SETUP_AND_CHECKLIST.md`
- Eksik kalan Topic Modeling katmanı tamamlandı:
  - `backend/app/ml/topic_model.py`
  - `backend/app/services/topic_service.py`
  - `backend/app/routers/topics.py`
  - `backend/app/tasks/topic_tasks.py`
- Topic endpointleri eklendi:
  - `POST /api/topics/train`
  - `GET /api/topics`
  - `GET /api/topics/trending`
  - `GET /api/topics/article/{article_id}`
  - `GET /api/topics/status`
- LDA ayarları PDF rehberine göre eklendi:
  - `num_topics=20`
  - `passes=15`
  - `alpha='auto'`
  - `eta='auto'`
  - `Dictionary.filter_extremes(no_below=5, no_above=0.5)`
  - `CoherenceModel(coherence='c_v')`
- Haftalık topic refresh Celery task eklendi:
  - `app.tasks.topic_tasks.refresh_topic_model`
  - `crontab(day_of_week="sun", hour=4, minute=0)`
- `database.py` değişmedi.
- `main.py` sadece `topics` router import/include için değişti.
- Sonraki son parça: **Modül 8 — Reporting & Administration**.

---

## Modül 8 P36 — Admin CRUD / Soft Delete / Audit Log

Eklenen dosyalar:

- `backend/app/services/admin_service.py`
- `backend/app/schemas/admin.py`
- `backend/app/routers/admin.py`
- `backend/MODULE_8_ADMINISTRATION.md`

Yeni endpointler:

```http
GET   /api/admin/users
PATCH /api/admin/users/{user_id}/role
GET   /api/admin/sources
POST  /api/admin/sources/{source_id}/activate
POST  /api/admin/sources/{source_id}/deactivate
PATCH /api/admin/sources/{source_id}/trust-score
GET   /api/admin/articles
POST  /api/admin/articles/{article_id}/mark-duplicate
POST  /api/admin/articles/{article_id}/safe-delete
GET   /api/admin/audit-log
```

P36 notları:

- Admin guard eklendi; gerçek JWT/RBAC Prompt 39 gelince `require_role("ADMIN")` ile değiştirilmeye hazır.
- Source hard delete yapılmaz, `is_active=False` kullanılır.
- Article hard delete yapılmaz, `is_duplicate=True` kullanılır.
- `trust_score` 0.0-1.0 aralığında doğrulanır.
- Kritik işlemler `audit_log` tablosuna yazılır.
- `database.py` değişmedi.
- `main.py` sadece admin router import/include için değişti.

---

## Modül 8 P37 — System Monitoring / Health Check / RotatingFileHandler

Eklenen dosyalar:

- `backend/app/services/monitoring_service.py`
- `backend/app/core/logging_config.py`
- `backend/app/routers/monitoring.py`
- `backend/logs/.gitkeep`
- `backend/MODULE_8_P37_MONITORING.md`

Yeni endpointler:

```http
GET /api/monitoring/health
GET /api/monitoring/metrics
GET /api/monitoring/logs/recent?lines=100
```

P37 notları:

- DB `SELECT 1` latency check eklendi.
- Redis env’den okunur; Redis yoksa sistem çökmez.
- CPU/RAM/Disk metrikleri `psutil` ile hesaplanır.
- Model dosya klasörleri kontrol edilir:
  - `backend/models/recommenders/`
  - `backend/models/topics/`
  - `models/`
- RotatingFileHandler eklendi:
  - `backend/logs/app.log`
  - 10MB
  - 5 backup
- `/health` public, `/metrics` ve `/logs/recent` ADMIN guard ile korumalıdır.
- `database.py` değişmedi.
- `main.py` sadece monitoring router include ve logging setup için değişti.

## Modül 8 / P38 — Reporting System / Matplotlib PDF + CSV Export

Eklenen/güncellenen dosyalar:

- `backend/app/services/report_service.py`
- `backend/app/routers/reports.py`
- `backend/storage/reports/.gitkeep`
- `backend/MODULE_8_P38_REPORTING.md`
- `backend/MODULE_8_ADMINISTRATION.md`
- `backend/requirements.txt`
- `backend/app/main.py`

Endpointler:

```http
POST   /api/reports/generate?days=30&format=pdf
POST   /api/reports/generate?days=30&format=csv
GET    /api/reports/download?path=...
GET    /api/reports/list
DELETE /api/reports/cleanup?days=30
```

Notlar:

- PDF üretimi `matplotlib.backends.backend_pdf.PdfPages` ile yapılır.
- CSV export `utf-8-sig` encoding ile Türkçe karakterleri korur.
- Download sadece `backend/storage/reports/` altına izin verir.
- `database.py` değişmedi.
- `main.py` sadece reports router import/include için değişti.

---

## Modül 8 P39 — JWT Authentication + RBAC Authorization

Eklenen/güncellenen dosyalar:

- `backend/app/core/security.py`
- `backend/app/dependencies/__init__.py`
- `backend/app/dependencies/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/schemas/auth.py`
- `backend/app/routers/auth.py`
- `backend/migrations/20260621_add_user_password_hash.sql`
- `backend/MODULE_8_P39_AUTH_RBAC.md`
- `backend/MODULE_8_ADMINISTRATION.md`
- `backend/app/models.py`
- `backend/app/routers/admin.py`
- `backend/app/routers/monitoring.py`
- `backend/app/routers/reports.py`
- `backend/requirements.txt`
- `.env.example`
- `backend/app/main.py`

Yeni endpointler:

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
```

P39 notları:

- `passlib[bcrypt]` ile password hashing eklendi.
- `python-jose` ile JWT access/refresh token yapısı eklendi.
- `SECRET_KEY` env üzerinden okunur; hardcode edilmez.
- Access token `30 dakika`, refresh token `7 gün` varsayılan sürelidir.
- Token payload içinde `sub`, `role`, `type`, `exp` vardır.
- Protected endpointlerde refresh token kabul edilmez.
- Refresh endpointinde access token kabul edilmez.
- RBAC matrix `ADMIN`, `EDITOR`, `USER` için tanımlandı.
- P36/P37/P38 geçici admin guard yapıları gerçek `require_role("ADMIN")` dependency ile değiştirildi.
- `database.py` değişmedi.
- `main.py` sadece auth router import/include için değişti.

---

## Modül 8 / P40 — Two-Layer Content Moderation

Bu paketle iki katmanlı içerik moderasyon sistemi eklendi.

Eklenen/güncellenen dosyalar:

- `backend/app/services/content_moderation_service.py`
- `backend/app/routers/content_moderation.py`
- `backend/migrations/20260621_add_content_moderation_fields.sql`
- `backend/app/models.py`
- `backend/app/main.py`
- `backend/MODULE_8_P40_CONTENT_MODERATION.md`
- `backend/MODULE_8_ADMINISTRATION.md`

Endpointler:

- `POST /api/moderation/check-text`
- `GET /api/moderation/queue`
- `POST /api/moderation/{moderation_id}/approve`
- `POST /api/moderation/{moderation_id}/reject`
- `GET /api/moderation/stats`

Doğrulama hedefleri:

- Blocked keyword içeren metin `REJECTED` döner.
- `score >= 0.95` için `REJECTED` kararı uygulanır.
- `0.70 <= score < 0.95` için `PENDING` kararı uygulanır.
- `score < 0.70` için `APPROVED` kararı uygulanır.
- ML model yoksa sistem keyword-only fallback ile çalışır.
- PENDING/REJECTED kayıtlar `moderation_queue` içine düşer.
- approve/reject `reviewed_by` ve `reviewed_at` doldurur.
- review işlemleri `audit_log` içine yazılır.
- `database.py` değişmemiştir.

---

## Modül 8 Complete — Reporting & Administration Kurulum / Endpoint / Kontrol Listesi

Bu paketle Modül 8 için toplu kurulum, endpoint özeti ve kontrol listesi eklendi.

Eklenen/güncellenen dosyalar:

- `backend/MODULE_8_SETUP_AND_CHECKLIST.md`
- `backend/MODULE_8_ADMINISTRATION.md`
- `FINAL_PACKAGE_REPORT.md`

Kapsam:

- Auth / RBAC endpoint özeti
- Admin CRUD endpoint özeti
- Monitoring endpoint özeti
- PDF/CSV report endpoint özeti
- Content moderation endpoint özeti
- P36 Admin CRUD checklist
- P37 Monitoring checklist
- P38 Reporting checklist
- P39 JWT/RBAC checklist
- P40 Content Moderation checklist
- `database.py` değişmedi doğrulaması
- `main.py` sadece router include ve P37 logging setup için değişti notu
- `python -m compileall -q backend`, FastAPI route check, `npm test`, `npm run build` doğrulama notları

## No-Cache Fix — Eski Build / Eski Haber Gösterme Sorunu

Kullanıcı geri bildirimi üzerine cache mantığı kaldırıldı/kapalı hale getirildi. Tarayıcı artık eski `dist/app.min.js`, eski CSS veya eski `news_cache_*` localStorage kayıtlarını kullanmaz.

- `server.js` static file cache kapalı.
- `ETag` / `304 Not Modified` kullanılmıyor.
- Static response header'ları `no-store, no-cache, max-age=0` döner.
- Frontend haber cache sistemi kapalı.
- Uygulama açılışında `news_cache_*` localStorage kayıtları temizlenir.
- GET API istekleri cache-buster ile gider.
- `TrendingService` ve `AnalyticsService` Redis cache read/write no-op hale getirildi; güncel SQL/DB datası hesaplanır.
- `database.py` değişmedi, `main.py` değişmedi.


## E-Gazete Gerçek Gazete Deneyimi — Kod Entegrasyonu

- E-Gazete modu fiziksel gazete yaprağı görünümüne geçirildi.
- Kişisel haberler, trend/gündem haberleri ve kullanıcının Kaynaklarım içerikleri aynı gazete baskısında birleştirildi.
- Haberlerin kendi görselleri kullanılıyor; görsel yoksa fallback görseller devreye giriyor.
- Sayfa çevirme hissi için paper curl, page stack, gölge ve geçiş animasyonu eklendi.
- PDF indirme butonu kişisel + trend + kaynak haberleri parametreleriyle çalışacak şekilde korundu.
- `database.py` değişmedi; backend router yapısına dokunulmadı.


## Clustered News Source Switching

Aynı olay farklı kaynaklardan geldiğinde tek haber kartı, kaynak ikonları, kaynaklar arası geçiş, cluster detay endpointi ve Türkiye haber kaynak katalogları eklendi.

## Clustered News Sources — Tek Haber Kartı + Kaynak Geçişi

- 25+ Türkiye haber RSS/fallback kaynak katalogları eklendi.
- API provider katalogları eklendi: GNews, NewsAPI, Mediastack, World News API, Event Registry / NewsAPI.ai.
- `GET /api/feed?clustered=true` cluster response destekler.
- `GET /api/articles/clusters/:clusterId` tek cluster detayını döndürür.
- `GET /api/articles/:articleId` cluster içi kaynak versiyonlarını da bulabilir.
- Aynı olay tek haber kartı olarak gösterilir.
- Kartta kaynak ikonları, `+N kaynak` butonu ve kaynak değiştirme davranışı eklendi.
- Detay modalına kaynak sekmeleri ve kaynak karşılaştırması eklendi.
- E-Gazete, PDF, paylaşım, TR/EN, kategori filtreleri ve no-cache düzeni korunmuştur.


## E-Gazete Collapsible Source Panel — 2026-06-21

- Sağ kaynak sütunu açılır/kapanır panel haline getirildi.
- Panel açıkken mevcut sağ sütun korunur; kapalıyken küçük “Kaynaklar” sekmesiyle geri çağrılır.
- Ana gazete alanı iki sayfa olacak şekilde sadeleştirildi.
- Her sayfada iki haber gösterilecek şekilde düzenlendi.
- Mobil taşma kontrolü ve responsive davranış eklendi.
- Cache sürümü `egazete-drawer-20260621-01` olarak güncellendi.
- `database.py` ve `backend/app/main.py` değiştirilmedi.


## E-Gazete Referans Görünüm Düzenlemesi

- Kullanıcının gönderdiği son referans görseline göre e-Gazete iki sayfalı gazete düzeni ve sağ kaynak paneli yeniden hizalandı.
- Sağ panel korunarak aç/kapat davranışı devam ettirildi.
- index asset versiyonu yenilendi.

## Feedback Center — Sağ Alt İkonlu Geri Bildirim Merkezi

- Sağ alt sadece ikonlu kırmızı/bordo geri bildirim butonu eklendi.
- Kullanıcı modal içinden öneri, hata bildirimi, şikayet, yeni özellik, memnuniyet ve genel mesaj gönderebilir.
- Kullanıcı kendi mesaj geçmişini `Mesajlarım` sekmesinden görebilir.
- Backend endpointleri eklendi: `/api/feedback`, `/api/feedback/my`, `/api/feedback/my/:id`.
- Admin endpointleri eklendi: `/api/admin/feedback`, detay, status, reply ve archive.
- Admin paneline `Kullanıcı Geri Bildirimleri` sayfası eklendi.
- Admin cevabı kullanıcı bildirimlerine `Admin geri bildiriminize cevap verdi.` mesajıyla düşer.
- XSS için düz metin sanitization, backend validation ve rate limit eklendi.
- Mevcut e-Gazete, PDF, paylaşım, kaynak paneli ve haber akışı korunmuştur.

## Multi-Source Event Discovery — Şehrindeki Etkinlikler

Etkinlik bölümü multi-source adapter mimarisiyle yenilendi. Biletix, Bubilet, Passo, Mobilet, Biletinial, Ticketmaster, Eventbrite, Meetup, Kültür İstanbul, İBB Kültür Sanat, Zorlu PSM, AKM ve ek RSS/API kaynakları için adapter dosyaları eklendi. Event normalize/dedupe aggregator kuruldu. Frontend etkinlik kartları gerçek görsel, kaynak ikonları, fiyat, mekan, tarih, bilet, favori, takvim ve hatırlatıcı akışıyla güncellendi.
