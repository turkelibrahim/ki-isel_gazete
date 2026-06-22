# MODÜL 3 / P17 — Personal Newspaper Edition Pipeline

## Amaç

Kullanıcının kişisel haber akışını alıp filtreleyen, manşet sıralaması yapan, citation bilgilerini ekleyen, Jinja2 gazete HTML layout üreten ve sonucu `newspaper_editions` tablosuna kaydeden uçtan uca edisyon üretim hattıdır. PDF üretimi bu modülde yapılmaz; `html_content` Modül 4 PDF export için hazır tutulur.

## Genel Akış

1. Kullanıcı `users` tablosundan okunur.
2. `language_preference` belirlenir.
3. `RecommendationService.get_personalized_feed()` ile kişisel haber adayları alınır.
4. Filtre varsa `ArticleFilterService` çalışır ve kategori/tarih/kaynak/dil filtreleri uygulanır.
5. `PrioritizationService.rank()` ile manşet ve haber sırası belirlenir.
6. Yaklaşan `events` kayıtları alınır.
7. `CitationService` her haber için kaynak/citation bilgisini üretir.
8. `LayoutService.render_daily()` ile PDF-ready HTML üretilir.
9. Aynı kullanıcı + aynı gün + daily için mevcut edisyon varsa güncellenir, yoksa yeni kayıt açılır.
10. `newspaper_editions.html_content` Modül 4 PDF dönüşümü için hazır kalır.

## Endpointler

```bash
POST   /api/newspaper/editions/generate
GET    /api/newspaper/editions/me?user_id=<USER_ID>
GET    /api/newspaper/editions/{edition_id}
DELETE /api/newspaper/editions/{edition_id}
```

## POST Body

```json
{
  "user_id": 1,
  "filters": {
    "category_id": 2,
    "date_from": "2026-06-01T00:00:00+03:00",
    "source_ids": [1, 2],
    "language": "tr",
    "sort_by": "popularity"
  }
}
```

## Celery Beat

Her sabah 07:00 Europe/Istanbul saatine göre tüm kullanıcılar için günlük edisyon üretir:

```python
crontab(hour=7, minute=0)
```

Task adı:

```bash
app.tasks.edition_tasks.generate_daily_editions
```

Kullanıcı bazlı hata olursa loglanır, diğer kullanıcılar için üretim devam eder.

## DB Notları

`database.py` değişmedi. P17 için migration dosyası eklendi:

```bash
backend/migrations/20260621_add_edition_pipeline.sql
```

Eklenen/güncellenen alanlar:

- `newspaper_editions.edition_date`
- `newspaper_editions.frequency`
- `newspaper_editions.pdf_path`
- `newspaper_editions.updated_at`
- `events` tablosu

Aynı gün aynı kullanıcı için duplicate edisyon engeli:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_newspaper_daily_edition
ON newspaper_editions(user_id, edition_date, frequency);
```

## Doğrulama

- `POST /api/newspaper/editions/generate` çalışır.
- `newspaper_editions.html_content` kaydedilir.
- Aynı gün aynı kullanıcı için edisyon güncellenir.
- HTML preview `GET /api/newspaper/editions/{edition_id}` ile alınır.
- Celery task kullanıcı bazlı hatada devam eder.
- `database.py` değişmedi.
- `main.py` sadece router include için değişti.
