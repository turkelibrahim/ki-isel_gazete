# Modül 5 — Events & Reminders

## Genel Akış

1. Haber veya duyuru metni sisteme gelir.
2. `EventDetector` metni cümlelere böler.
3. spaCy NER ile `DATE` entity aranır.
4. Regex ile tarih/saat formatları aranır.
5. `EVENT_KW` keyword listesiyle etkinlik kelimeleri aranır.
6. Hem tarih hem etkinlik keyword varsa event candidate oluşur.
7. `EventCategoryClassifier` keyword puan sistemiyle kategori belirler.
8. `EventService` events tablosuna kayıt açar.
9. `remind_at = event_date - 24 saat` olarak hesaplanır.
10. Celery reminder task her 15 dakikada yaklaşan etkinlikleri tarar.
11. `remind_at` zamanı gelen ve `is_notified=False` olan etkinlikler bulunur.
12. `PushService` FCM ile bildirim gönderir.
13. `EmailService` SMTP ile e-posta gönderir.
14. Gönderim başarılıysa `is_notified=True` yapılır.
15. `EditionPipeline` önümüzdeki 7 günün etkinliklerini kişisel gazeteye ekler.

## P22 — Event Detection / NER + Regex

### Eklenen dosya

- `backend/app/ml/event_detector.py`

### Desteklenen sinyaller

- spaCy NER `DATE` entity
- Regex tarih/saat formatları
- Turkish relative date fallback: `bugün`, `yarın`, `cuma günü`
- Türkçe gün-ay ifadeleri: `21 Haziran`, `21 Haziran’da`, `21 Haziran 2026`
- Event keyword eşleşmesi

### Event candidate kuralı

Bir cümle ancak şu iki sinyali birlikte taşıyorsa event kabul edilir:

- En az bir tarih/saat sinyali
- En az bir etkinlik keyword'ü

Sadece tarih geçen veya sadece keyword geçen cümleler event olarak dönmez.

### Confidence kuralı

- Tek keyword + tarih: `0.65`
- Birden fazla keyword + tarih: `0.85`
- NER DATE + regex date birlikte varsa: `+0.05`
- Maksimum confidence: `0.95`

## P23 — Event Categorization / Keyword Score

### Eklenen dosya

- `backend/app/ml/event_category_classifier.py`

### Kategoriler

- `EXAM`: sınav, vize, final, quiz, test, değerlendirme
- `DEADLINE`: son başvuru, deadline, son tarih, teslim, başvuru bitiş
- `ACADEMIC`: seminer, konferans, webinar, eğitim, atölye, panel
- `MEETING`: toplantı, görüşme, kurul, oturum, randevu
- `SOCIAL`: konser, festival, tören, gezi, sosyal, etkinlik
- `OTHER`: fallback

### Keyword puan sistemi

- Text küçük harfe çevrilir.
- Her kategori için eşleşen keyword başına `+1` puan verilir.
- En yüksek puanlı kategori seçilir.
- Hiç eşleşme yoksa `OTHER` döner.

### Eşitlik önceliği

Eşitlik durumunda şu sabit sıra korunur:

`EXAM > DEADLINE > ACADEMIC > MEETING > SOCIAL > OTHER`

### EventDetector entegrasyonu

`EventDetector.detect_events()` çıktısı artık şu alanları da döndürür:

- `category`
- `category_score`
- `matched_category_keywords`
- `category_scores`

## Kurulum

```bash
pip install spacy dateparser python-dateutil
python -m spacy download xx_ent_wiki_sm
```

Türkçe model mevcutsa tercih edilir:

```bash
python -m spacy download tr_core_news_sm
```

Model yoksa sistem regex-only fallback ile çalışır ve çökmez.

## Kontrol Listesi

- [x] `backend/app/ml/event_detector.py` oluşturuldu.
- [x] `backend/app/ml/event_category_classifier.py` oluşturuldu.
- [x] spaCy Türkçe model deneniyor.
- [x] `xx_ent_wiki_sm` fallback deneniyor.
- [x] Model yoksa regex-only mode çalışıyor.
- [x] Tarih + etkinlik keyword olan cümle event dönüyor.
- [x] Sadece tarih geçen cümle event dönmüyor.
- [x] Sadece keyword geçen cümle event dönmüyor.
- [x] Confidence `0.65` / `0.85` mantığı uygulanıyor.
- [x] `final sınavı 21 Haziran’da` metni `EXAM` kategorisi alıyor.
- [x] `son başvuru tarihi yarın` metni `DEADLINE` kategorisi alıyor.
- [x] `webinar ve seminer yapılacak` metni `ACADEMIC` kategorisi alıyor.
- [x] Eşitlikte öncelik sırası uygulanıyor.
- [x] `EventDetector` çıktısına `category` alanı eklendi.
- [x] Her cümle `try/except` ile izole ediliyor.
- [x] `database.py` değişmedi.
- [x] `main.py` değişmedi; P22/P23 router istemiyor.

## P24 — Event Service + CRUD API

### Eklenen dosyalar

- `backend/app/services/event_service.py`
- `backend/app/schemas/events.py`
- `backend/app/routers/events.py`
- `backend/migrations/20260621_add_event_service_columns.sql`

### Endpointler

```bash
GET    /api/events
GET    /api/events/upcoming?days=7
POST   /api/events
POST   /api/events/detect-from-text
PATCH  /api/events/{event_id}
DELETE /api/events/{event_id}
```

### Davranış

- Manuel event oluştururken `title` ve `event_date` zorunludur.
- `category` verilmezse `EventCategoryClassifier` otomatik kategori belirler.
- `remind_at` verilmezse `event_date - 24 saat` olarak hesaplanır.
- Etkinlik 24 saatten yakınsa `remind_at = now()` olur.
- Geçmiş tarihli event oluşturulmaz ve kontrollü `400` döner.
- Aynı `title + event_date` aktif event tekrar eklenmez.
- `delete_event` veri kaybını azaltmak için soft delete uygular: `is_active=False`.
- `POST /api/events/detect-from-text` sadece `confidence >= 0.65` adayları kaydeder.

### P24 Kontrol Listesi

- [x] `EventService` oluşturuldu.
- [x] `EventCreate`, `EventUpdate`, `EventResponse`, `EventDetectionRequest`, `EventDetectionResponse` şemaları eklendi.
- [x] `/api/events` CRUD router eklendi.
- [x] `remind_at = event_date - 24 saat` mantığı eklendi.
- [x] 24 saatten yakın eventlerde `remind_at = now()` fallback çalışıyor.
- [x] Geçmiş event kontrollü şekilde reddediliyor.
- [x] Duplicate kontrolü `title + event_date` ile yapılıyor.
- [x] `EventDetector.detect_events()` çıktıları DB kayıt akışına bağlandı.
- [x] `confidence < 0.65` event adayları kaydedilmiyor.
- [x] `events.is_notified` alanı model ve migration içinde eklendi.
- [x] `database.py` değişmedi.
- [x] `main.py` sadece events router import/include için değişti.

## P25 — Push + Email Notification Services

### Eklenen dosyalar

- `backend/app/services/push_service.py`
- `backend/app/services/email_service.py`

### Push Service

`PushService` Firebase Cloud Messaging legacy HTTP API üzerinden push bildirim gönderir.

- Endpoint: `https://fcm.googleapis.com/fcm/send`
- Header: `Authorization: key={FCM_SERVER_KEY}`
- Token yoksa veya `FCM_SERVER_KEY` boşsa sistem çökmez, warning loglar ve push kanalını atlar.
- `send_event_reminder_push(user, event)` standart mesaj üretir:
  - Başlık: `Etkinlik Hatırlatması`
  - Gövde: `{event.title} etkinliği yaklaşıyor.`

### Email Service

`EmailService` SMTP SSL ile HTML email gönderir.

Env değişkenleri:

```bash
FCM_SERVER_KEY=
SMTP_HOST=
SMTP_PORT=465
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
```

- `smtplib.SMTP_SSL(host, 465)` kullanılır.
- `MIMEMultipart("alternative")` ile HTML mail oluşturulur.
- SMTP bilgileri eksikse sistem çökmez, warning loglar ve email kanalını atlar.
- Push ve email kanalları bağımsızdır; biri hata verirse diğeri çalışmaya devam eder.

### P25 Kontrol Listesi

- [x] `PushService` oluşturuldu.
- [x] `EmailService` oluşturuldu.
- [x] `FCM_SERVER_KEY` env üzerinden okunuyor.
- [x] FCM token yoksa sistem çökmeden push atlanıyor.
- [x] SMTP bilgileri yoksa sistem çökmeden email atlanıyor.
- [x] Push ve email ayrı `try/except` hata yönetimine sahip.
- [x] Event reminder push title/body standardı uygulandı.
- [x] Event reminder HTML email body üretildi.
- [x] `.env.example` içine FCM/SMTP değişkenleri eklendi.
- [x] `database.py` değişmedi.
- [x] `main.py` değişmedi; P25 router istemiyor.

## P26 — Reminder Polling + Newspaper Integration

### Eklenen dosya

- `backend/app/tasks/reminder_task.py`

### Güncellenen dosyalar

- `backend/celeryconfig.py`
- `backend/app/tasks/__init__.py`
- `backend/app/services/edition_pipeline_service.py`
- `backend/templates/newspaper/daily.html`
- `backend/app/routers/events.py`

### Reminder polling mantığı

- `setTimeout` veya memory tabanlı timer kullanılmaz.
- Celery Beat her 15 dakikada DB sorgular.
- Task adı: `app.tasks.reminder_task.send_event_reminders`
- Schedule: `crontab(minute="*/15")`
- Task retry: `max_retries=3`, `default_retry_delay=60`
- Due reminder sorgusu `remind_at <= now + 15 dakika`, `event_date >= now`, `is_notified=False` ve `is_active=True` filtresini kullanır.
- `remind_at <= now + 15 dakika` seçimi restart sırasında kaçırılmış ama etkinlik tarihi geçmemiş hatırlatmaları da tekrar yakalar.

### Bildirim mantığı

- Kullanıcıya özel eventlerde yalnızca `event.user_id` sahibi hedeflenir.
- Global eventlerde MVP davranışı olarak tüm kullanıcılar hedeflenir.
- `PushService` kullanıcının `fcm_token` değeri varsa push göndermeyi dener.
- `EmailService` kullanıcının `email` değeri varsa HTML email göndermeyi dener.
- Push veya email kanallarından en az biri başarılıysa `event.is_notified=True` yapılır.
- Hiçbir kanal başarılı değilse event pending kalır ve sonraki polling çalışmasında tekrar denenebilir.
- Event bazlı hata diğer eventleri durdurmaz.

### Gazete entegrasyonu

- `EditionPipelineService` artık etkinlikleri `EventService().get_upcoming_events(db, days=7)` ile alır.
- Kullanıcıya özel ve global eventler kişisel gazete HTML layout’una gönderilir.
- `daily.html` etkinlik kutusunda tarih, konum, kategori ve açıklama render eder.
- PDF sistemi `html_content` üzerinden çalıştığı için etkinlikler PDF’e otomatik dahil olur.

### Test endpoint’i

```bash
POST /api/events/reminders/run-now
```

Bu endpoint polling logic’ini manuel çalıştırır. Production ortamında ADMIN auth dependency bağlanması için TODO notu bırakılmıştır.

### P26 Kontrol Listesi

- [x] `backend/app/tasks/reminder_task.py` oluşturuldu.
- [x] Celery Beat içinde `send-event-reminders-every-15-minutes` schedule eklendi.
- [x] `send_event_reminders` task `max_retries=3`, `default_retry_delay=60` ile tanımlandı.
- [x] `remind_at` zamanı gelen ve `is_notified=False` eventler DB’den bulunuyor.
- [x] Event bazlı hata diğer eventleri durdurmuyor.
- [x] Push ve email kanalları ayrı ayrı deneniyor.
- [x] En az bir kanal başarılıysa `is_notified=True` yapılacak şekilde akış kuruldu.
- [x] Restart senaryosu için reminder DB polling mantığı kullanılıyor.
- [x] Önümüzdeki 7 günün etkinlikleri kişisel gazete HTML’ine ekleniyor.
- [x] PDF export HTML üzerinden çalıştığı için etkinlikleri otomatik içerecek.
- [x] `POST /api/events/reminders/run-now` manuel test endpoint’i eklendi.
- [x] `database.py` değişmedi.
- [x] `main.py` bu adımda değişmedi; events router zaten P24’te eklenmişti.
## Modül 5 Toplu Kurulum ve Complete Kontrol Listesi

Detaylı toplu kurulum, endpoint özeti ve tüm Modül 5 kontrol listesi ayrı dosyada tutulur:

- `backend/MODULE_5_SETUP_AND_CHECKLIST.md`
