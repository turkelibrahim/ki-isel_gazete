# Modül 6 / Prompt 28 — Advanced Filters / BM25 + SQL Hybrid Search

Bu doküman BM25 arama skorlarını SQL filtreleriyle birleştiren gelişmiş haber arama sistemini özetler.

## Amaç

Kullanıcı aynı anda keyword araması, kategori, kaynak, tarih, dil, bookmark ve sıralama filtresi kullanabilir. Arama varsa BM25 skoru devreye girer; arama yoksa klasik SQL filtreleme çalışır.

## Eklenen Dosyalar

- `backend/app/schemas/search_filters.py`
- `backend/app/services/advanced_search_service.py`
- `backend/app/routers/advanced_search.py`
- `backend/sql/search_filter_indexes.sql`

## Endpoint

```bash
GET /api/search/advanced?q=merkez+bankası&category_ids=1,2&source_ids=3&language=tr&sort_by=relevance&page=1&page_size=20
```

Tekrarlı query parametreleri de desteklenir:

```bash
GET /api/search/advanced?category_ids=1&category_ids=2&source_ids=3&source_ids=4
```

## Filtre Parametreleri

- `q`: BM25 keyword query. Boşsa SQL-only filtreleme yapılır.
- `category_ids`: çoklu kategori filtresi.
- `source_ids`: çoklu kaynak filtresi.
- `date_from`: başlangıç tarihi.
- `date_to`: bitiş tarihi.
- `language`: dil filtresi.
- `only_bookmarked`: sadece kullanıcının bookmark ettiği haberler.
- `user_id`: `only_bookmarked=true` için zorunlu.
- `sort_by`: `relevance`, `date`, `popularity`, `trend`.
- `page`: minimum 1.
- `page_size`: maksimum 100.

## Hibrit Arama Mantığı

1. `q` varsa `BM25Engine.search(q, top_n=200)` çağrılır.
2. BM25 sonuçlarından `article_id` listesi alınır.
3. SQL query içine `Article.id.in_(bm25_ids)` filtresi eklenir.
4. Kategori, kaynak, tarih, dil ve bookmark filtreleri SQL tarafında uygulanır.
5. `sort_by=relevance` ise kalan sonuçlar BM25 skor sırasına göre sıralanır.
6. `q` yoksa sadece SQL filtreleri çalışır.

## Sort Mantığı

- `relevance`: q varsa BM25 skoru, q yoksa `published_at DESC` fallback.
- `date`: `published_at DESC`.
- `popularity`: `view_count DESC`.
- `trend`: runtime trend skoru.

Trend skoru:

```text
trend_score = view_count × e^(-0.05 × hours_since_published)
```

## Bookmark Filtresi

`only_bookmarked=true` için `user_id` zorunludur. Auth sistemi bağlandığında bu parametre `current_user` ile değiştirilebilir.

`user_bookmarks` için migration bu prompt kapsamında yapılmadı; sadece performans index SQL script’i eklendi.

## Performance Index Script

`backend/sql/search_filter_indexes.sql` manuel çalıştırılabilir:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_search_filter
ON articles(published_at DESC, source_id, language, view_count DESC)
WHERE is_duplicate = FALSE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_article_categories_filter
ON article_categories(category_id, article_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_bookmarks_filter
ON user_bookmarks(user_id, article_id);
```

## Response Format

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "has_next": false,
  "filters_applied": {
    "q": "merkez bankası",
    "category_ids": [1, 2],
    "source_ids": [3],
    "language": "tr",
    "sort_by": "relevance",
    "exclude_duplicates": true,
    "bm25_top_n": 200
  }
}
```

## Kontrol Listesi

- [x] `q` varsa BM25 top 200 ID alınır.
- [x] `q + category` filtresi birlikte çalışacak şekilde SQL query kurulur.
- [x] `q` yoksa SQL-only filtreleme yapılır.
- [x] `source_ids` çoklu filtre desteklenir.
- [x] `date_from/date_to` desteklenir.
- [x] `only_bookmarked=True` için user bookmark join yapılır.
- [x] `sort_by=relevance` BM25 sırasını korur.
- [x] `sort_by=trend` runtime trend skoru üretir.
- [x] Pagination doğru `offset/page_size` mantığıyla yapılır.
- [x] Duplicate haberler varsayılan filtrelenir.
- [x] `database.py` değişmedi.
- [x] `main.py` sadece advanced search router import/include için değişti.
