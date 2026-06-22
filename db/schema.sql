CREATE TABLE users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  password_salt TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE user_preferences (
  user_id TEXT PRIMARY KEY REFERENCES users(id),
  interests TEXT NOT NULL,
  preferred_sources TEXT NOT NULL,
  reading_mode TEXT NOT NULL DEFAULT 'daily',
  language TEXT NOT NULL DEFAULT 'tr',
  reading_goal INTEGER NOT NULL DEFAULT 20
);

CREATE TABLE articles (
  id TEXT PRIMARY KEY,

  -- Legacy display fields (kept for backward compat)
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  full_text TEXT NOT NULL,

  -- Original-language fields (never overwritten by translation)
  original_title TEXT,
  original_summary TEXT,
  original_content TEXT,
  original_language TEXT NOT NULL DEFAULT 'tr',

  -- Translation fields (populated by AI translation pipeline; optional)
  translated_title TEXT NOT NULL DEFAULT '',
  translated_summary TEXT NOT NULL DEFAULT '',
  translated_content TEXT NOT NULL DEFAULT '',

  -- Locale-aware display fields (derived; updated when translation arrives)
  display_title TEXT,
  display_summary TEXT,
  display_content TEXT,

  -- Category & topics
  category TEXT NOT NULL,
  subcategory TEXT,
  tags TEXT NOT NULL,
  topics TEXT NOT NULL DEFAULT '[]',

  -- Source metadata
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_country TEXT NOT NULL DEFAULT '',
  source_country_code TEXT NOT NULL DEFAULT '',
  source_region TEXT NOT NULL DEFAULT 'global',
  source_language TEXT NOT NULL DEFAULT 'tr',
  source_trust_level TEXT NOT NULL DEFAULT 'medium',
  source_type TEXT NOT NULL DEFAULT 'rss',
  is_global_source INTEGER NOT NULL DEFAULT 0,
  source_id TEXT NOT NULL DEFAULT '',

  -- Region detection
  detected_event_region TEXT NOT NULL DEFAULT 'global',
  mentioned_regions TEXT NOT NULL DEFAULT '[]',
  mentioned_countries TEXT NOT NULL DEFAULT '[]',

  -- Named entities (JSON object)
  named_entities TEXT NOT NULL DEFAULT '{}',

  -- Media & URLs
  image_url TEXT,
  url TEXT,
  author TEXT,

  -- Timestamps
  published_at TEXT NOT NULL,
  fetched_at TEXT,
  created_at TEXT NOT NULL,

  -- Processing
  content_hash TEXT NOT NULL,
  duplicate_group_id TEXT,
  is_duplicate INTEGER NOT NULL DEFAULT 0,
  minhash_signature BLOB,
  ai_summary TEXT,
  content_status TEXT NOT NULL DEFAULT 'summary_only'
);

CREATE TABLE user_article_events (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  article_id TEXT NOT NULL REFERENCES articles(id),
  event_type TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE bookmarks (
  user_id TEXT NOT NULL REFERENCES users(id),
  article_id TEXT NOT NULL REFERENCES articles(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, article_id)
);

CREATE TABLE read_status (
  user_id TEXT NOT NULL REFERENCES users(id),
  article_id TEXT NOT NULL REFERENCES articles(id),
  status TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, article_id)
);

CREATE TABLE ingestion_runs (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  status TEXT NOT NULL,
  fetched_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  finished_at TEXT
);


-- Notification system schema
CREATE TABLE IF NOT EXISTS notification_preferences (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  push_enabled INTEGER DEFAULT 0,
  email_enabled INTEGER DEFAULT 1,
  critical_announcements_enabled INTEGER DEFAULT 1,
  event_reminders_enabled INTEGER DEFAULT 1,
  one_day_before_enabled INTEGER DEFAULT 1,
  one_hour_before_enabled INTEGER DEFAULT 1,
  event_start_enabled INTEGER DEFAULT 0,
  timezone TEXT DEFAULT 'Europe/Istanbul',
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  p256dh_key TEXT NOT NULL,
  auth_key TEXT NOT NULL,
  user_agent TEXT,
  is_active INTEGER DEFAULT 1,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS scheduled_notifications (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  announcement_id TEXT,
  event_id TEXT,
  article_id TEXT,
  notification_type TEXT,
  channel TEXT,
  title TEXT,
  message TEXT,
  html_content TEXT,
  target_url TEXT,
  scheduled_at TEXT,
  sent_at TEXT,
  status TEXT DEFAULT 'pending',
  retry_count INTEGER DEFAULT 0,
  error_message TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS announcements (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  event_date TEXT,
  is_critical INTEGER DEFAULT 0,
  priority TEXT DEFAULT 'normal',
  target_url TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_notification_preferences_user ON notification_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user ON push_subscriptions(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_due ON scheduled_notifications(status, scheduled_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_scheduled_notifications_dedupe ON scheduled_notifications(user_id, announcement_id, event_id, article_id, notification_type, channel);
CREATE INDEX IF NOT EXISTS idx_announcements_critical ON announcements(is_critical, event_date);

-- Advanced search, full-text fallback and trend scoring schema
ALTER TABLE articles ADD COLUMN search_count INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN search_click_count INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN trend_score REAL DEFAULT 0;

CREATE TABLE IF NOT EXISTS search_logs (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  query TEXT,
  normalized_query TEXT,
  result_count INTEGER DEFAULT 0,
  clicked_news_id TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_interactions (
  id TEXT PRIMARY KEY,
  news_id TEXT NOT NULL,
  user_id TEXT,
  interaction_type TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_source_name ON articles(source_name);
CREATE INDEX IF NOT EXISTS idx_articles_published_at_search ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_trend_score ON articles(trend_score);
CREATE INDEX IF NOT EXISTS idx_articles_view_count_search ON articles(view_count);
CREATE INDEX IF NOT EXISTS idx_articles_share_count_search ON articles(share_count);
CREATE INDEX IF NOT EXISTS idx_articles_search_click_count ON articles(search_click_count);
CREATE INDEX IF NOT EXISTS idx_search_logs_query ON search_logs(normalized_query, created_at);
CREATE INDEX IF NOT EXISTS idx_news_interactions_news_type ON news_interactions(news_id, interaction_type, created_at);

-- Analytics and recommendation module tables.
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


-- Reports, RBAC and audit log module
CREATE TABLE IF NOT EXISTS generated_reports (
  id TEXT PRIMARY KEY,
  created_by_user_id TEXT,
  report_type TEXT NOT NULL,
  title TEXT,
  date_range_start TEXT,
  date_range_end TEXT,
  format TEXT NOT NULL,
  file_url TEXT,
  status TEXT DEFAULT 'pending',
  error_message TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS scheduled_reports (
  id TEXT PRIMARY KEY,
  created_by_user_id TEXT,
  report_type TEXT NOT NULL,
  frequency TEXT NOT NULL,
  format TEXT NOT NULL,
  recipients_json TEXT,
  scheduled_time TEXT,
  scheduled_day TEXT,
  timezone TEXT DEFAULT 'Europe/Istanbul',
  is_active INTEGER DEFAULT 1,
  last_run_at TEXT,
  next_run_at TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS system_metrics (
  id TEXT PRIMARY KEY,
  cpu_usage REAL,
  memory_usage REAL,
  disk_usage REAL,
  request_count INTEGER DEFAULT 0,
  error_count INTEGER DEFAULT 0,
  average_response_time REAL,
  pdf_generation_count INTEGER DEFAULT 0,
  email_sent_count INTEGER DEFAULT 0,
  report_generation_count INTEGER DEFAULT 0,
  scheduler_status TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS roles (id TEXT PRIMARY KEY, name TEXT, slug TEXT UNIQUE, description TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS permissions (id TEXT PRIMARY KEY, name TEXT, slug TEXT UNIQUE, description TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS role_permissions (id TEXT PRIMARY KEY, role_id TEXT, permission_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS user_roles (id TEXT PRIMARY KEY, user_id TEXT, role_id TEXT, assigned_by TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  actor_user_id TEXT,
  action TEXT,
  target_type TEXT,
  target_id TEXT,
  old_value_json TEXT,
  new_value_json TEXT,
  ip_hash TEXT,
  user_agent TEXT,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_generated_reports_created_by ON generated_reports(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_generated_reports_status ON generated_reports(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_next_run ON scheduled_reports(is_active, next_run_at);
CREATE INDEX IF NOT EXISTS idx_system_metrics_created_at ON system_metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
