# Modül 8 / P38 — Reporting System / Matplotlib PDF + CSV Export

Bu paket, analytics verilerinden admin indirilebilir PDF ve CSV raporları üretir.

## Kurulum

```bash
pip install matplotlib pandas
```

## Eklenen Dosyalar

- `backend/app/services/report_service.py`
- `backend/app/routers/reports.py`
- `backend/storage/reports/.gitkeep`

## Endpointler

```http
POST   /api/reports/generate?days=30&format=pdf
POST   /api/reports/generate?days=30&format=csv
GET    /api/reports/download?path=report_20260621T120000Z.pdf
GET    /api/reports/list
DELETE /api/reports/cleanup?days=30
```

Tüm endpointler geçici ADMIN guard kullanır. Prompt 39 JWT/RBAC tamamlanınca `require_role("ADMIN")` bağımlılığına bağlanacaktır.

Örnek:

```bash
curl -X POST -H "X-User-Role: ADMIN" \
  "http://localhost:8000/api/reports/generate?days=30&format=pdf"
```

## ReportService

`ReportService` şu metodları sağlar:

- `generate_overview_report(db, days=30, format="pdf")`
- `generate_pdf_report(data, output_path)`
- `generate_csv_report(data, output_path)`
- `build_report_data(db, days=30)`
- `cleanup_old_reports(days=30)`
- `list_reports()`

## Rapor Datası

Rapor datası `AnalyticsService` üzerinden toplanır:

- `overview`
- `daily_active_users`
- `top_articles`
- `category_reads`
- `source_performance`
- `moderation_summary`

Analytics tarafında hata olursa rapor servisi kontrollü `partial` veri dönebilir; uygulama import aşamasında çökmez.

## PDF Rapor

PDF üretimi `matplotlib.backends.backend_pdf.PdfPages` ile yapılır.

Sayfalar:

1. Overview text summary
2. DAU line chart
3. Category reads bar chart
4. Top articles table
5. Source performance table

Büyük tablolar ilk 20 satırla sınırlandırılır.

Dosya yolu:

```text
backend/storage/reports/report_{timestamp}.pdf
```

## CSV Export

CSV export tek dosya olarak üretilir:

```text
backend/storage/reports/report_{timestamp}.csv
```

Sütunlar:

- `metric_type`
- `key`
- `value`
- `date`

Türkçe karakterler için `encoding="utf-8-sig"` kullanılır.

## Güvenli Download

`/api/reports/download` path traversal koruması içerir:

- Sadece `backend/storage/reports/` altındaki `.pdf` ve `.csv` dosyaları indirilebilir.
- `../` içeren path reddedilir.
- Root dışındaki absolute path reddedilir.

## Cleanup

`DELETE /api/reports/cleanup?days=30` 30 günden eski `report_*.pdf` ve `report_*.csv` dosyalarını siler.

## Doğrulama

- `POST /api/reports/generate?format=pdf` PDF rapor üretir.
- `POST /api/reports/generate?format=csv` CSV rapor üretir.
- Raporlar `backend/storage/reports/` altında tutulur.
- Download endpoint path traversal denemelerini reddeder.
- Cleanup eski raporları silebilir.
- `database.py` değiştirilmez.
- `main.py` sadece reports router import/include için değişir.
