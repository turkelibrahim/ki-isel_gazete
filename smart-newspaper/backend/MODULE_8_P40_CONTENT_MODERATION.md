# Modül 8 / P40 — Two-Layer Content Moderation

Bu parça haber içerikleri, kullanıcı yorumları ve dış kaynak metinleri için iki katmanlı içerik moderasyonu ekler.

## Akış

1. `keyword_filter` önce metni hızlıca kontrol eder.
2. Blocked keyword varsa sonuç doğrudan `REJECTED` olur.
3. Keyword temizse lazy-load ML toxicity classifier çalıştırılır.
4. Model yoksa backend çökmez; `ml_available=false` ile keyword-only karar verilir.
5. Skor karar eşikleri uygulanır:
   - `score >= 0.95` → `REJECTED`
   - `0.70 <= score < 0.95` → `PENDING`
   - `score < 0.70` → `APPROVED`
6. `PENDING` ve `REJECTED` kayıtları `moderation_queue` içine yazılır.
7. `REJECTED` article mevcutsa `article.is_duplicate=True` yapılır, böylece feed/search tarafında görünmez.
8. Human review approve/reject işlemleri `reviewed_by`, `reviewed_at` alanlarını doldurur.
9. Review işlemleri `audit_log` içine yazılır.

## Endpointler

```bash
POST /api/moderation/check-text
GET  /api/moderation/queue
POST /api/moderation/{moderation_id}/approve
POST /api/moderation/{moderation_id}/reject
GET  /api/moderation/stats
```

## Kurulum

```bash
pip install transformers torch
```

## ML Model

```text
savasy/bert-base-turkish-sentiment-cased
```

Model lazy-load edilir. Dependency veya model yoksa sistem çökmez.

## Keyword Filter

Başlangıç placeholder listesi:

```python
[
  "hakaret_kelime_1",
  "tehdit_kelime_1",
  "nefret_kelime_1",
]
```

Gerçek prod ortamında bu liste policy/database/config tabanlı genişletilmelidir.

## Moderation Queue Uyumluluğu

Mevcut `moderation_queue` daha önce kategori/active-learning için kullanılıyordu. P40 bu tabloyu bozmaz; içerik moderasyonu için şu alanları ekleyen migration sağlar:

- `toxicity_score`
- `flagged_reason`
- `predicted_category_id` nullable

Kategori moderasyonu `confidence/reason/predicted_category_id` ile çalışmaya devam eder.

## Güvenlik

- Queue, stats, approve/reject ve check-text endpointleri `ADMIN` veya `EDITOR` rolü ister.
- `USER` moderation queue göremez.
- `database.py` değişmez.
- `main.py` sadece router import/include için değişmiştir.
