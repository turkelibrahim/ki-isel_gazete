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
