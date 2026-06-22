# MODÜL 7 / P34 — Engagement Analytics / SQL Aggregation

## Amaç

`user_events`, `articles`, `categories`, `sources` ve `user_bookmarks` verilerinden admin/reporting ekranları için engagement istatistikleri üretir.

## Eklenen Dosyalar

- `backend/app/services/analytics_service.py`
- `backend/app/routers/analytics.py`

## Endpointler

```http
GET /api/analytics/overview
GET /api/analytics/dau?days=30
GET /api/analytics/top-articles?days=7&limit=20
GET /api/analytics/categories?days=30
GET /api/analytics/user/{user_id}?days=30
GET /api/analytics/sources?days=30
```

## DAU — Daily Active Users

`user_events.created_at` üzerinden günlük benzersiz kullanıcı sayısı hesaplanır.

Mantık:

```sql
SELECT DATE(created_at), COUNT(DISTINCT user_id)
FROM user_events
WHERE created_at >= now() - interval '30 days'
GROUP BY DATE(created_at)
ORDER BY DATE(created_at);
```

## Top Articles

Weighted engagement score:

```text
VIEWED * 0.3 + READ * 1.0 + BOOKMARKED * 1.5 + SHARED * 2.0
```

Duplicate haberler dışlanır:

```text
Article.is_duplicate = False
```

## Category Reads

`article_categories`, `categories` ve `user_events` join edilir.

Sayılır:

- `read_count`
- `unique_users`
- `avg_duration_seconds`
- `avg_scroll_percent`
- `engagement_score`

## User Analytics

Kullanıcı bazlı dönen alanlar:

- `total_events`
- `read_count`
- `bookmark_count`
- `share_count`
- `avg_duration_seconds`
- `avg_scroll_percent`
- `favorite_categories`
- `last_active_at`

Auth altyapısı henüz bağlanmadığı için endpoint içinde TODO bırakıldı. Geçici olarak `requester_user_id` ve `requester_role` query parametreleriyle hedeflenen izin mantığı simüle edilebilir.

## Source Performance

`sources`, `articles` ve `user_events` üzerinden kaynak performansı ölçülür:

- `article_count`
- `total_views`
- `avg_trust_score`
- `engagement_score`

## Overview

Dashboard için hızlı özet:

- `total_users`
- `total_articles`
- `total_events`
- `total_bookmarks`
- `active_users_7d`
- `top_category`
- `top_article`

## Cache

Redis varsa analytics sonuçları 5 dakika cache’lenir.

Cache key örnekleri:

```text
analytics:dau:{days}:0
analytics:top_articles:{days}:{limit}
analytics:categories:{days}:0
analytics:sources:{days}:0
analytics:overview:0:0
```

Redis yoksa veya cache hatası oluşursa sistem cache olmadan SQL sorgularıyla çalışır.

## Doğrulama Notları

- `database.py` değiştirilmedi.
- `main.py` sadece `analytics` router import/include için değişti.
- Redis yoksa analytics sistemi cache olmadan çalışır.
- `python -m compileall -q backend` başarılıdır.
- FastAPI route check başarılıdır.
