-- Module 8 / Prompt 39 — JWT Authentication support
-- Adds a password hash column without touching backend/app/database.py.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
