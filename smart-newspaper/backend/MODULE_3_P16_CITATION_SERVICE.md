# PROMPT 16 — Citation Service for Personal Newspaper

## Amaç

Kişisel gazete HTML layout içinde her haber için kaynak/citation bilgisi üretir. Kullanıcı her haberin kaynağını, yayın zamanını ve güven seviyesini görebilir.

## Eklenen Dosyalar

- `backend/app/services/citation_service.py`
- `backend/app/routers/newspaper_citations.py`

## Güncellenen Dosyalar

- `backend/app/services/layout_service.py`
- `backend/templates/newspaper/daily.html`
- `backend/app/routers/newspaper_layout.py`
- `backend/app/main.py`

## Citation Alanları

Her haber için üretilen bilgi:

```json
{
  "article_id": 1,
  "source_name": "Anadolu Ajansı",
  "source_url": "https://www.aa.com.tr",
  "article_url": "https://...",
  "published_at": "2026-06-21T10:00:00+03:00",
  "published_human": "3 saat önce",
  "trust_score": 0.82,
  "trust_badge": "güvenilir",
  "citation_text": "Anadolu Ajansı · 3 saat önce · Güven: güvenilir"
}
```

## Trust Badge

- `trust_score >= 0.8` → `güvenilir`
- `trust_score >= 0.5` → `orta`
- `trust_score < 0.5` → `düşük`
- Source yoksa → `trust_score=0.5`, `trust_badge=orta`

## Endpointler

```bash
GET  /api/newspaper/articles/{article_id}/citation
POST /api/newspaper/citations/batch
```

Batch body örneği:

```json
{
  "article_ids": [1, 2, 3]
}
```

## LayoutService Entegrasyonu

`LayoutService.render_daily()` içine citation verilmezse otomatik olarak `CitationService().build_citations(articles)` çalışır. Template içinde haberlerin altında `citation_text` gösterilir.

## Doğrulama

- Her haberin altında kaynak adı görünür.
- `published_at` varsa Türkçe humanize tarih üretilir.
- `trust_score` doğru badge’e çevrilir.
- `database.py` değiştirilmedi.
