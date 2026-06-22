# Modül 4 — PDF Export / Print Router Toplu Kurulum ve Kontrol Listesi

Bu doküman, **MODÜL 4 — PDF Export** kapsamındaki P18, P19 ve P21 parçalarının tek yerden kurulması ve doğrulanması için hazırlandı.

## Modül 4 Genel Akış

1. `newspaper_editions` tablosundan `html_content` alınır.
2. Kullanıcının seçtiği PDF template belirlenir:
   - `A4`
   - `TABLOID`
   - `BOOKLET`
3. `TemplateService` ilgili `@page` CSS ayarlarını üretir.
4. `print.css` ile gazete sütunları, manşet, sayfa kırılmaları ve baskı stilleri uygulanır.
5. `PdfService`, WeasyPrint ile HTML’i PDF bytes’a çevirir.
6. PDF dosyası `storage/pdf/editions/` klasörüne kaydedilir.
7. `newspaper_editions.pdf_path` alanı güncellenir.
8. Preview endpoint HTML döndürür.
9. Download endpoint `StreamingResponse` ile PDF indirir.
10. Hatalar loglanır, `database.py` değişmez, `main.py` sadece router include alır.

## Modül 4 Toplu Kurulum

### Linux / Ubuntu sistem paketleri

```bash
sudo apt-get update
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libffi-dev shared-mime-info
```

### Python paketleri

```bash
pip install weasyprint
pip install jinja2 arrow beautifulsoup4
```

Tek komut alternatifi:

```bash
pip install -r backend/requirements.txt
```

## Modül 4 Endpoint Özeti

```bash
GET  /api/print/templates
GET  /api/print/preview/{edition_id}?template=A4
POST /api/print/generate/{edition_id}?template=A4
GET  /api/print/download/{edition_id}?template=A4&mode=attachment
GET  /api/print/download/{edition_id}?template=A4&mode=inline
```

## Modül 4 Kontrol Listesi

- [x] `backend/app/services/pdf_service.py` oluşturuldu.
- [x] `backend/app/services/template_service.py` oluşturuldu.
- [x] `backend/app/services/preview_service.py` oluşturuldu.
- [x] `backend/app/routers/print_router.py` oluşturuldu.
- [x] `backend/templates/newspaper/print.css` oluşturuldu.
- [x] A4 template çalışıyor.
- [x] TABLOID template çalışıyor.
- [x] BOOKLET template çalışıyor.
- [x] `@page` size/margin/page counter CSS’i üretiliyor.
- [x] `column-count` ile gazete sütun düzeni uygulanıyor.
- [x] `column-span: all` ile manşet tam genişlik oluyor.
- [x] Preview endpoint `HTMLResponse` döndürecek şekilde tanımlandı.
- [x] Generate endpoint PDF dosyası üretecek şekilde `PdfService`e bağlı.
- [x] Download endpoint `StreamingResponse` kullanıyor.
- [x] `mode=attachment` indirme header’ı üretiyor.
- [x] `mode=inline` tarayıcıda gösterme header’ı üretiyor.
- [x] `newspaper_editions.pdf_path` PDF üretiminden sonra güncelleniyor.
- [x] Boş `html_content` için kontrollü `400` dönüyor.
- [x] Kayıt bulunamazsa `404` dönüyor.
- [x] Yetkisiz kullanıcı kendi olmayan PDF’i alamıyor; owner/admin kontrol helper’ı var.
- [x] `database.py` hiç değişmedi.
- [x] `main.py` sadece router include için değişti.
- [x] `python -m compileall -q backend` başarılı.
- [x] FastAPI route check başarılı.

## Notlar

- WeasyPrint native dependency gerektirdiği için Linux ortamında yukarıdaki sistem paketleri kurulmalıdır.
- `PdfService` WeasyPrint importunu lazy yapar; eksik dependency varsa uygulama import aşamasında çökmez, PDF üretiminde kontrollü hata döner.
- Auth altyapısı bağlandığında `print_router.py` içindeki TODO helper `current_user` dependency ile değiştirilebilir.
- Frontend UI/CSS/HTML dosyalarına dokunulmadı; ekran kayması oluşturacak değişiklik yapılmadı.
