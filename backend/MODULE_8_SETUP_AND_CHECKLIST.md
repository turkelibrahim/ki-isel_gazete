# Modül 8 — Toplu Kurulum, Endpoint Özeti ve Kontrol Listesi

Bu doküman Modül 8 içinde eklenen yönetim, monitoring, raporlama, JWT/RBAC ve içerik moderasyon katmanlarının tek yerden kurulum ve doğrulama özetidir.

## Modül 8 Genel Akış

1. Admin kullanıcı sisteme JWT ile giriş yapar.
2. AuthService access token ve refresh token üretir.
3. Protected endpointlerde token decode edilir.
4. RBAC sistemi kullanıcının rolünü kontrol eder.
5. ADMIN, EDITOR, USER izin matrisi uygulanır.
6. Admin kaynak, kategori, kullanıcı ve haber yönetimi yapar.
7. Silme işlemlerinde hard delete yerine mümkünse soft delete uygulanır.
8. MonitoringService sistem sağlığını, CPU, RAM, disk, DB ve Redis durumunu ölçer.
9. RotatingFileHandler log dosyalarını boyut bazlı döndürür.
10. ReportService analytics verilerinden PDF/CSV rapor üretir.
11. ModerationService önce keyword filter, sonra ML toxicity classifier çalıştırır.
12. `score >= 0.95` ise otomatik reddedilir.
13. `0.70 <= score < 0.95` ise insan incelemesine düşer.
14. `score < 0.70` ise onaylanır.
15. Tüm admin işlemleri `audit_log` tablosuna yazılır.
16. `database.py` değişmez, `main.py` sadece router include ve P37 logging setup için değişir.

## Toplu Kurulum

```bash
pip install python-jose passlib[bcrypt] python-multipart
pip install psutil redis
pip install matplotlib pandas
pip install transformers torch
```

Proje `backend/requirements.txt` içine bu bağımlılıkları ekler. Ağır/opsiyonel paketler eksikse backend import aşamasında çökmez; ilgili servisler kontrollü fallback döndürür.

## ENV

```bash
SECRET_KEY=32_karakterden_uzun_rastgele_secret
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
REDIS_URL=redis://localhost:6379/0
```

`SECRET_KEY` dosyaya hardcode edilmez. Development ortamında eksikse warning verilir; production ortamında güçlü secret kullanılmalıdır.

## Endpoint Özeti

### Auth / RBAC

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
```

### Admin

```http
GET   /api/admin/users
PATCH /api/admin/users/{user_id}/role
GET   /api/admin/sources
POST  /api/admin/sources/{source_id}/activate
POST  /api/admin/sources/{source_id}/deactivate
PATCH /api/admin/sources/{source_id}/trust-score
GET   /api/admin/articles
POST  /api/admin/articles/{article_id}/mark-duplicate
POST  /api/admin/articles/{article_id}/safe-delete
GET   /api/admin/audit-log
```

### Monitoring

```http
GET /api/monitoring/health
GET /api/monitoring/metrics
GET /api/monitoring/logs/recent
```

### Reports

```http
POST   /api/reports/generate?days=30&format=pdf
POST   /api/reports/generate?days=30&format=csv
GET    /api/reports/download?path=...
GET    /api/reports/list
DELETE /api/reports/cleanup?days=30
```

### Moderation

```http
POST /api/moderation/check-text
GET  /api/moderation/queue
POST /api/moderation/{moderation_id}/approve
POST /api/moderation/{moderation_id}/reject
GET  /api/moderation/stats
```

## Kontrol Listesi

### P36 — Admin CRUD / Soft Delete / Audit Log

- [x] `backend/app/services/admin_service.py` oluşturuldu.
- [x] `backend/app/schemas/admin.py` oluşturuldu.
- [x] `backend/app/routers/admin.py` oluşturuldu.
- [x] Source silme hard delete yerine `is_active=False` yapıyor.
- [x] Article safe delete `is_duplicate=True` yapıyor.
- [x] Admin işlemleri `audit_log` içine yazılıyor.
- [x] `trust_score` `0.0-1.0` aralığında validate ediliyor.

### P37 — System Monitoring / Health Check / RotatingFileHandler

- [x] `backend/app/services/monitoring_service.py` oluşturuldu.
- [x] `backend/app/core/logging_config.py` oluşturuldu.
- [x] `backend/app/routers/monitoring.py` oluşturuldu.
- [x] DB health `SELECT 1` ile kontrol ediliyor.
- [x] Redis yoksa sistem çökmüyor ve `disabled`/`error` durumunu kontrollü döndürüyor.
- [x] CPU/RAM/Disk `psutil` ile ölçülüyor.
- [x] RotatingFileHandler `maxBytes=10MB`, `backupCount=5` ile ayarlı.
- [x] `GET /api/monitoring/health` çalışıyor.

### P38 — Reporting System / Matplotlib PDF + CSV Export

- [x] `backend/app/services/report_service.py` oluşturuldu.
- [x] `backend/app/routers/reports.py` oluşturuldu.
- [x] Matplotlib `PdfPages` ile PDF rapor üretiliyor.
- [x] CSV export `utf-8-sig` encoding kullanıyor.
- [x] Raporlar `backend/storage/reports` içinde saklanıyor.
- [x] Path traversal engelleniyor.
- [x] Eski rapor cleanup çalışıyor.

### P39 — JWT Authentication + RBAC Authorization

- [x] `backend/app/core/security.py` oluşturuldu.
- [x] `backend/app/dependencies/auth.py` oluşturuldu.
- [x] `backend/app/services/auth_service.py` oluşturuldu.
- [x] `backend/app/schemas/auth.py` oluşturuldu.
- [x] `backend/app/routers/auth.py` oluşturuldu.
- [x] Password bcrypt ile hashleniyor; `passlib` yoksa controlled fallback import çökmesini engelliyor.
- [x] JWT HS256 kullanıyor.
- [x] Access token varsayılan `30 dakika`.
- [x] Refresh token varsayılan `7 gün`.
- [x] Refresh token protected endpointlerde reddediliyor.
- [x] `require_role("ADMIN")` USER için `403` döndürüyor.
- [x] `SECRET_KEY` hardcode edilmedi.

### P40 — Two-Layer Content Moderation / Keyword + ML Toxicity

- [x] `backend/app/services/content_moderation_service.py` oluşturuldu.
- [x] `backend/app/routers/content_moderation.py` oluşturuldu.
- [x] Keyword filter blocked kelimeleri yakalıyor.
- [x] ML toxicity classifier lazy singleton yükleniyor.
- [x] Model yoksa backend import aşamasında çökmüyor.
- [x] `score >= 0.95` → `REJECTED`.
- [x] `0.70 <= score < 0.95` → `PENDING`.
- [x] `score < 0.70` → `APPROVED`.
- [x] `PENDING` kayıt `moderation_queue` içine düşüyor.
- [x] approve/reject `reviewed_by` ve `reviewed_at` dolduruyor.
- [x] Review işlemleri `audit_log` içine yazılıyor.

### Paket Doğrulama

- [x] `database.py` hiç değişmedi.
- [x] `main.py` sadece router include ve P37 logging setup için değişti.
- [x] `python -m compileall -q backend` başarılı.
- [x] FastAPI route check başarılı.
- [x] `npm test` hâlâ `70/70 passed`.
- [x] `npm run build` başarılı.

## Sonraki Parça

Sıradaki son parça: **Modül 8 final paket doğrulama / teslim raporu** veya istenirse proje geneli üretim hazırlığı.
