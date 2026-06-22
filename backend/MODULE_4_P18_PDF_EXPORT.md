# Modül 4 — P18 PDF Export With WeasyPrint

## Genel Akış

1. `newspaper_editions` tablosundan `html_content` alınır.
2. Kullanıcının seçtiği PDF template belirlenir: `A4`, `TABLOID`, `BOOKLET`.
3. `TemplateService` ilgili `@page` CSS ayarlarını üretir.
4. `print.css` ile gazete sütunları, manşet, sayfa kırılmaları ve baskı stilleri uygulanır.
5. `PdfService`, WeasyPrint ile HTML'i PDF bytes'a çevirir.
6. PDF dosyası `backend/storage/pdf/editions/` klasörüne kaydedilir.
7. `newspaper_editions.pdf_path` alanı güncellenir.
8. Preview/download endpointleri sonraki promptlarda router üzerinden bağlanacaktır.
9. Hatalar loglanır, kontrollü `HTTPException` döner.
10. `database.py` değişmez; P18 kapsamında `main.py` de değiştirilmez.

## Eklenen Dosyalar

- `backend/app/services/pdf_service.py`
- `backend/templates/newspaper/print.css`
- `backend/storage/pdf/editions/.gitkeep`

## PdfService Metodları

- `generate_pdf_bytes(html_content: str, template: str = "A4") -> bytes`
- `save_pdf_file(pdf_bytes: bytes, edition_id: int, template: str = "A4") -> str`
- `generate_pdf_for_edition(db, edition_id: int, template: str = "A4") -> dict`

## Template Desteği

- `A4`: `@page size: A4 portrait`, 3 sütun
- `TABLOID`: `@page size: 11in 17in portrait`, 4 sütun
- `BOOKLET`: `@page size: A5 portrait`, 2 sütun

## Kurulum

Linux sistem bağımlılıkları:

```bash
apt-get install libpango-1.0-0 libpangoft2-1.0-0
```

Python bağımlılığı:

```bash
pip install weasyprint
```

veya:

```bash
pip install -r backend/requirements.txt
```

## Doğrulama

- `html_content` PDF bytes'a çevrilebilir.
- PDF dosyası `backend/storage/pdf/editions/` içine kaydedilir.
- `newspaper_editions.pdf_path` güncellenir.
- Boş `html_content` için sistem çökmez, 400 döner.
- `database.py` değişmez.
- P18 router eklemez; bu yüzden `main.py` değişmez.


## P19 — PDF Template System Güncellemesi

PDF template üretimi `backend/app/services/template_service.py` dosyasına ayrıldı. `PdfService` A4, TABLOID ve BOOKLET şablonları için template-specific CSS'i bu servisten alır.
