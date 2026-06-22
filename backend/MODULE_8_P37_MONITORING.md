# Modül 8 / P37 — System Monitoring / Health Check / RotatingFileHandler

Bu parça sistem sağlığı, servis durumları, uygulama metrikleri ve kontrollü log yönetimi için MonitoringService katmanını ekler.

## Eklenen Dosyalar

- `backend/app/services/monitoring_service.py`
- `backend/app/core/logging_config.py`
- `backend/app/routers/monitoring.py`
- `backend/logs/.gitkeep`

## Güncellenen Dosyalar

- `backend/app/main.py`
- `backend/requirements.txt`
- `backend/MODULE_8_ADMINISTRATION.md`
- `FINAL_PACKAGE_REPORT.md`

## Kurulum

```bash
pip install psutil redis
```

## Endpointler

```http
GET /api/monitoring/health
GET /api/monitoring/metrics
GET /api/monitoring/logs/recent?lines=100
```

## Health Check İçeriği

`GET /api/monitoring/health` public endpoint olarak tasarlandı ve şu bileşenleri döndürür:

- Database `SELECT 1` latency check
- Redis ping veya `disabled` durumu
- CPU yüzdesi
- RAM kullanımı
- Disk kullanımı
- Model dosya kontrolü

Redis yapılandırılmamışsa health endpoint bozulmaz:

```json
{"status": "disabled"}
```

## Application Metrics

`GET /api/monitoring/metrics` admin dashboard için şu sayıları döndürür:

- `total_users`
- `total_articles`
- `total_sources`
- `active_sources`
- `total_events`
- `pending_moderation_count`
- `total_editions`
- `total_bookmarks`

## RotatingFileHandler

`backend/app/core/logging_config.py` içinde `setup_logging()` eklendi.

Ayarlar:

- Log dosyası: `backend/logs/app.log`
- Rotation: `10 * 1024 * 1024` byte
- Backup sayısı: `5`
- Format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- Console handler korunur.

`backend/logs/` klasörü yoksa otomatik oluşturulur.

## Recent Logs

`GET /api/monitoring/logs/recent?lines=100` son N satırı döndürür.

- Default: `100`
- Maksimum: `1000`
- Log dosyası yoksa boş liste döner.

## Permission

- `/api/monitoring/health` public olabilir.
- `/api/monitoring/metrics` ve `/api/monitoring/logs/recent` ADMIN ister.
- Auth/RBAC Prompt 39 gelene kadar geçici guard desteklenir:

```bash
curl -H "X-User-Role: ADMIN" "http://localhost:8000/api/monitoring/metrics"
```

veya:

```bash
curl "http://localhost:8000/api/monitoring/metrics?requester_role=ADMIN"
```

## Doğrulama

- DB durumu yapılandırılmış bağlantıda `ok`, bağlantı yoksa kontrollü `error` döner.
- Redis yoksa sistem çökmez, `disabled` veya `error` döner.
- CPU/RAM/Disk metrikleri `psutil` ile döner.
- `backend/logs/app.log` dosyası oluşur.
- Log dosyası 10MB üstünde rotate edebilir.
- `database.py` değişmez.
- `main.py` sadece monitoring router include ve logging setup için değişir.
