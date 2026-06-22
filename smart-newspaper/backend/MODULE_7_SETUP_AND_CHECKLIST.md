# Modül 7 — Toplu Kurulum, Endpoint Özeti ve Kontrol Listesi

## Modül 7 Toplu Kurulum

```bash
pip install scikit-surprise pandas joblib numpy
pip install gensim
pip install redis celery[redis]
```

## Modül 7 Endpoint Özeti

```http
POST /api/tracking/event
POST /api/tracking/view/{article_id}
POST /api/tracking/read/{article_id}
POST /api/tracking/skip/{article_id}
GET  /api/tracking/user/{user_id}/ratings
GET  /api/tracking/article/{article_id}/stats

POST /api/recommendations/train
GET  /api/recommendations/status
GET  /api/recommendations/user/{user_id}
GET  /api/recommendations/debug/{user_id}

POST /api/topics/train
GET  /api/topics
GET  /api/topics/trending
GET  /api/topics/article/{article_id}
GET  /api/topics/status

GET  /api/analytics/overview
GET  /api/analytics/dau?days=30
GET  /api/analytics/top-articles?days=7&limit=20
GET  /api/analytics/categories?days=30
GET  /api/analytics/user/{user_id}?days=30
GET  /api/analytics/sources?days=30

GET  /api/adaptive-ranking/interests/{user_id}
POST /api/adaptive-ranking/update
POST /api/adaptive-ranking/reset/{user_id}
POST /api/adaptive-ranking/rank-preview/{user_id}
```

## Modül 7 Kontrol Listesi

- [ ] `backend/app/services/tracking_service.py` oluşturuldu mu?
- [ ] `backend/app/schemas/tracking.py` oluşturuldu mu?
- [ ] `backend/app/routers/tracking.py` oluşturuldu mu?
- [ ] `EVENT_WEIGHTS` `SHARED=2.0`, `BOOKMARKED=1.5`, `READ=1.0`, `VIEWED=0.3`, `SKIPPED=0.0` mı?
- [ ] `effective_rating = weight × min(scroll_percent/100, 1.0)` uygulanıyor mu?
- [ ] Aynı `user_id + article_id` için max rating mantığı uygulanıyor mu?
- [ ] `VIEWED/READ` eventlerinde `Article.view_count` artıyor mu?

- [ ] `backend/app/ml/recommender/ibcf_recommender.py` oluşturuldu mu?
- [ ] `backend/app/ml/recommender/svd_recommender.py` oluşturuldu mu?
- [ ] `backend/app/ml/recommender/analytics_hybrid_recommender.py` oluşturuldu mu?
- [ ] `backend/app/services/recommender_training_service.py` oluşturuldu mu?
- [ ] IBCF `KNNWithMeans k=20, user_based=False, cosine, min_support=3` ile çalışıyor mu?
- [ ] SVD `n_factors=50, n_epochs=20, lr_all=0.005, reg_all=0.02` ile çalışıyor mu?
- [ ] `cross_validate` RMSE/MAE hesaplıyor mu?
- [ ] Hibrit skor `0.30 CB + 0.35 IBCF + 0.25 SVD + 0.10 trending` mi?
- [ ] Haftalık recommender Celery task tanımlandı mı?

- [ ] `backend/app/ml/topic_model.py` oluşturuldu mu?
- [ ] `backend/app/services/topic_service.py` oluşturuldu mu?
- [ ] `backend/app/routers/topics.py` oluşturuldu mu?
- [ ] LDA `num_topics=20`, `passes=15`, `alpha='auto'`, `eta='auto'` ile eğitiliyor mu?
- [ ] `Dictionary.filter_extremes(no_below=5, no_above=0.5)` uygulanıyor mu?
- [ ] `CoherenceModel coherence='c_v'` hesaplıyor mu?
- [ ] `coherence > 0.4` hedefi raporlanıyor mu?
- [ ] `GET /api/topics/trending` çalışıyor mu?

- [ ] `backend/app/services/analytics_service.py` oluşturuldu mu?
- [ ] `backend/app/routers/analytics.py` oluşturuldu mu?
- [ ] DAU SQL aggregation çalışıyor mu?
- [ ] Top articles `engagement_score` ile sıralanıyor mu?
- [ ] Category reads `avg_duration` ve `avg_scroll_percent` hesaplıyor mu?
- [ ] User analytics endpoint doğru istatistikleri dönüyor mu?
- [ ] Redis yoksa analytics cache olmadan çalışıyor mu?

- [ ] `backend/app/services/adaptive_ranking_service.py` oluşturuldu mu?
- [ ] `backend/app/routers/adaptive_ranking.py` oluşturuldu mu?
- [ ] Pozitif event için `w += 0.1 × (1.0 - w)` uygulanıyor mu?
- [ ] Negatif event için `w -= 0.1 × w` uygulanıyor mu?
- [ ] Weight `0-1` arasında clamp ediliyor mu?
- [ ] `TrackingService` adaptive update hook çağırıyor mu?
- [ ] Birden fazla kategoriye sahip makalede tüm kategoriler güncelleniyor mu?

- [ ] `database.py` hiç değişmedi mi?
- [ ] `main.py` sadece router include için değişti mi?
- [ ] `python -m compileall -q backend` başarılı mı?
- [ ] FastAPI route check başarılı mı?
- [ ] `npm test` hâlâ `70/70 passed` mı?
- [ ] `npm run build` başarılı mı?

## Sonraki Parça

Sıradaki son parça: **Modül 8 — Reporting & Administration**.
