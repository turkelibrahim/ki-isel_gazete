# MODÜL 7 / PROMPT 32 — IBCF + SVD Recommendation System

## Amaç

TrackingService tarafından üretilen implicit rating verilerini kullanarak IBCF + SVD tabanlı gelişmiş öneri sistemi eklendi. Modül 3'teki kişisel gazete öneri sistemi bozulmadan, model dosyaları varsa yeni analytics hybrid skor devreye girer; model dosyaları yoksa eski CB %60 + CF %40 akışı çalışmaya devam eder.

## Eğitim Datası

`TrackingService.get_user_ratings_matrix(db)` kullanılır.

Aynı `user_id + article_id` için birden fazla event varsa en güçlü sinyal alınır.

Rating scale:

```python
Reader(rating_scale=(0, 2.0))
```

Çünkü `SHARED = 2.0` olabilir.

## IBCF

Dosya:

```text
backend/app/ml/recommender/ibcf_recommender.py
```

Model:

```python
KNNWithMeans(
    k=20,
    sim_options={
        "name": "cosine",
        "user_based": False,
        "min_support": 3,
    },
)
```

`user_based=False` olduğu için item-based collaborative filtering çalışır.

## SVD

Dosya:

```text
backend/app/ml/recommender/svd_recommender.py
```

Model:

```python
SVD(
    n_factors=50,
    n_epochs=20,
    lr_all=0.005,
    reg_all=0.02,
)
```

Formül:

```text
r_hat(u,i) = μ + b_u + b_i + p_u · q_i
```

## Analytics Hybrid Formül

Dosya:

```text
backend/app/ml/recommender/analytics_hybrid_recommender.py
```

Formül:

```text
final = 0.30 * content_based_score
      + 0.35 * ibcf_score
      + 0.25 * svd_score
      + 0.10 * trending_score
```

Tüm skorlar 0-1 aralığına normalize edilir. Eksik skor 0.0 kabul edilir.

## Model Training Service

Dosya:

```text
backend/app/services/recommender_training_service.py
```

Çıktı model dosyaları:

```text
backend/models/recommenders/ibcf.pkl
backend/models/recommenders/svd.pkl
```

Eğitim datası yetersizse controlled warning döner. Eski model varsa silinmez.

## Celery Task

Dosya:

```text
backend/app/tasks/recommender_tasks.py
```

Task:

```text
app.tasks.recommender_tasks.train_recommender_models
```

Schedule:

```python
crontab(day_of_week="sun", hour=3, minute=0)
```

## Endpointler

```http
POST /api/recommendations/train
GET  /api/recommendations/status
GET  /api/recommendations/user/{user_id}
GET  /api/recommendations/debug/{user_id}
```

## Kurulum

```bash
pip install scikit-surprise pandas joblib numpy
```

## Güvenli Fallback

`scikit-surprise` kurulu değilse backend import aşamasında çökmez. Eğitim endpoint'i `scikit-surprise-not-installed` durumunu controlled response olarak döner.

Model dosyaları yoksa `RecommendationService` eski Modül 3 hybrid recommender ile çalışmaya devam eder.

## Kontrol Listesi

- [ ] user_events verisinden Surprise Dataset oluşuyor mu?
- [ ] IBCF KNNWithMeans user_based=False çalışıyor mu?
- [ ] SVD n_factors=50 ile eğitiliyor mu?
- [ ] cross_validate RMSE/MAE döndürüyor mu?
- [ ] Model dosyaları joblib ile kaydediliyor mu?
- [ ] Eğitim başarısızsa eski model silinmiyor mu?
- [ ] Hibrit formül 0.30 CB + 0.35 IBCF + 0.25 SVD + 0.10 trending mi?
- [ ] database.py değişmedi mi?
- [ ] main.py sadece router include için değişti mi?
