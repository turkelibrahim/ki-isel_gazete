# Modül 5 — Events & Reminders / Toplu Kurulum ve Kontrol Listesi

## Modül 5 Genel Akış

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

## Modül 5 Toplu Kurulum

```bash
pip install spacy dateparser python-dateutil
pip install httpx
pip install celery[redis] redis
python -m spacy download xx_ent_wiki_sm
```

İsteğe bağlı Türkçe spaCy modeli mevcutsa önce o kullanılabilir:

```bash
python -m spacy download tr_core_news_sm
```

## Modül 5 Endpoint Özeti

```bash
GET    /api/events
GET    /api/events/upcoming?days=7
POST   /api/events
POST   /api/events/detect-from-text
PATCH  /api/events/{event_id}
DELETE /api/events/{event_id}
POST   /api/events/reminders/run-now
```

## Modül 5 Kontrol Listesi

- [x] `backend/app/ml/event_detector.py` oluşturuldu.
- [x] `backend/app/ml/event_category_classifier.py` oluşturuldu.
- [x] `backend/app/services/event_service.py` oluşturuldu.
- [x] `backend/app/services/push_service.py` oluşturuldu.
- [x] `backend/app/services/email_service.py` oluşturuldu.
- [x] `backend/app/tasks/reminder_task.py` oluşturuldu.
- [x] `backend/app/routers/events.py` oluşturuldu.
- [x] Tarih + keyword olan cümle event olarak yakalanıyor.
- [x] Sadece tarih olan cümle event olmuyor.
- [x] Sadece keyword olan cümle event olmuyor.
- [x] Confidence `0.65` / `0.85` mantığı uygulanıyor.
- [x] Event category `EXAM` / `DEADLINE` / `ACADEMIC` / `MEETING` / `SOCIAL` / `OTHER` çalışıyor.
- [x] Eşitlikte `EXAM > DEADLINE > ACADEMIC > MEETING > SOCIAL` önceliği var.
- [x] `remind_at = event_date - 24 saat` hesaplanıyor.
- [x] Celery Beat reminder task `*/15` dakika planlandı.
- [x] `is_notified=True` tekrar bildirim göndermeyi engelliyor.
- [x] `FCM_SERVER_KEY` yoksa sistem çökmeden push atlıyor.
- [x] SMTP bilgileri yoksa sistem çökmeden email atlıyor.
- [x] Önümüzdeki 7 günün etkinlikleri gazete HTML’ine ekleniyor.
- [x] PDF export etkinlikleri otomatik içeriyor.
- [x] `database.py` hiç değişmedi.
- [x] `main.py` sadece router include için değişti.
- [x] `python -m compileall -q backend` başarılı.
- [x] FastAPI route check başarılı.

## Uygulama Notları

- Hatırlatıcılar memory tabanlı `setTimeout` ile değil, DB polling + Celery Beat ile çalışır.
- Sunucu restart olursa `remind_at` verisi DB’de kaldığı için reminder tekrar yakalanabilir.
- Push ve email kanalları birbirinden bağımsızdır; bir kanal hata verirse diğer kanal denenmeye devam eder.
- En az bir bildirim kanalı başarılı olursa event `is_notified=True` yapılır.
- PDF tarafına ayrıca kod eklenmedi; etkinlikler HTML layout içine girdiği için Modül 4 PDF export otomatik olarak etkinlikleri de içerir.
