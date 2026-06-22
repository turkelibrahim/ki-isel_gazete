# P06 — MinHash + LSH Duplicate Detection Implementation Report

## Added files

- `backend/app/ml/duplicate_detector.py`
- `backend/app/tasks/dedup_task.py`
- `backend/migrations/20260621_add_dedup_columns.sql`

## Updated files

- `backend/app/services/article_saver.py`
- `backend/app/models.py`
- `backend/app/main.py`
- `backend/app/tasks/__init__.py`
- `backend/celeryconfig.py`
- `backend/requirements.txt`
- `backend/app/routers/articles.py`
- `db/schema.sql`

## Behavior

- New articles are checked with MinHash + LSH before insert.
- Same URL is still handled by the existing PostgreSQL `ON CONFLICT DO NOTHING` upsert.
- Same or near-same content from a different URL is marked with `articles.is_duplicate = True`.
- Non-duplicate inserted articles are added to the in-memory LSH index.
- Existing non-duplicate articles are loaded into the LSH index on FastAPI startup.
- A daily Celery task rebuilds the duplicate index and updates older rows in batches.

## Algorithm parameters

- Shingle size: `k=5`
- MinHash permutations: `num_perm=128`
- LSH threshold: `0.8`
- Final Jaccard verification threshold: `0.8`
- Batch size for daily rebuild: `500`

## Celery task

Daily duplicate rebuild task:

```bash
celery -A backend.celery_app worker --loglevel=info
celery -A backend.celery_app beat --loglevel=info
```

Beat schedule name:

- `rebuild-duplicate-index-daily`

Task name:

- `app.tasks.dedup_task.rebuild_duplicate_index`

## Dependency

```bash
pip install datasketch
```

or install all backend dependencies:

```bash
pip install -r backend/requirements.txt
```

## Database migration

For an existing PostgreSQL database, run:

```bash
psql "$DATABASE_URL" -f backend/migrations/20260621_add_dedup_columns.sql
```

The migration adds:

- `articles.is_duplicate BOOLEAN NOT NULL DEFAULT FALSE`
- `articles.minhash_signature BYTEA`
- index on `is_duplicate`

## Safety

If `datasketch` is not installed yet, the detector logs a warning and safely falls back to `duplicate=False` instead of crashing ingestion. Once dependencies are installed, MinHash + LSH is active.
