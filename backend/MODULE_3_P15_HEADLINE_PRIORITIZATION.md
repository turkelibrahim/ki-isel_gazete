# PROMPT 15 — Headline Prioritization / Temporal Decay

Bu bölüm, kişisel gazetenin manşet haberini seçmek için relevance, recency, popularity ve source trust skorlarını birleştirir.

## Amaç

- Eski ama çok popüler haberlerin sürekli manşette kalmasını engellemek.
- Yeni, alakalı, güvenilir ve popüler haberleri dengeli biçimde öne çıkarmak.
- Kullanıcı profili yoksa cold-start güvenli fallback kullanmak.

## Skor Bileşenleri

### 1. Temporal Decay

```text
recency = exp(-0.05 * hours_old)
```

Yaklaşık değerler:

| Yaş | Recency |
|---:|---:|
| 0 saat | 1.000 |
| 6 saat | 0.741 |
| 12 saat | 0.549 |
| 24 saat | 0.301 |
| 48 saat | 0.091 |

`published_at` yoksa fallback: `0.5`.

### 2. Popularity Normalization

```text
popularity = log10(1 + view_count)
pop_norm = popularity / max_popularity
```

Log dönüşümü çok yüksek view count değerlerinin sistemi domine etmesini engeller.

### 3. Relevance

- Kullanıcı profili varsa content-based relevance skoru kullanılır.
- Profil yoksa cold-start fallback: `0.5`.

### 4. Trust

- `source.trust_score` kullanılır.
- Yoksa fallback: `0.5`.

## Final Formül

```text
final = 0.40 * relevance + 0.30 * recency + 0.20 * pop_norm + 0.10 * trust
```

Sonuç `0-1` aralığında clamp edilir ve yüksekten düşüğe sıralanır. En yüksek skorlu haber `articles[0]` / manşet kabul edilir.

## Eklenen Dosyalar

- `backend/app/services/prioritization_service.py`
- `backend/app/routers/prioritization.py`

## Endpointler

```bash
POST /api/newspaper/rank-headlines
GET  /api/articles/top-headlines
```

### POST Body Örneği

```json
{
  "user_id": "demo-user",
  "article_ids": [1, 2, 3, 4],
  "language": "tr",
  "limit": 10
}
```

## Veritabanı Notu

- Yeni migration yapılmadı.
- `database.py` dosyasına dokunulmadı.
- `Article.priority_score` alanı yoksa skor runtime response içinde döndürülür.

## Kontrol Listesi

- [x] Yeni haber recency sayesinde öne çıkabilir.
- [x] Çok eski haber yüksek view count alsa bile temporal decay ile dengelenir.
- [x] Trust score final skora dahil edilir.
- [x] Kullanıcı profili yoksa relevance `0.5` fallback çalışır.
- [x] Manşet en yüksek skorlu haber olarak `items[0]` ve `headline` alanında döner.
- [x] `database.py` değiştirilmedi.
- [x] `main.py` sadece router import/include için güncellendi.
