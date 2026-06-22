-- P08/P09: Multi-label classification and keyword extraction support.
-- article_categories already supports multiple rows per article through
-- uq_article_category(article_id, category_id). No extra multi-label table is required.

CREATE TABLE IF NOT EXISTS article_keywords (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_article_keyword UNIQUE (article_id, keyword)
);

CREATE INDEX IF NOT EXISTS ix_article_keywords_article_id ON article_keywords(article_id);
CREATE INDEX IF NOT EXISTS ix_article_keywords_keyword ON article_keywords(keyword);
CREATE INDEX IF NOT EXISTS ix_article_keywords_score ON article_keywords(score);
