-- SmartNewspaper analytics, user behavior tracking, TF-IDF recommendation and dashboard schema.
-- Safe SQLite/PostgreSQL-compatible baseline; JSON runtime uses scripts/migrate-json-db.js.

CREATE TABLE IF NOT EXISTS user_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  anonymous_id TEXT,
  session_id TEXT NOT NULL UNIQUE,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  device_type TEXT,
  browser TEXT,
  ip_hash TEXT,
  user_agent TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_interactions (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  anonymous_id TEXT,
  session_id TEXT,
  news_id TEXT,
  category TEXT,
  source_name TEXT,
  interaction_type TEXT NOT NULL,
  duration_seconds INTEGER DEFAULT 0,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_profiles (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  anonymous_id TEXT,
  favorite_categories_json TEXT,
  favorite_sources_json TEXT,
  favorite_tags_json TEXT,
  average_reading_time REAL DEFAULT 0,
  total_reading_time REAL DEFAULT 0,
  total_articles_read INTEGER DEFAULT 0,
  last_active_at TEXT,
  profile_vector_json TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS news_vectors (
  id TEXT PRIMARY KEY,
  news_id TEXT NOT NULL,
  vector_json TEXT,
  text_hash TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS user_recommendations (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  news_id TEXT NOT NULL,
  recommendation_score REAL DEFAULT 0,
  content_based_score REAL DEFAULT 0,
  collaborative_score REAL,
  content_similarity_score REAL DEFAULT 0,
  popularity_score REAL DEFAULT 0,
  freshness_score REAL DEFAULT 0,
  reason TEXT,
  status TEXT DEFAULT 'active',
  created_at TEXT,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_anonymous_id ON user_sessions(anonymous_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_news_id ON user_interactions(news_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_created_at ON user_interactions(created_at);
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_news_vectors_news_id ON news_vectors(news_id);
CREATE INDEX IF NOT EXISTS idx_user_recommendations_user_id ON user_recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_recommendations_score ON user_recommendations(recommendation_score);
