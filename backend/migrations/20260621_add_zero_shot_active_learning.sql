-- P10/P11: zero-shot labels, active learning and audit trail.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'USER';

CREATE INDEX IF NOT EXISTS ix_users_role ON users(role);

ALTER TABLE moderation_queue
    ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_moderation_queue_reviewed_by ON moderation_queue(reviewed_by);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    details JSONB,
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS ix_audit_log_resource_type ON audit_log(resource_type);
CREATE INDEX IF NOT EXISTS ix_audit_log_resource_id ON audit_log(resource_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_created_by ON audit_log(created_by);
