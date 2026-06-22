-- Module 3 / P17 personal newspaper edition pipeline additions.
-- Safe to run after 20260621_add_personal_newspaper_tables.sql.

ALTER TABLE newspaper_editions
  ADD COLUMN IF NOT EXISTS edition_date DATE NOT NULL DEFAULT CURRENT_DATE;

ALTER TABLE newspaper_editions
  ADD COLUMN IF NOT EXISTS frequency VARCHAR(50) NOT NULL DEFAULT 'daily';

ALTER TABLE newspaper_editions
  ADD COLUMN IF NOT EXISTS pdf_path TEXT;

ALTER TABLE newspaper_editions
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS uq_newspaper_daily_edition
ON newspaper_editions(user_id, edition_date, frequency);

CREATE INDEX IF NOT EXISTS ix_newspaper_editions_edition_date ON newspaper_editions(edition_date);
CREATE INDEX IF NOT EXISTS ix_newspaper_editions_frequency ON newspaper_editions(frequency);
CREATE INDEX IF NOT EXISTS ix_newspaper_editions_updated_at ON newspaper_editions(updated_at);

CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY,
  title VARCHAR(500) NOT NULL,
  description TEXT,
  location VARCHAR(500),
  category VARCHAR(100),
  event_date TIMESTAMPTZ NOT NULL,
  remind_at TIMESTAMPTZ,
  user_id VARCHAR(255) REFERENCES users(id) ON DELETE CASCADE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_events_event_date ON events(event_date);
CREATE INDEX IF NOT EXISTS ix_events_remind_at ON events(remind_at);
CREATE INDEX IF NOT EXISTS ix_events_category ON events(category);
CREATE INDEX IF NOT EXISTS ix_events_user_id ON events(user_id);
CREATE INDEX IF NOT EXISTS ix_events_is_active ON events(is_active);
CREATE INDEX IF NOT EXISTS ix_events_created_at ON events(created_at);
