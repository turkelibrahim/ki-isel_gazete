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
