-- SmartNewspaper advanced search + trends migration.
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
