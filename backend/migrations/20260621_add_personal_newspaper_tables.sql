-- Module 3 / P12 personal newspaper recommendation tables and article fields.
-- Safe to run after previous Module 1 and Module 2 migrations.

ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS summary TEXT;

ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS view_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_articles_view_count ON articles(view_count);

CREATE TABLE IF NOT EXISTS user_events (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  event_type VARCHAR(50) NOT NULL DEFAULT 'VIEWED',
  duration_seconds DOUBLE PRECISION,
  scroll_percent DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_user_events_user_id ON user_events(user_id);
CREATE INDEX IF NOT EXISTS ix_user_events_article_id ON user_events(article_id);
CREATE INDEX IF NOT EXISTS ix_user_events_event_type ON user_events(event_type);
CREATE INDEX IF NOT EXISTS ix_user_events_created_at ON user_events(created_at);

CREATE TABLE IF NOT EXISTS user_interests (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_user_interest_category UNIQUE (user_id, category_id)
);

CREATE INDEX IF NOT EXISTS ix_user_interests_user_id ON user_interests(user_id);
CREATE INDEX IF NOT EXISTS ix_user_interests_category_id ON user_interests(category_id);

CREATE TABLE IF NOT EXISTS newspaper_editions (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  html_content TEXT NOT NULL,
  language VARCHAR(10) NOT NULL DEFAULT 'tr',
  metadata_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_newspaper_editions_user_id ON newspaper_editions(user_id);
CREATE INDEX IF NOT EXISTS ix_newspaper_editions_language ON newspaper_editions(language);
CREATE INDEX IF NOT EXISTS ix_newspaper_editions_created_at ON newspaper_editions(created_at);
