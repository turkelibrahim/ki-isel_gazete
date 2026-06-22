-- Module 6 / P29: Bookmark CRUD / Optimistic Upsert
-- Apply manually after previous migrations. database.py is intentionally unchanged.

CREATE TABLE IF NOT EXISTS user_bookmarks (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_bookmark_article UNIQUE (user_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_user_bookmarks_user_created
ON user_bookmarks(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_bookmarks_article
ON user_bookmarks(article_id);
