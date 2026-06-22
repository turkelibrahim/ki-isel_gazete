# Modül 7 / P35 — Adaptive Ranking / Online Learning

## Amaç

Kullanıcı etkileşimlerinden `user_interests.weight` değerlerini gerçek zamanlı güncelleyerek kişisel gazete önerilerinin kullanıcının değişen ilgilerine uyum sağlamasını sağlar.

## Online Learning Formülü

Sabit öğrenme oranı:

```text
ALPHA = 0.1
```

Pozitif etkileşimler:

- `READ`
- `BOOKMARKED`
- `SHARED`

Pozitif güncelleme:

```text
w_new = w + ALPHA * (1.0 - w)
```

Negatif etkileşimler:

- `SKIPPED`
- `UNBOOKMARKED`

Negatif güncelleme:

```text
w_new = w - ALPHA * w
```

Clamp:

```text
w_new = max(0.0, min(1.0, w_new))
```

Kategori confidence varsa:

```text
effective_alpha = ALPHA * confidence
```

## Dosyalar

- `backend/app/services/adaptive_ranking_service.py`
- `backend/app/routers/adaptive_ranking.py`

## Endpointler

```http
GET  /api/adaptive-ranking/interests/{user_id}
POST /api/adaptive-ranking/update
POST /api/adaptive-ranking/reset/{user_id}
POST /api/adaptive-ranking/rank-preview/{user_id}
```

## Tracking Entegrasyonu

`TrackingService.track_event(...)` başarılı olduktan sonra lazy import ile:

```python
AdaptiveRankingService().update_weights_from_event(...)
```

çağrılır. Adaptive update hata verirse tracking rollback edilmez; sadece warning log yazılır.

## Recommendation Entegrasyonu

`RecommendationService.get_personalized_feed(...)` sonuçları üretildikten sonra adaptive interest ranking uygulanır.

Final skor:

```text
final_score = 0.70 * existing_recommendation_score + 0.30 * interest_score
```

`existing_recommendation_score` yoksa `0.5` fallback kullanılır.

`interest_score`, makalenin kategori confidence değerleriyle kullanıcının `user_interests.weight` değerlerinin ağırlıklı ortalamasıdır.

## Kontrol Listesi

- [ ] `READ` event kategori weight değerini artırıyor mu?
- [ ] `BOOKMARKED` ve `SHARED` pozitif davranış kabul ediliyor mu?
- [ ] `SKIPPED` weight değerini azaltıyor mu?
- [ ] `UNBOOKMARKED` weight değerini azaltıyor mu?
- [ ] Weight `0.0` altına düşmüyor mu?
- [ ] Weight `1.0` üstüne çıkmıyor mu?
- [ ] Bir makale birden fazla kategoriye sahipse tüm kategoriler güncelleniyor mu?
- [ ] Category confidence varsa `effective_alpha = ALPHA * confidence` uygulanıyor mu?
- [ ] Tracking event adaptive update hatasında rollback olmadan devam ediyor mu?
- [ ] Recommendation response adaptive interest skorundan etkileniyor mu?
- [ ] `database.py` değişmedi mi?
- [ ] `main.py` sadece router include için değişti mi?
