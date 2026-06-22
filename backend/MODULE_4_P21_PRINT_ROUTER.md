# Modül 4 / P21 - Print Router / Preview / Download

## Amaç

Kullanıcının kişisel gazete edisyonunu HTML olarak önizleyebilmesi, PDF olarak üretebilmesi ve büyük PDF dosyalarını `StreamingResponse` ile güvenli şekilde indirebilmesi için print router eklenmiştir.

## Endpointler

```bash
GET  /api/print/templates
GET  /api/print/preview/{edition_id}?template=A4
POST /api/print/generate/{edition_id}?template=A4
GET  /api/print/download/{edition_id}?template=A4&mode=attachment
GET  /api/print/download/{edition_id}?template=A4&mode=inline
```

## Davranış

- `/api/print/templates`, `TemplateService.get_available_templates()` çıktısını döndürür.
- `/api/print/preview/{edition_id}`, PDF üretmeden `html_content` döndürür.
- `/api/print/generate/{edition_id}`, `PdfService.generate_pdf_for_edition()` ile PDF üretir ve `newspaper_editions.pdf_path` alanını günceller.
- `/api/print/download/{edition_id}`, mevcut PDF varsa onu stream eder; yoksa önce üretir, sonra indirir.
- `mode=attachment` indirme header'ı üretir.
- `mode=inline` tarayıcıda açma header'ı üretir.

## Güvenlik / Yetki

FastAPI auth altyapısı henüz bağlı olmadığı için router geçici olarak `user_id` query parametresini destekler.

- `user_id` edition sahibiyse erişim verilir.
- `users.role = ADMIN` ise tüm edisyonlara erişim verilir.
- Farklı kullanıcı ise `403` döner.
- Auth bağlandığında TODO comment içindeki helper `current_user` dependency ile değiştirilebilir.

## Hata Yönetimi

- Edisyon yoksa `404`.
- `html_content` boşsa `400`.
- PDF üretilemezse kontrollü `500`.
- Tüm beklenmeyen hatalar `logger.exception` ile loglanır.

## Dosyalar

- `backend/app/routers/print_router.py`
- `backend/app/services/preview_service.py`

## Değişmeyenler

- `database.py` değişmedi.
- `main.py` sadece router import/include için değişti.
- Frontend UI/CSS/HTML tarafına dokunulmadı.


## Modül 4 Toplu Kontrol Listesi

Toplu kurulum, endpoint özeti ve doğrulama maddeleri için:

- `backend/MODULE_4_SETUP_AND_CHECKLIST.md`
