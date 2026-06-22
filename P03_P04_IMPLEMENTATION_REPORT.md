# P03/P04 Implementation Report

## P03 — Celery Beat Scheduled Data Fetching

Implemented Celery + Redis + Celery Beat scheduling for background news ingestion.

### Added

- `backend/celery_app.py`
- `backend/celeryconfig.py`
- `backend/app/tasks/fetch_tasks.py`
- `backend/app/tasks/__init__.py`
- `backend/app/services/news_api_service.py`
- `backend/app/services/rss_service.py`

### Schedule

- `fetch_breaking_news`: every 5 minutes with `crontab(minute="*/5")`
- `fetch_all_rss`: hourly with `crontab(minute=0)`
- `full_crawl`: every day at 06:00 Europe/Istanbul with `crontab(hour=6, minute=0)`

### Retry

Each task uses:

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
```

Failures are logged. Transient failures retry after 60 seconds and final failures are logged with `logger.exception`.

## P04 — Multi-Language Support

Implemented deterministic article language detection and user-language filtering.

### Added

- `backend/app/routers/articles.py`
- `backend/app/ml/language_detector.py`
- `backend/app/ml/__init__.py`
- `backend/app/services/article_saver.py`
- `backend/app/services/language_service.py`
- `backend/app/services/__init__.py`

### Updated

- `backend/app/models.py`
  - Added `Article.language`
  - Added minimal `User.language_preference` model for language filtering
- `backend/app/crawlers/spider_manager.py`
  - Article persistence now goes through `save_article()` so language is detected before insert.
- `backend/requirements.txt`
  - Added `celery[redis]`, `redis`, and `langdetect`.

## Commands

```bash
cd smart-newspaper-Redmamba
pip install -r backend/requirements.txt
celery -A backend.celery_app worker --loglevel=info
celery -A backend.celery_app beat --loglevel=info
```

## Environment

```env
REDIS_URL=redis://localhost:6379/0
NEWS_API_KEY=your_news_api_key_here
NEWS_API_COUNTRY=tr
NEWS_API_PAGE_SIZE=20
```

## Database note

For an existing PostgreSQL database, add the language columns before running scheduled ingestion. The `users.id` type should match your production schema; this project uses text-compatible user ids:

```sql
ALTER TABLE articles ADD COLUMN IF NOT EXISTS language VARCHAR(10) NOT NULL DEFAULT 'unknown';
CREATE INDEX IF NOT EXISTS ix_articles_language ON articles(language);
ALTER TABLE users ADD COLUMN IF NOT EXISTS language_preference VARCHAR(10) NOT NULL DEFAULT 'tr';
```
