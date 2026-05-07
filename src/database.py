"""Database service for tracking processed emails using local SQLite."""

import os
import sqlite3
from pathlib import Path
from typing import List, Optional


class Database:
    """Local SQLite database client."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default: data/gmail_helper.db relative to project root
            project_root = Path(__file__).parent.parent
            data_dir = project_root / 'data'
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / 'gmail_helper.db')

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                email_id TEXT NOT NULL,
                classification TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(account_name, email_id)
            );

            CREATE INDEX IF NOT EXISTS idx_processed_emails_account_email
            ON processed_emails(account_name, email_id);

            CREATE TABLE IF NOT EXISTS job_application_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                email_id TEXT NOT NULL,
                is_job_related INTEGER NOT NULL DEFAULT 0,
                needs_followup INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(account_name, email_id)
            );

            CREATE INDEX IF NOT EXISTS idx_job_app_emails_account_email
            ON job_application_emails(account_name, email_id);

            CREATE TABLE IF NOT EXISTS general_cleanup_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                email_id TEXT NOT NULL,
                classification TEXT NOT NULL,
                matched_rule TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(account_name, email_id)
            );

            CREATE INDEX IF NOT EXISTS idx_general_cleanup_account_email
            ON general_cleanup_emails(account_name, email_id);
        """)
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    # Marketing emails
    def get_processed_marketing_ids(self, account_name: str, email_ids: List[str]) -> List[str]:
        """Get IDs of emails that have already been processed."""
        if not email_ids:
            return []

        placeholders = ','.join(['?' for _ in email_ids])
        sql = f"""
            SELECT email_id FROM processed_emails
            WHERE account_name = ? AND email_id IN ({placeholders})
        """
        params = [account_name] + email_ids
        cursor = self.conn.execute(sql, params)
        return [row['email_id'] for row in cursor.fetchall()]

    def record_marketing_processed(self, account_name: str, email_id: str, classification: str):
        """Record a processed marketing email."""
        sql = """
            INSERT INTO processed_emails (account_name, email_id, classification)
            VALUES (?, ?, ?)
            ON CONFLICT (account_name, email_id) DO NOTHING
        """
        self.conn.execute(sql, [account_name, email_id, classification])
        self.conn.commit()

    # Job application emails
    def get_processed_job_app_ids(self, account_name: str, email_ids: List[str]) -> List[str]:
        """Get IDs of job app emails that have already been processed."""
        if not email_ids:
            return []

        placeholders = ','.join(['?' for _ in email_ids])
        sql = f"""
            SELECT email_id FROM job_application_emails
            WHERE account_name = ? AND email_id IN ({placeholders})
        """
        params = [account_name] + email_ids
        cursor = self.conn.execute(sql, params)
        return [row['email_id'] for row in cursor.fetchall()]

    # General cleanup emails
    def get_processed_general_ids(self, account_name: str, email_ids: List[str]) -> List[str]:
        """Get IDs of emails that have already been processed by general cleanup."""
        if not email_ids:
            return []

        placeholders = ','.join(['?' for _ in email_ids])
        sql = f"""
            SELECT email_id FROM general_cleanup_emails
            WHERE account_name = ? AND email_id IN ({placeholders})
        """
        params = [account_name] + email_ids
        cursor = self.conn.execute(sql, params)
        return [row['email_id'] for row in cursor.fetchall()]

    def record_general_processed(self, account_name: str, email_id: str, classification: str, matched_rule: str = None):
        """Record a processed general cleanup email."""
        sql = """
            INSERT INTO general_cleanup_emails (account_name, email_id, classification, matched_rule)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (account_name, email_id) DO NOTHING
        """
        self.conn.execute(sql, [account_name, email_id, classification, matched_rule])
        self.conn.commit()

    def record_job_app_processed(
        self,
        account_name: str,
        email_id: str,
        is_job_related: bool,
        needs_followup: Optional[bool]
    ):
        """Record a processed job application email."""
        sql = """
            INSERT INTO job_application_emails
            (account_name, email_id, is_job_related, needs_followup)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (account_name, email_id) DO NOTHING
        """
        self.conn.execute(sql, [
            account_name,
            email_id,
            1 if is_job_related else 0,
            1 if needs_followup else (0 if needs_followup is False else None)
        ])
        self.conn.commit()
