-- Module 5 / P24 event service additions.
-- Adds notification state expected by EventService without touching database.py.

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS is_notified BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_events_is_notified ON events(is_notified);

CREATE UNIQUE INDEX IF NOT EXISTS uq_events_title_date_active
ON events(title, event_date)
WHERE is_active = TRUE;
