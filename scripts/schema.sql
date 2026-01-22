-- Cloudflare D1 Schema for Gmail Inbox Helper
-- Run via Wrangler: npx wrangler d1 execute gmail-inbox-helper --file=scripts/schema.sql

-- Processed marketing emails
CREATE TABLE IF NOT EXISTS processed_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    email_id TEXT NOT NULL,
    classification TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(account_name, email_id)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_processed_emails_account_email
ON processed_emails(account_name, email_id);

-- Job application emails
CREATE TABLE IF NOT EXISTS job_application_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    email_id TEXT NOT NULL,
    is_job_related INTEGER NOT NULL DEFAULT 0,
    needs_followup INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(account_name, email_id)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_job_app_emails_account_email
ON job_application_emails(account_name, email_id);
