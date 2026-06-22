# Modül 6 — Setup & Checklist

Bu doküman Modül 6 için toplu kurulum, endpoint özeti ve doğrulama kontrol listesini içerir.

## Modül 6 Genel Akış

1. Uygulama başlangıcında duplicate olmayan haberler BM25 index’e alınır.
2. Her haber için `title + summary + content[:500]` metni tokenize edilir.
3. Türkçe karakterleri koruyan tokenizer noktalama ve stop word temizliği yapar.
4. Kullanıcı arama yaparsa `BM25Engine` query skorlarını hesaplar.
5. Arama skoru yüksek ilk 200 `article_id` alınır.
6. Gelişmiş filtre varsa SQL query içinde bu ID’ler category/source/date/language filtreleriyle daraltılır.
7. Kullanıcı bookmark eklerse `user_bookmarks` tablosuna optimistic insert yapılır.
8. `UNIQUE(user_id, article_id)` constraint duplicate bookmark’ı engeller.
9. Trend haberlerde son 72 saatteki haberler değerlendirilir.
10. `trend_score = view_count × e^(-0.05 × hours_since_published)` ile sıralama yapılır.
11. Endpointler search, advanced filter, bookmark ve trending sonuçlarını döndürür.
12. `database.py` değişmez, `main.py` sadece router include için değişir.

## Modül 6 Toplu Kurulum

```bash
pip install rank-bm25
pip install redis celery[redis]
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Modül 6 Endpoint Özeti

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

## Modül 6 Kontrol Listesi

- [x] `backend/app/ml/search/bm25_engine.py` oluşturuldu.
- [x] `backend/app/services/search_service.py` oluşturuldu.
- [x] `backend/app/services/advanced_search_service.py` oluşturuldu.
- [x] `backend/app/services/bookmark_service.py` oluşturuldu.
- [x] `backend/app/services/trending_service.py` oluşturuldu.
- [x] `backend/app/routers/search.py` oluşturuldu.
- [x] `backend/app/routers/advanced_search.py` oluşturuldu.
- [x] `backend/app/routers/bookmarks.py` oluşturuldu.
- [x] `backend/app/routers/trending.py` oluşturuldu.
- [x] Türkçe tokenizer `çğıöşü` karakterlerini koruyor.
- [x] BM25 `k1=1.5` ve `b=0.75` ile kuruluyor.
- [x] Duplicate haberler BM25 index’e alınmıyor.
- [x] `GET /api/search?q=...` endpoint wiring’i çalışıyor.
- [x] `POST /api/search/rebuild-index` endpoint wiring’i çalışıyor.
- [x] `q` varsa advanced search BM25 top 200 ID kullanıyor.
- [x] `q` yoksa advanced search sadece SQL filtre kullanıyor.
- [x] Category/source/date/language filtreleri servis seviyesinde destekleniyor.
- [x] `only_bookmarked` filtresi `user_bookmarks` join ile çalışıyor.
- [x] Bookmark optimistic insert + `IntegrityError` yakalama kullanıyor.
- [x] Aynı kullanıcı aynı haberi iki kez bookmark edemiyor; DB unique constraint bunu garanti ediyor.
- [x] Bookmark toggle ekleme/kaldırma yapıyor.
- [x] Bookmark eklenince `user_events` içine `BOOKMARKED` yazılıyor.
- [x] Trend formülü `view_count × e^(-0.05 × hours)` olarak uygulanıyor.
- [x] Trend `window_hours=72` varsayılan.
- [x] `is_duplicate=True` haberler trend listesine girmiyor.
- [x] `sort_by=trend` advanced search ile aynı `TrendingService` formülünü kullanıyor.
- [x] Redis yoksa trend sistemi cache olmadan çalışıyor.
- [x] Celery `refresh_trending_cache` `*/10 dakika` planlandı.
- [x] `database.py` hiç değişmedi.
- [x] `main.py` sadece router include için değişti.
- [x] `python -m compileall -q backend` başarılı.
- [x] FastAPI route check başarılı.

## Sonraki Parça

Sıradaki geliştirme paketi: **Modül 7 — Analytics & Recommendation**.
