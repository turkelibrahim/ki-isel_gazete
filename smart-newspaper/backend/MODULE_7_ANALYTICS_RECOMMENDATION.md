# Modül 7 — Analytics & Recommendation

## Genel Akış

1. Kullanıcı haber görüntüler, okur, bookmark eder, paylaşır veya geçer.
2. `TrackingService` bu davranışı `user_events` tablosuna kaydeder.
3. Event type değerine göre implicit rating hesaplanır.
4. `VIEWED` / `READ` / `BOOKMARKED` / `SHARED` / `SKIPPED` ağırlıkları uygulanır.
5. Aynı kullanıcı-makale için birden fazla event varsa en güçlü sinyal alınır.
6. IBCF modeli benzer makaleleri bulur.
7. SVD modeli kullanıcı-makale gizli faktörlerini öğrenir.
8. Hibrit öneri skoru CB + IBCF + SVD + Trending ile üretilir.
9. LDA topic model haberleri konu kümelerine ayırır.
10. `AnalyticsService` DAU, top articles, category reads ve user stats üretir.
11. `AdaptiveRankingService` her event sonrası `user_interests.weight` değerini günceller.
12. Pozitif davranış ilgiyi artırır, negatif davranış ilgiyi azaltır.
13. Celery haftalık model training ve topic refresh task’larını çalıştırır.
14. `database.py` değişmez, `main.py` sadece router include için değişir.

## P31 — User Behavior Tracking / Implicit Feedback

### Eklenen Dosyalar

- `backend/app/services/tracking_service.py`
- `backend/app/schemas/tracking.py`
- `backend/app/routers/tracking.py`

### Endpointler

```http
POST /api/tracking/event
POST /api/tracking/view/{article_id}
POST /api/tracking/read/{article_id}
POST /api/tracking/skip/{article_id}
GET  /api/tracking/user/{user_id}/ratings
GET  /api/tracking/article/{article_id}/stats
```

### Event Ağırlıkları

```python
{
  "SHARED": 2.0,
  "BOOKMARKED": 1.5,
  "READ": 1.0,
  "VIEWED": 0.3,
  "SKIPPED": 0.0,
  "UNBOOKMARKED": 0.0
}
```

### Effective Rating

```text
effective_rating = weight × min(scroll_percent / 100, 1.0)
```

Scroll bilgisi yoksa fallback:

- `VIEWED`: `0.1`
- `READ`: `0.8`
- `BOOKMARKED` / `SHARED`: `1.0`

Davranış destekleri:

- `duration_seconds >= 30` ise `VIEWED` davranışı `READ` olarak güçlendirilir.
- `duration_seconds < 5` ve `scroll_percent < 10` ise davranış `SKIPPED` kabul edilir.

### MAX Signal Logic

Aynı kullanıcı ve aynı makale için birden fazla event varsa öneri sistemi en güçlü sinyali kullanır.

Örnek:

- `VIEWED`, `%10 scroll` → `0.03`
- `READ`, `%80 scroll` → `0.80`
- `BOOKMARKED`, `%100 scroll` → `1.50`

Final rating: `1.50`

### Entegrasyon Notları

- `VIEWED` ve `READ` eventlerinde `Article.view_count` artırılır.
- Event başarılı kaydedilince kişisel feed cache invalidation denenir.
- `AdaptiveRankingService` ileride eklendiğinde lazy hook üzerinden çağrılabilir.
- Döngüsel import riskine karşı adaptive hook lazy import ile korunur.
- Auth dependency henüz bağlanmadığı için geçici `user_id` query/body ile alınır ve TODO bırakılmıştır.
- `database.py` değişmedi.
- `main.py` sadece `tracking` router import/include için değişti.


## P32 — IBCF + SVD Recommendation System

- `backend/app/ml/recommender/ibcf_recommender.py` eklendi.
- `backend/app/ml/recommender/svd_recommender.py` eklendi.
- `backend/app/ml/recommender/analytics_hybrid_recommender.py` eklendi.
- `backend/app/services/recommender_training_service.py` eklendi.
- `backend/app/tasks/recommender_tasks.py` eklendi.
- `backend/app/routers/recommendations.py` eklendi.
- Haftalık Celery schedule: `crontab(day_of_week="sun", hour=3, minute=0)`.
- Model dosyaları: `backend/models/recommenders/ibcf.pkl`, `backend/models/recommenders/svd.pkl`.
- Analytics hybrid formül: `0.30 CB + 0.35 IBCF + 0.25 SVD + 0.10 Trending`.
- Model dosyaları yoksa eski Modül 3 öneri sistemi çalışmaya devam eder.


## P34 — Engagement Analytics / SQL Aggregation

- `backend/app/services/analytics_service.py` eklendi.
- `backend/app/routers/analytics.py` eklendi.
- DAU, top articles, category reads, user analytics, source performance ve overview metrikleri eklendi.
- Engagement score formülü: `VIEWED * 0.3 + READ * 1.0 + BOOKMARKED * 1.5 + SHARED * 2.0`.
- Redis varsa 5 dakika analytics cache kullanılır.
- Redis yoksa sistem cache olmadan çalışır.
- Auth altyapısı bağlanana kadar permission noktalarına TODO bırakıldı.

### Endpointler

```http
GET /api/analytics/overview
GET /api/analytics/dau?days=30
GET /api/analytics/top-articles?days=7&limit=20
GET /api/analytics/categories?days=30
GET /api/analytics/user/{user_id}?days=30
GET /api/analytics/sources?days=30
```

### Doğrulama

- `database.py` değişmedi.
- `main.py` sadece `analytics` router import/include için değişti.
- Redis yoksa analytics cache olmadan çalışır.

## P35 — Adaptive Ranking / Online Learning

- `backend/app/services/adaptive_ranking_service.py` eklendi.
- `backend/app/routers/adaptive_ranking.py` eklendi.
- `TrackingService.track_event(...)` başarılı olduktan sonra adaptive update hook çağırır.
- Adaptive update hata verirse tracking rollback edilmez; sadece warning loglanır.
- Pozitif eventler: `READ`, `BOOKMARKED`, `SHARED`.
- Negatif eventler: `SKIPPED`, `UNBOOKMARKED`.
- Online learning formülü:
  - Pozitif: `w_new = w + 0.1 * (1.0 - w)`
  - Negatif: `w_new = w - 0.1 * w`
  - Clamp: `0.0 <= w <= 1.0`
- Category confidence varsa `effective_alpha = ALPHA * confidence` kullanılır.
- Kişisel feed sonuçları `0.70 existing_recommendation_score + 0.30 interest_score` formülüyle adaptive olarak yeniden sıralanabilir.

### Endpointler

```http
GET  /api/adaptive-ranking/interests/{user_id}
POST /api/adaptive-ranking/update
POST /api/adaptive-ranking/reset/{user_id}
POST /api/adaptive-ranking/rank-preview/{user_id}
```

### Doğrulama

- `database.py` değişmedi.
- `main.py` sadece `adaptive_ranking` router import/include için değişti.
- Migration yapılmadı; `user_interests` için application-level SELECT + UPDATE kullanıldı.

## P33 — Topic Modeling / LDA

- `backend/app/ml/topic_model.py` eklendi.
- `backend/app/services/topic_service.py` eklendi.
- `backend/app/routers/topics.py` eklendi.
- `backend/app/tasks/topic_tasks.py` eklendi.
- LDA ayarları:
  - `num_topics=20`
  - `passes=15`
  - `alpha="auto"`
  - `eta="auto"`
- Dictionary temizliği:
  - `Dictionary.filter_extremes(no_below=5, no_above=0.5)`
- Coherence:
  - `CoherenceModel(coherence="c_v")`
  - hedef: `coherence > 0.4`
- Haftalık topic refresh Celery task:
  - `crontab(day_of_week="sun", hour=4, minute=0)`
- `gensim` yoksa backend import aşamasında çökmez; controlled fallback döner.

### Endpointler

```http
POST /api/topics/train
GET  /api/topics
GET  /api/topics/trending
GET  /api/topics/article/{article_id}
GET  /api/topics/status
```

## Modül 7 Toplu Kurulum ve Kontrol Listesi

Detaylı kurulum/endpoint/checklist dosyası:

- `backend/MODULE_7_SETUP_AND_CHECKLIST.md`

Sıradaki son parça: **Modül 8 — Reporting & Administration**.
