-- P06 MinHash + LSH duplicate detection columns for PostgreSQL backend.
-- Safe to run multiple times on PostgreSQL.

ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS minhash_signature BYTEA;

CREATE INDEX IF NOT EXISTS ix_articles_is_duplicate ON articles (is_duplicate);
