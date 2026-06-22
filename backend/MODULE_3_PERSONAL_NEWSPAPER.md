# MODÜL 3 — Personal Newspaper Toplu Kurulum ve Kontrol Listesi

Bu dosya Modül 3 kapsamındaki P12, P13, P14, P15, P16 ve P17 çalışmalarının kurulum komutlarını, genel akışını ve doğrulama kontrol listesini içerir.

## Modül 3 Toplu Kurulum

```bash
pip install scikit-learn scipy numpy redis
pip install jinja2 arrow
pip install celery[redis] redis
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Modül 3 Genel Akış

1. Kullanıcının okuduğu haberler `user_events` tablosundan alınır.
2. Kullanıcının okuduğu haberlerden TF-IDF ortalama vektörü çıkarılır.
3. Content-Based öneri skoru hesaplanır.
4. Benzer kullanıcıların okuduğu haberlerden Collaborative Filtering skoru hesaplanır.
5. CB `%60` + CF `%40` hibrit skor üretilir.
6. Cold start kullanıcı için `user_interests` + popüler haber fallback uygulanır.
7. Kullanıcı filtreleriyle haber listesi daraltılır.
8. Manşet sıralaması temporal decay + relevance + popularity + trust skoruyla yapılır.
9. Jinja2 template ile dijital gazete HTML’i üretilir.
10. Citation bilgileri her haberin altına eklenir.
11. `newspaper_editions` tablosuna `html_content` kaydedilir.
12. Sonraki Modül 4’te aynı HTML PDF’e dönüştürülecek.

## P12 / P13 / P14 / P15 / P16 / P17 Endpoint Özeti

### P12 — Hybrid Recommender

```bash
GET  /api/personal/feed?user_id=<USER_ID>&limit=30
GET  /api/personal/feed/{user_id}?limit=30
POST /api/personal/rebuild-index?language=tr
GET  /api/personal/recommendation-debug?user_id=<USER_ID>
```

### P13 — Article Filtering

```bash
GET /api/articles?category_id=1&source_ids=1,2&date_from=2026-06-01&language=tr&sort_by=popularity&page=1&page_size=20
```

### P14 — Newspaper Layout Preview

```bash
POST /api/newspaper/preview-html
```

### P15 — Headline Prioritization

```bash
POST /api/newspaper/rank-headlines
GET  /api/articles/top-headlines
```

### P16 — Newspaper Citations

```bash
GET  /api/newspaper/articles/{article_id}/citation
POST /api/newspaper/citations/batch
```

### P17 — Newspaper Edition Pipeline

```bash
POST   /api/newspaper/editions/generate
GET    /api/newspaper/editions/me?user_id=<USER_ID>
GET    /api/newspaper/editions/{edition_id}
DELETE /api/newspaper/editions/{edition_id}
```

## Modül 3 Kontrol Listesi

- [x] Hybrid recommender CB `%60` + CF `%40` çalışıyor.
- [x] Okunmuş haberler öneriden çıkarılıyor.
- [x] Cold start `user_interests` + popüler haber fallback çalışacak şekilde servis akışı hazır.
- [x] Article filtering category/source/date/language destekliyor.
- [x] Pagination `page` / `page_size` ile doğru offset/limit üretiyor.
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

## Notlar

- `database.py` dosyasına dokunulmadı.
- Frontend UI/CSS/HTML dosyalarına dokunulmadı; ekran kayması oluşturacak değişiklik yapılmadı.
- P17 ile üretilen `html_content`, Modül 4 PDF export için hazır tutulur.


---

# MODÜL 3 — Personal Newspaper / P12 Hybrid Recommender

Bu doküman, kişisel haber akışı için Content-Based Filtering, User-Based Collaborative Filtering ve cold-start fallback yapısını açıklar.

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
10. Redis ile kullanıcı başına 5 dakikalık cache kullanılabilir.
11. `newspaper_editions` tablosu, sonraki Modül 4 PDF üretimi için HTML içerik saklamaya hazırdır.

## P12 — Hybrid Recommender

### Content-Based Filtering

Dosya:

- `backend/app/ml/recommenders/content_based.py`

Özellikler:

- `TfidfVectorizer`
- `max_features=30000`
- `ngram_range=(1, 2)`
- `sublinear_tf=True`
- `min_df=2`
- `strip_accents="unicode"`
- Duplicate olmayan haberleri indeksler: `is_duplicate=False`
- Kullanıcı profili: okunan haber TF-IDF vektörlerinin ortalaması
- Öneri skoru: cosine similarity

Küçük development verilerinde `min_df=2` corpus'u boşaltırsa sistem çökmesin diye güvenli `min_df=1` fallback vardır.

### User-Based Collaborative Filtering

Dosya:

- `backend/app/ml/recommenders/user_cf.py`

Event ağırlıkları:

| Event | Ağırlık |
|---|---:|
| `VIEWED` | `0.3` |
| `READ` | `1.0` |
| `BOOKMARKED` | `1.5` |
| `SHARED` | `2.0` |
| `SKIPPED` | `0.0` |

Ek davranışlar:

- `scroll_percent` varsa `min(scroll_percent / 100, 1.0)` ile rating güçlendirilir.
- `duration_seconds` varsa uzun okumalar küçük bonus alır.
- Kullanıcılar arası cosine similarity hesaplanır.
- En benzer `K=20` kullanıcı kullanılır.
- Tahmin formülü:

```text
pred(u, article_i) =
mean(u) + sum(sim(u,v) * (rating(v,i) - mean(v))) / sum(abs(sim(u,v)))
```

### Hibrit Birleştirme

Dosya:

- `backend/app/ml/recommenders/hybrid_recommender.py`

Formül:

```text
final_score = 0.60 * norm_cb + 0.40 * norm_cf
```

İlk 30 haber döndürülür.

### Cold Start

Dosya:

- `backend/app/services/recommendation_service.py`

Okuma geçmişi yoksa:

1. `user_interests` içindeki kategori ağırlıkları okunur.
2. İlgili kategorilerdeki `is_duplicate=False` ve `language=user.language_preference` haberler seçilir.
3. `view_count`, `source.trust_score`, kategori güveni ve ilgi ağırlığı birlikte skorlanır.
4. `user_interests` de yoksa son 24-48 saatin popüler ve güvenilir haberleri döndürülür.

## Endpointler

```bash
GET  /api/personal/feed?user_id=<USER_ID>&limit=30
GET  /api/personal/feed/{user_id}?limit=30
POST /api/personal/rebuild-index?language=tr
GET  /api/personal/recommendation-debug?user_id=<USER_ID>
```

## Yeni Dosyalar

- `backend/app/ml/recommenders/content_based.py`
- `backend/app/ml/recommenders/user_cf.py`
- `backend/app/ml/recommenders/hybrid_recommender.py`
- `backend/app/services/recommendation_service.py`
- `backend/app/routers/personal_feed.py`
- `backend/migrations/20260621_add_personal_newspaper_tables.sql`

## Yeni / Güncellenen Tablolar

Yeni tablolar:

- `user_events`
- `user_interests`
- `newspaper_editions`

Güncellenen tablo:

- `articles.summary`
- `articles.view_count`

## Kurulum

```bash
pip install scikit-learn scipy numpy redis
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Kontrol Listesi

- [x] Okuma geçmişi olan kullanıcı için hibrit öneri servis akışı var.
- [x] Okuma geçmişi olmayan kullanıcı için cold start fallback var.
- [x] Okunmuş haberler tekrar önerilmiyor.
- [x] Duplicate haberler önerilmiyor.
- [x] Kullanıcı dil tercihi uygulanıyor.
- [x] CB `%60`, CF `%40` ağırlığı korunuyor.
- [x] Redis cache key formatı `personal_feed:{user_id}:{language}` olarak hazır.
- [x] `database.py` değiştirilmedi.
- [x] UI/CSS/HTML dosyalarına dokunulmadı.

---

## PROMPT 13 — Article Filtering / Composite Index + SQL

### Amaç
Kullanıcı kişisel gazetesini oluştururken haberleri tarih, kategori, kaynak, dil, popülerlik ve relevance filtresiyle hızlı şekilde listeleyebilir.
Duplicate haberler varsayılan olarak listelenmez.

### Eklenen Dosyalar
- `backend/sql/performance_indexes.sql`
- `backend/app/schemas/article_filters.py`
- `backend/app/services/article_filter_service.py`
- `backend/app/routers/articles_filter.py`

### Endpoint
```bash
GET /api/articles?category_id=1&date_from=2026-06-01&sort_by=popularity&page=1&page_size=20
```

### Desteklenen Filtreler
- `category_id`
- `source_ids` — repeated veya comma-separated kullanılabilir: `source_ids=1&source_ids=2` veya `source_ids=1,2`
- `date_from`
- `date_to`
- `language`
- `user_id` — language verilmezse kullanıcının `language_preference` değeri kullanılabilir
- `sort_by=date|popularity|relevance`
- `page`
- `page_size` — maksimum 100

### Response Alanları
- `items`
- `page`
- `page_size`
- `total`
- `has_next`
- `filters_applied`

### Performans Index Script
`backend/sql/performance_indexes.sql` içinde PostgreSQL için tabloyu kilitlemeden çalışan composite index script’i vardır:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_filter
ON articles(published_at DESC, source_id, view_count DESC)
WHERE is_duplicate = FALSE;
```

### Kontrol Listesi
- [ ] `category_id` filtresi çalışıyor mu?
- [ ] `source_ids` çoklu filtre çalışıyor mu?
- [ ] `date_from/date_to` çalışıyor mu?
- [ ] `sort_by=popularity` `view_count DESC` sıralıyor mu?
- [ ] `page/page_size` doğru offset/limit üretiyor mu?
- [ ] Duplicate haberler varsayılan listelenmiyor mu?
- [ ] `database.py` değişmedi mi?
- [ ] `main.py` sadece router import/include için değişti mi?


## P14 — Jinja2 Layout Generation / CSS Grid Newspaper

- Dijital gazete HTML layout üretimi eklendi.
- `backend/templates/newspaper/daily.html` içinde manşet, 3 kolon grid, küçük haberler, etkinlik kutusu, citation/footer alanları bulunur.
- `LayoutService.render_daily(articles, events, user)` ile PDF'e dönüştürülebilir HTML üretilir.
- `POST /api/newspaper/preview-html` endpoint'i eklendi.
- `database.py` değiştirilmedi; `main.py` sadece router include için güncellendi.

---

## PROMPT 15 — Headline Prioritization / Temporal Decay

P15 ile kişisel gazete içindeki manşet sıralaması runtime priority score ile belirlenir.

### Eklenen Dosyalar

- `backend/app/services/prioritization_service.py`
- `backend/app/routers/prioritization.py`
- `backend/MODULE_3_P15_HEADLINE_PRIORITIZATION.md`

### Endpointler

```bash
POST /api/newspaper/rank-headlines
GET  /api/articles/top-headlines
```

### Final Skor

```text
final = 0.40 * relevance + 0.30 * recency + 0.20 * pop_norm + 0.10 * trust
```

### Davranış

- `recency = exp(-0.05 * hours_old)` kullanılır.
- `view_count` için `log10(1 + view_count)` uygulanır.
- Kullanıcı profili yoksa relevance `0.5` olur.
- `source.trust_score` yoksa trust `0.5` olur.
- `Article.priority_score` kolonu yoksa migration yapılmaz, skor response içinde döner.
- `POST /api/newspaper/preview-html` artık haberleri layout’a göndermeden önce priority score ile sıralar; manşet en yüksek skorlu haber olur.

### Kontrol Listesi

- [x] Yeni haber recency sayesinde öne çıkabilir.
- [x] Çok eski haber yüksek view count olsa bile skoru düşer.
- [x] Trust score final skora dahildir.
- [x] Kullanıcı profili yoksa relevance `0.5` fallback çalışır.
- [x] Manşet `items[0]` ve `headline` olarak en yüksek skorlu haber seçilir.
- [x] `database.py` değiştirilmedi.
- [x] UI/CSS/HTML frontend dosyalarına dokunulmadı.

## P16 — Citation Service for Personal Newspaper

- `CitationService` kişisel gazetedeki her haber için kaynak metni üretir.
- `citation_text` formatı: `{source_name} · {published_human} · Güven: {trust_badge}`.
- `LayoutService.render_daily()` citation context’i otomatik oluşturur ve Jinja2 template’e gönderir.
- API endpointleri:
  - `GET /api/newspaper/articles/{article_id}/citation`
  - `POST /api/newspaper/citations/batch`
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

