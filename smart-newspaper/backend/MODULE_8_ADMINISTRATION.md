# Modül 8 — Reporting & Administration

Bu modül yönetim, güvenlik, izleme, raporlama ve moderasyon katmanlarını kapsar.

## Genel Akış

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
16. `database.py` değişmez, `main.py` sadece router include için değişir.

## P36 — Admin CRUD / Soft Delete / Audit Log

Eklenen dosyalar:

- `backend/app/services/admin_service.py`
- `backend/app/schemas/admin.py`
- `backend/app/routers/admin.py`

Güncellenen dosyalar:

- `backend/app/main.py`
- `FINAL_PACKAGE_REPORT.md`

### Endpointler

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

### Geçici Admin Guard

Prompt 39 Auth/RBAC gelene kadar admin endpointleri geçici guard kullanır.

```bash
curl "http://localhost:8000/api/admin/users?requester_role=ADMIN&admin_user_id=admin-1"
```

veya:

```bash
curl -H "X-User-Role: ADMIN" -H "X-User-Id: admin-1" \
  "http://localhost:8000/api/admin/users"
```

`ADMIN` olmayan istekler `403` döner.

### Soft Delete Mantığı

- Kaynak silme yapılmaz: `sources.is_active = False`
- Haber hard delete yapılmaz: `articles.is_duplicate = True`
- Kullanıcı silme endpointi eklenmedi. `users.is_active` alanı yoksa migration yapılmaz şartı korunur.

### Audit Log

Kritik admin aksiyonları `audit_log` tablosuna yazılır:

- `UPDATE_USER_ROLE`
- `DEACTIVATE_SOURCE`
- `ACTIVATE_SOURCE`
- `UPDATE_SOURCE_TRUST`
- `MARK_ARTICLE_DUPLICATE`
- `SAFE_DELETE_ARTICLE`

Mevcut migration şemasına sadık kalınır:

- `action`
- `resource_type`
- `resource_id`
- `details`
- `created_by`
- `created_at`

API response tarafında `created_by`, kullanıcı dostu olması için `user_id` olarak döndürülür.

### Doğrulama

- ADMIN olmayan kullanıcı admin endpointlerine erişemez.
- Kaynak silme yerine `is_active=False` uygulanır.
- Haber silme yerine `is_duplicate=True` uygulanır.
- `trust_score` `0.0` ile `1.0` arasında doğrulanır.
- Her kritik işlem audit log yazar.
- `database.py` değişmez.
- `main.py` sadece admin router import/include için değişir.

## P37 — System Monitoring / Health Check / RotatingFileHandler

Eklenen dosyalar:

- `backend/app/services/monitoring_service.py`
- `backend/app/core/logging_config.py`
- `backend/app/routers/monitoring.py`
- `backend/logs/.gitkeep`
- `backend/MODULE_8_P37_MONITORING.md`

### Endpointler

```http
GET /api/monitoring/health
GET /api/monitoring/metrics
GET /api/monitoring/logs/recent?lines=100
```

### Health İçeriği

- Database `SELECT 1` latency check
- Redis ping veya `disabled` fallback
- CPU yüzdesi
- RAM kullanımı
- Disk kullanımı
- Model dosyaları kontrolü

Redis hatası tüm health endpointini 500 yapmaz.

### Log Yönetimi

`setup_logging()` RotatingFileHandler kullanır:

- Dosya: `backend/logs/app.log`
- `maxBytes = 10 * 1024 * 1024`
- `backupCount = 5`
- Format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`

`main.py` içinde router include dışında sadece logging setup import/call eklendi.

### Doğrulama

- `GET /api/monitoring/health` sistem durumunu döndürür.
- `GET /api/monitoring/metrics` admin dashboard metriklerini döndürür.
- `GET /api/monitoring/logs/recent` son log satırlarını döndürür.
- `database.py` değiştirilmedi.

## P38 — Reporting System / Matplotlib PDF + CSV Export

Eklenen dosyalar:

- `backend/app/services/report_service.py`
- `backend/app/routers/reports.py`
- `backend/storage/reports/.gitkeep`
- `backend/MODULE_8_P38_REPORTING.md`

### Endpointler

```http
POST   /api/reports/generate?days=30&format=pdf
POST   /api/reports/generate?days=30&format=csv
GET    /api/reports/download?path=...
GET    /api/reports/list
DELETE /api/reports/cleanup?days=30
```

### Rapor İçeriği

ReportService, AnalyticsService metriklerini kullanır:

- overview
- daily_active_users
- top_articles
- category_reads
- source_performance
- moderation_summary

PDF rapor Matplotlib `PdfPages` ile 5 sayfa üretir: overview, DAU line chart, category bar chart, top articles table, source performance table.

CSV export tek dosya olarak `metric_type,key,value,date` kolonlarıyla ve `utf-8-sig` encoding ile oluşturulur.

### Güvenlik

Download endpoint sadece `backend/storage/reports/` altındaki `.pdf` ve `.csv` dosyalarını verir. `../` path traversal denemeleri reddedilir.

### Doğrulama

- PDF/CSV rapor üretimi desteklenir.
- Rapor dosyaları `backend/storage/reports/` altında tutulur.
- Cleanup eski raporları silebilir.
- `database.py` değiştirilmedi.
- `main.py` sadece reports router import/include için değişti.

## P39 — JWT Authentication + RBAC Authorization

Eklenen dosyalar:

- `backend/app/core/security.py`
- `backend/app/dependencies/auth.py`
- `backend/app/services/auth_service.py`
- `backend/app/schemas/auth.py`
- `backend/app/routers/auth.py`
- `backend/migrations/20260621_add_user_password_hash.sql`
- `backend/MODULE_8_P39_AUTH_RBAC.md`

### Endpointler

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
```

### RBAC Entegrasyonu

P36, P37 ve P38 içindeki geçici admin guard yapıları gerçek JWT/RBAC dependency ile değiştirildi:

- `/api/admin/*` → ADMIN
- `/api/monitoring/metrics` → ADMIN
- `/api/monitoring/logs/recent` → ADMIN
- `/api/reports/*` → ADMIN
- `/api/monitoring/health` → public

### Güvenlik Notları

- Password response içinde dönmez.
- `password_hash` response içinde dönmez.
- `SECRET_KEY` dosyaya hardcode edilmez.
- Access token kısa ömürlüdür.
- Refresh token uzun ömürlüdür.
- Token `type` alanı kontrol edilir.
- Refresh token protected endpointlerde kabul edilmez.
- Access token refresh endpointinde kabul edilmez.

### Doğrulama

- Register password hash üretir.
- Login token çifti döndürür.
- `/api/auth/me` access token ister.
- ADMIN endpointleri USER rolü için 403 döner.
- `database.py` değiştirilmedi.

---

## P40 — Two-Layer Content Moderation

Eklenen dosyalar:

- `backend/app/services/content_moderation_service.py`
- `backend/app/routers/content_moderation.py`
- `backend/migrations/20260621_add_content_moderation_fields.sql`
- `backend/MODULE_8_P40_CONTENT_MODERATION.md`

Endpointler:

```bash
POST /api/moderation/check-text
GET  /api/moderation/queue
POST /api/moderation/{moderation_id}/approve
POST /api/moderation/{moderation_id}/reject
GET  /api/moderation/stats
```

Karar mantığı:

- `keyword_blocked=True` → `REJECTED`, `BLOCKED_KEYWORD`, skor en az `0.95`
- `score >= 0.95` → `REJECTED`, `HIGH_TOXICITY`
- `0.70 <= score < 0.95` → `PENDING`, `NEEDS_HUMAN_REVIEW`
- `score < 0.70` → `APPROVED`, `LOW_RISK`

Notlar:

- `transformers`/`torch` veya model yoksa sistem çökmez, `ml_available=false` döner.
- Keyword filter her zaman çalışır.
- `PENDING` ve `REJECTED` kayıtları `moderation_queue` içine yazılır.
- `REJECTED` article için `is_duplicate=True` uygulanır.
- Approve/reject işlemleri `audit_log` içine `APPROVE_MODERATION` / `REJECT_MODERATION` yazar.

---

## Modül 8 — Toplu Kurulum ve Kontrol Listesi

Toplu kurulum komutları, endpoint özeti ve tüm P36/P37/P38/P39/P40 kontrol listesi şu dokümana eklenmiştir:

- `backend/MODULE_8_SETUP_AND_CHECKLIST.md`

Bu dokümanda Modül 8 genel akışı, auth/admin/monitoring/report/moderation endpointleri, güvenlik notları ve doğrulama maddeleri tek yerde tutulur.
