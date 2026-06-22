-- Module 6 / P28 search + filter performance indexes.
-- Run manually in PostgreSQL.  This file is intentionally not a migration.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_search_filter
ON articles(published_at DESC, source_id, language, view_count DESC)
WHERE is_duplicate = FALSE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_article_categories_filter
ON article_categories(category_id, article_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_bookmarks_filter
ON user_bookmarks(user_id, article_id);
