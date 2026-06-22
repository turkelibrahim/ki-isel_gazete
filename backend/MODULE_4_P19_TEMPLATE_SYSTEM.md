# Modül 4 / P19 — PDF Template System

Bu modül kişisel gazete PDF çıktısı için üç farklı baskı şablonu sağlar:

- `A4`: standart dikey A4 çıktı, 3 kolon, 10pt font.
- `TABLOID`: geniş yatay gazete formatı, 4 kolon, 9pt font.
- `BOOKLET`: A5 kitapçık formatı, 2 kolon, 9pt font.

## Dosyalar

- `backend/app/services/template_service.py`
- `backend/templates/newspaper/print.css`
- `backend/app/services/pdf_service.py`

## TemplateService

`TemplateService` şu metodları sağlar:

- `get_available_templates() -> list[dict]`
- `get_template_css(template: str) -> str`
- `validate_template(template: str) -> str`
- `get_template_metadata(template: str) -> dict`

Geçersiz template değeri geldiğinde hata fırlatılmaz; güvenli varsayılan olarak `A4` kullanılır ve warning log yazılır.

## Desteklenen şablonlar

| Template | Size | Margin | Columns | Font |
|---|---|---:|---:|---:|
| A4 | A4 portrait | 1.5cm | 3 | 10pt |
| TABLOID | 279mm 432mm landscape | 1.2cm | 4 | 9pt |
| BOOKLET | A5 portrait | 1cm | 2 | 9pt |

## PdfService entegrasyonu

`PdfService.generate_pdf_bytes()` artık template CSS'i şu şekilde alır:

```python
TemplateService().get_template_css(template)
```

WeasyPrint stylesheets sırası:

1. `backend/templates/newspaper/print.css`
2. Template-specific CSS string

Bu sayede genel baskı stilleri korunur, sayfa boyutu/kolon/font ayarları seçilen template'e göre uygulanır.

## Doğrulama

- A4 template CSS üretir.
- TABLOID template CSS üretir.
- BOOKLET template CSS üretir.
- Geçersiz template `A4` fallback kullanır.
- `print.css` içinde `break-inside: avoid` vardır.
- `database.py` değişmez.
- `main.py` değişmez.
