# Modül 6 — Search / Bookmark / Trending

Bu doküman Modül 6 kapsamındaki arama, gelişmiş filtre, bookmark ve trending özelliklerini özetler.

## Genel Akış

1. Uygulama başlangıcında veya manuel endpoint ile duplicate olmayan haberler BM25 index’e alınır.
2. Her haber için `title + summary + content[:500]` metni tokenize edilir.
3. Türkçe karakterleri koruyan tokenizer noktalama ve stop word temizliği yapar.
4. Kullanıcı arama yaparsa `BM25Engine` query skorlarını hesaplar.
5. Arama skoru yüksek ilk 200 `article_id` gelişmiş filtre katmanına aktarılabilir.
6. SQL filtreleri category/source/date/language/bookmark koşullarıyla sonuçları daraltır.
7. Kullanıcı bookmark eklerse `user_bookmarks` tablosuna optimistic insert yapılır.
8. `UNIQUE(user_id, article_id)` duplicate bookmark’ı engeller.
9. Trend haberlerde son 72 saatteki duplicate olmayan haberler değerlendirilir.
10. `trend_score = view_count × e^(-0.05 × hours_since_published)` ile sıralama yapılır.
11. Endpointler search, advanced filter, bookmark ve trending sonuçlarını döndürür.
12. `database.py` değişmez, `main.py` sadece router include için değişir.

## Modül 6 Toplu Kurulum

```bash
pip install rank-bm25
pip install redis celery[redis]
```

veya:

```bash
pip install -r backend/requirements.txt
```

## Endpoint Özeti

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

## P27 — Keyword Search / BM25

Eklenen dosyalar:

- `backend/app/ml/search/bm25_engine.py`
- `backend/app/ml/search/__init__.py`
- `backend/app/services/search_service.py`
- `backend/app/routers/search.py`

BM25 ayarları:

- `k1=1.5`
- `b=0.75`
- `rank_bm25.BM25Okapi`
- `rank-bm25` kurulu değilse import aşamasında çökmesin diye fallback implementation bulunur.

Türkçe tokenizer:

```python
re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ]", " ", text.lower())
```

Stop word listesi:

```text
ve, veya, ile, bir, bu, şu, o, da, de, mi, mı, için, olarak, olan, gibi, çok, daha, sonra
```

## P28 — Advanced Filters / BM25 + SQL Hybrid Search

Eklenen dosyalar:

- `backend/app/schemas/search_filters.py`
- `backend/app/services/advanced_search_service.py`
- `backend/app/routers/advanced_search.py`
- `backend/sql/search_filter_indexes.sql`
- `backend/MODULE_6_P28_ADVANCED_SEARCH.md`

Desteklenen filtreler:

- `q`
- `category_ids`
- `source_ids`
- `date_from`
- `date_to`
- `language`
- `only_bookmarked`
- `sort_by=relevance|date|popularity|trend`
- `page`
- `page_size`

Notlar:

- `q` varsa önce BM25 top 200 article ID alınır, sonra SQL filtreleri uygulanır.
- `q` yoksa sadece SQL filtreleme çalışır.
- `only_bookmarked=true` için `user_id` zorunludur.
- `sort_by=trend`, P30 `TrendingService.calculate_trend_score()` metodunu kullanır.

## P29 — Bookmark CRUD / Optimistic Upsert

Eklenen dosyalar:

- `backend/app/services/bookmark_service.py`
- `backend/app/schemas/bookmarks.py`
- `backend/app/routers/bookmarks.py`
- `backend/migrations/20260621_add_user_bookmarks.sql`
- `backend/MODULE_6_P29_BOOKMARKS.md`

Notlar:

- Bookmark ekleme optimistic INSERT + `IntegrityError` yakalama ile çalışır.
- `UNIQUE(user_id, article_id)` duplicate bookmark’ı DB seviyesinde engeller.
- Duplicate haberler bookmark edilemez.
- Bookmark eklenince `user_events` içine `BOOKMARKED` kaydı atılır.
- Bookmark kaldırılınca `UNBOOKMARKED` sinyali yazılır.

## P30 — Trending Detection / Temporal Decay Trend Score

Eklenen dosyalar:

- `backend/app/services/trending_service.py`
- `backend/app/tasks/trending_tasks.py`
- `backend/app/routers/trending.py`
- `backend/MODULE_6_P30_TRENDING.md`

Formül:

```text
trend_score = view_count × e^(-0.05 × hours_since_published)
```

Notlar:

- Sadece son `72` saat içindeki haberler varsayılan trend listesine girer.
- `is_duplicate=True` haberler dışlanır.
- Redis varsa trend sonuçları 5 dakika cache’lenir.
- Redis yoksa cache olmadan çalışır.
- Celery Beat her 10 dakikada `refresh_trending_cache` task’ını çalıştırır.

## Kontrol Listesi

Kontrol listesi için bkz. `backend/MODULE_6_SETUP_AND_CHECKLIST.md`.

## Korunan Şartlar

- `database.py` değişmedi.
- `main.py` sadece router import/include için değişti.
- Frontend UI/CSS/HTML tarafına dokunulmadı.

## Sonraki Parça

Sıradaki geliştirme paketi: **Modül 7 — Analytics & Recommendation**.
