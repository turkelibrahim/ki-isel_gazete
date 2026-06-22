-- P40: Content moderation fields for keyword + ML toxicity review.
-- Keeps existing active-learning moderation rows compatible while allowing
-- content moderation rows that are not tied to a predicted category.

ALTER TABLE moderation_queue
    ALTER COLUMN predicted_category_id DROP NOT NULL;

ALTER TABLE moderation_queue
    ADD COLUMN IF NOT EXISTS toxicity_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS flagged_reason VARCHAR(255);

CREATE INDEX IF NOT EXISTS ix_moderation_queue_flagged_reason ON moderation_queue(flagged_reason);
CREATE INDEX IF NOT EXISTS ix_moderation_queue_toxicity_score ON moderation_queue(toxicity_score);
