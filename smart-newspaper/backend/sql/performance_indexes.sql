-- Performance indexes for Module 3 / P13 article filtering.
-- Run this manually against PostgreSQL outside a transaction, because
-- CREATE INDEX CONCURRENTLY cannot run inside a standard migration transaction.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_filter
ON articles(published_at DESC, source_id, view_count DESC)
WHERE is_duplicate = FALSE;

-- Optional helper indexes for common join/filter paths used by /api/articles.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_article_categories_article_category
ON article_categories(article_id, category_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_language_published
ON articles(language, published_at DESC)
WHERE is_duplicate = FALSE;
