# MODÜL 3 — P14 Jinja2 Layout Generation / CSS Grid Newspaper

## Amaç

Kişisel haber akışını düz liste yerine dijital gazete düzeninde HTML olarak üretir. Üretilen HTML, Modül 4 PDF dönüşümü için print uyumlu CSS içerir.

## Genel Akış

1. `POST /api/newspaper/preview-html` isteği alınır.
2. `article_ids` geldiyse haberler aynı sırayla veritabanından okunur.
3. `article_ids` yoksa P12 kişisel feed servisi kullanılır.
4. Haber citation/source bilgileri hazırlanır.
5. `LayoutService.render_daily()` Jinja2 template'i render eder.
6. `articles[0]` manşet, `articles[1:4]` ikincil haberler, `articles[4:]` küçük haberler olur.
7. Etkinlikler ayrı kutuda gösterilir.
8. Response içinde `{ "html": "..." }` döner.

## Dosyalar

- `backend/templates/newspaper/daily.html`
- `backend/app/services/layout_service.py`
- `backend/app/routers/newspaper_layout.py`

## Endpoint

```bash
POST /api/newspaper/preview-html
```

Örnek body:

```json
{
  "user_id": "demo-user",
  "article_ids": [1, 2, 3, 4, 5],
  "date": "2026-06-21T06:00:00+03:00",
  "events": [
    {"title": "Konser", "date": "2026-06-21T20:00:00+03:00", "location": "İstanbul"}
  ]
}
```

## CSS Grid Kuralları

- `.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }`
- `.featured { grid-column: span 3; }`
- Manşet tam genişlikte render edilir.
- İkincil haberler 3 kolon halinde gösterilir.
- Küçük haberler kompakt kart olarak gösterilir.

## Print Uyumluluğu

- `@media print` içinde `column-count: 3` ve `column-gap: 20px` vardır.
- Kartlarda `break-inside: avoid` kullanılır.
- Görseller `max-width: 100%; height: auto;` ile taşma yapmaz.

## Custom Jinja2 Filterları

- `truncate_chars(n)` — uzun metni keser.
- `date_tr(datetime)` — `21 Haziran 2026` formatı üretir.
- `humanize_time(datetime)` — `3 saat önce` gibi Türkçe çıktı üretir.
- `safe_url(url)` — URL boşsa `#` döndürür.

## Kurulum

```bash
pip install jinja2 arrow
```

## Kontrol Listesi

- [ ] HTML içinde manşet tam genişlikte render ediliyor mu?
- [ ] 3 kolon grid bozulmadan çalışıyor mu?
- [ ] Boş haber listesinde empty state görünüyor mu?
- [ ] Türkçe tarih formatı çalışıyor mu?
- [ ] Citation/source alanları haber altında görünüyor mu?
- [ ] Print/PDF uyumlu CSS mevcut mu?
- [ ] `database.py` hiç değişmedi mi?
- [ ] `main.py` sadece router include için değişti mi?
