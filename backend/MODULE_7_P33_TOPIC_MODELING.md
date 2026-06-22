# Modül 7 — P33 Topic Modeling / LDA

## Amaç

Haberleri konu kümelerine ayırmak, trend olan konuları çıkarmak ve analytics/recommendation modüllerine konu bilgisi sağlamak.

## Algoritma

- Model: `gensim.models.LdaModel`
- `num_topics=20`
- `passes=15`
- `alpha="auto"`
- `eta="auto"`
- Dictionary filtering:
  - `Dictionary.filter_extremes(no_below=5, no_above=0.5)`
- Coherence:
  - `CoherenceModel(..., coherence="c_v")`
- Hedef kalite notu:
  - `coherence > 0.4`

## Eklenen Dosyalar

- `backend/app/ml/topic_model.py`
- `backend/app/services/topic_service.py`
- `backend/app/routers/topics.py`
- `backend/app/tasks/topic_tasks.py`
- `backend/models/topics/.gitkeep`

## Endpointler

```http
POST /api/topics/train
GET  /api/topics
GET  /api/topics/trending
GET  /api/topics/article/{article_id}
GET  /api/topics/status
```

## Celery

Haftalık topic refresh task eklendi:

```python
crontab(day_of_week="sun", hour=4, minute=0)
```

Task adı:

```text
app.tasks.topic_tasks.refresh_topic_model
```

## Fallback Davranışı

- `gensim` kurulu değilse backend import sırasında çökmez.
- Eğitim endpoint’i kontrollü `gensim-not-installed` sonucu döndürür.
- Model yoksa `GET /api/topics` basit keyword/topic fallback döndürebilir.
- Küçük veri setlerinde `filter_extremes(no_below=5, no_above=0.5)` sözlüğü boşaltırsa, required call korunur ve local/dev için güvenli relaxed fallback uygulanır.

## Doğrulama

- `backend/app/ml/topic_model.py` oluşturuldu.
- `backend/app/services/topic_service.py` oluşturuldu.
- `backend/app/routers/topics.py` oluşturuldu.
- LDA config `num_topics=20`, `passes=15`, `alpha="auto"`, `eta="auto"`.
- `Dictionary.filter_extremes(no_below=5, no_above=0.5)` uygulanır.
- `CoherenceModel(coherence="c_v")` hesaplanır.
- `GET /api/topics/trending` route’u aktif.
- `database.py` değişmedi.
