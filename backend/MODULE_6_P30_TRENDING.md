# Modül 6 / Prompt 30 — Trending Detection / Temporal Decay Trend Score

Bu parça son 72 saat içindeki duplicate olmayan haberleri temporal decay + popularity formülüyle trend olarak sıralar.

## Trend Formülü

```text
trend_score(article) = view_count × e^(-0.05 × hours_since_published)
```

Kurallar:

- `λ = 0.05`
- `published_at` yoksa `hours_since_published = 24`
- `view_count` yoksa `0`
- Varsayılan pencere: `72 saat`
- `Article.is_duplicate=False` şartı her zaman uygulanır.

## Eklenen Dosyalar

- `backend/app/services/trending_service.py`
- `backend/app/tasks/trending_tasks.py`
- `backend/app/routers/trending.py`

## Endpointler

```bash
GET  /api/trending?limit=20&window_hours=72&language=tr&source_ids=1,2,3
GET  /api/trending/category/{category_id}?limit=20
POST /api/trending/refresh-cache
```

## Filtreler

- `category_id`
- `language`
- `source_ids`
- `limit`
- `window_hours`

## Cache

Trend sonuçları Redis varsa 5 dakika cache’lenir. Redis yoksa cache olmadan çalışır.

Cache key örneği:

```text
trending:{language}:{category_id}:{source_ids}:{window_hours}:{limit}
```

## Celery Task

Task:

```text
app.tasks.trending_tasks.refresh_trending_cache
```

Celery Beat schedule:

```python
crontab(minute="*/10")
```

Her 10 dakikada trend cache yenilenebilir.

## Advanced Search Entegrasyonu

Prompt 28’deki `sort_by=trend` artık aynı `TrendingService.calculate_trend_score()` metodunu kullanır. Böylece trend formülü iki farklı yerde kopyalanmaz.

## Kontrol Listesi

- [x] Son 72 saat dışındaki haberler trend listesine girmez.
- [x] `is_duplicate=True` haberler trend listesine girmez.
- [x] `trend_score = view_count × e^(-0.05 × hours_since_published)` formülü uygulanır.
- [x] Çok eski haberler temporal decay ile aşağı düşer.
- [x] `GET /api/trending` endpoint’i eklendi.
- [x] `GET /api/trending/category/{category_id}` endpoint’i eklendi.
- [x] `POST /api/trending/refresh-cache` endpoint’i eklendi.
- [x] `sort_by=trend` advanced search ile ortak servis üzerinden uyumlu çalışır.
- [x] `database.py` değişmedi.
- [x] `main.py` sadece router include için değişti.
