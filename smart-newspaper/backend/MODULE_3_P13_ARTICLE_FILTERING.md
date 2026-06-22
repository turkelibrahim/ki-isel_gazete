# PROMPT 13 — Article Filtering / Composite Index + SQL

## Genel Amaç
Tarih, kategori, kaynak, dil, popülerlik ve relevance filtreleriyle çalışan makale listeleme API’si eklendi.
Bu API kişisel gazete oluşturma akışında haber havuzunu hızlı ve kontrollü şekilde daraltır.

## Sistem Akışı
1. API query parametreleri `FilterParams` ile doğrulanır.
2. Base query `articles.is_duplicate = FALSE` filtresiyle başlar.
3. Parametre geldikçe SQLAlchemy sorgusuna dinamik `WHERE` ve gerektiğinde `JOIN` eklenir.
4. `category_id` varsa `article_categories` tablosu join edilir.
5. `source_ids`, `date_from`, `date_to`, `language` filtreleri uygulanır.
6. `sort_by` değerine göre sıralama yapılır.
7. `page/page_size` ile offset-limit pagination uygulanır.
8. Response içinde `items`, `total`, `has_next` ve `filters_applied` döner.

## Endpoint
```bash
GET /api/articles
```

Örnek:
```bash
/api/articles?category_id=1&source_ids=2,3&date_from=2026-06-01&sort_by=popularity&page=1&page_size=20
```

## Kurulum / SQL Index
Migration yapılmadı. PostgreSQL index script’i ayrı dosyada tutuldu:

```bash
psql "$DATABASE_URL" -f backend/sql/performance_indexes.sql
```

## Dosyalar
- `backend/sql/performance_indexes.sql`
- `backend/app/schemas/article_filters.py`
- `backend/app/services/article_filter_service.py`
- `backend/app/routers/articles_filter.py`

## Kontrol Listesi
- [ ] `category_id` filtresi çalışıyor mu?
- [ ] `source_ids` çoklu filtre çalışıyor mu?
- [ ] `date_from/date_to` çalışıyor mu?
- [ ] `sort_by=popularity` `view_count DESC` sıralıyor mu?
- [ ] `page/page_size` düzgün offset üretiyor mu?
- [ ] Duplicate haberler varsayılan listelenmiyor mu?
- [ ] `database.py` hiç değişmedi mi?
- [ ] `main.py` sadece router import/include için değişti mi?
