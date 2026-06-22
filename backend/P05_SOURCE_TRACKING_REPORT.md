# P05 — Source Tracking & Citation Implementation Report

## Added

- `backend/app/services/source_tracker.py`
  - `MetadataExtractor.extract(html, url)`
  - Publisher priority chain: `og:site_name`, `article:publisher`, `twitter:site`, `application-name`, URL fallback
  - Date priority chain: `article:published_time`, `article:modified_time`, `og:updated_time`, `DC.Date`, `<time datetime>` fallback
  - Author priority chain: `author`, `article:author`, `DC.Creator`, `byline`
  - Turkish relative dates with `arrow.humanize(locale="tr")`
  - Trust badge mapping: `güvenilir`, `orta`, `düşük`

- `backend/app/routers/citations.py`
  - `GET /api/articles/{article_id}/citation`
  - Returns article title, source name, publisher, author, publication date, human date, URL, trust score and badge

## Modified

- `backend/app/main.py`
  - Included citations router only.

- `backend/app/models.py`
  - Added `Source.trust_score` with default `0.5` so new DBs can store the trust score required by P05.

- `backend/requirements.txt`
  - Added `arrow` and `python-dateutil`.

## Notes

- `backend/app/database.py` was not modified.
- If you already have a live PostgreSQL `sources` table, add a `trust_score` column or run a migration before using the new field in production.
