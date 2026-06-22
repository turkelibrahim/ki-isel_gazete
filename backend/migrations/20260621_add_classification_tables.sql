-- P07 News Classification schema additions.
-- Adds automatic/human category labels and low-confidence moderation queue.

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    slug VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS article_categories (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    model VARCHAR(50) NOT NULL DEFAULT 'ensemble',
    is_human_label BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_article_category UNIQUE(article_id, category_id)
);

CREATE INDEX IF NOT EXISTS ix_article_categories_article_id ON article_categories(article_id);
CREATE INDEX IF NOT EXISTS ix_article_categories_category_id ON article_categories(category_id);
CREATE INDEX IF NOT EXISTS ix_article_categories_is_human_label ON article_categories(is_human_label);

CREATE TABLE IF NOT EXISTS moderation_queue (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    predicted_category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    reason VARCHAR(255) NOT NULL DEFAULT 'low_confidence',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_moderation_queue_article_id ON moderation_queue(article_id);
CREATE INDEX IF NOT EXISTS ix_moderation_queue_predicted_category_id ON moderation_queue(predicted_category_id);
CREATE INDEX IF NOT EXISTS ix_moderation_queue_status ON moderation_queue(status);
