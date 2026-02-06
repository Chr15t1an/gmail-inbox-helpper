# Gmail Inbox Helper: Local Menu Bar App Migration — Implementation Plan

## Overview

Migrate the Gmail Inbox Helper from GitHub Actions + Cloudflare D1 to a locally-running macOS menu bar application using `rumps`. Replace all cloud infrastructure with local equivalents (SQLite, token files, `.env` config). Fully tear down the GitHub Actions workflows, Cloudflare Worker, and D1 database.

## Current State Analysis

The system runs as two GitHub Actions workflows (`marketing-cleanup.yml`, `job-app-cleanup.yml`) triggered every 6 hours by a Cloudflare Worker cron. Each workflow processes 3 Gmail accounts in parallel via matrix strategy, classifying emails with OpenAI GPT-4o-mini and tracking processed IDs in Cloudflare D1. The processing logic lives in `src/` — five Python files with clear separation: `gmail_service.py` (Gmail API), `classifier.py` (OpenAI), `database.py` (D1 REST client), and two entry points.

### Key Discoveries:
- The D1 schema (`scripts/schema.sql`) is native SQLite — zero schema changes needed
- `database.py` has a clean 5-method interface that maps directly to SQLite
- `gmail_service.py` and `classifier.py` need no changes — they don't touch env vars for DB or config
- The two cleanup scripts (`marketing_cleanup.py`, `job_app_cleanup.py`) read env vars directly and use `print()` + `sys.exit()` — they need refactoring to be callable functions with logging
- Three existing watcher apps on this machine provide the exact `rumps` pattern to follow
- `python-dotenv` is already in `requirements.txt`

## Desired End State

- A `rumps` menu bar app (`gmail_watcher.py`) running locally, showing status via emoji icon
- Clicking "Run Now" or waiting for the 6-hour timer triggers cleanup across all enabled accounts
- All processing tracked in a local SQLite database (`data/gmail_helper.db`)
- Gmail tokens stored as JSON files in `tokens/` directory
- Configuration via `.env` file (API key, toggles, intervals)
- Comprehensive logging to `watcher.log`
- Start/stop via `./start_watcher.sh` / `./stop_watcher.sh`, wired into the global `start-watcher` alias
- GitHub Actions workflows deleted, CF Worker shut down, D1 database deleted

### Verification:
1. `./start_watcher.sh` → menu bar icon appears
2. Click "Run Now" → emails get classified, labeled, archived (check Gmail)
3. `watcher.log` shows detailed per-email processing
4. Re-run → already-processed emails are skipped (SQLite dedup works)
5. `./stop_watcher.sh` → process cleanly exits
6. GitHub Actions page shows no workflows

## What We're NOT Doing

- No web UI or dashboard
- No multi-machine sync (SQLite is local-only)
- No data migration from D1 (starting fresh — re-labeling is idempotent)
- No changes to the OpenAI classification prompts or Gmail API logic
- No `schedule` library (simple sleep-based timer like Vector Watcher, not daily-at-time scheduling)
- No macOS notifications (menu bar status + log file is sufficient)

## Implementation Approach

Work bottom-up: database first (foundation), then refactor cleanup scripts to be callable, then build the watcher app on top, then shell scripts/aliases, and finally tear down the old infrastructure on a separate branch.

---

## Phase 1: Local SQLite Database Module

### Overview
Replace `src/database.py` with a drop-in SQLite implementation that preserves the exact same interface.

### Changes Required:

#### 1. Rewrite `src/database.py`
**File**: `src/database.py`
**Changes**: Complete replacement — Cloudflare D1 REST client → local SQLite

```python
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
```

#### 2. Create `data/` directory
**File**: `data/.gitkeep`
**Changes**: Create empty directory tracked by git (the `.db` file itself will be gitignored)

#### 3. Update `.gitignore`
**File**: `.gitignore`
**Changes**: Add SQLite database and token files

```
# Add after existing entries:

# Local database
data/*.db
data/*.db-journal
data/*.db-wal

# Token files
tokens/
```

### Success Criteria:

#### Automated Verification:
- [ ] Python can import the new Database: `cd src && python -c "from database import Database; db = Database(); db.close(); print('OK')"`
- [ ] Schema creates correctly: verify `data/gmail_helper.db` exists after import
- [ ] Insert + query works: quick smoke test script (provided below)

```python
# Run from project root: python -c "
import sys; sys.path.insert(0, 'src')
from database import Database
db = Database()
db.record_marketing_processed('test', 'email123', 'MARKETING')
ids = db.get_processed_marketing_ids('test', ['email123', 'email456'])
assert ids == ['email123'], f'Expected [email123], got {ids}'
db.record_job_app_processed('test', 'email789', True, True)
ids = db.get_processed_job_app_ids('test', ['email789'])
assert ids == ['email789'], f'Expected [email789], got {ids}'
db.close()
print('All database tests passed')
# "
```

#### Manual Verification:
- [ ] Confirm `data/gmail_helper.db` is created in the right location
- [ ] Confirm `.gitignore` correctly excludes the `.db` file: `git status` should not show it

**Pause here for confirmation before proceeding to Phase 2.**

---

## Phase 2: Refactor Cleanup Scripts into Callable Functions

### Overview
Convert `marketing_cleanup.py` and `job_app_cleanup.py` from standalone scripts that read env vars and call `sys.exit()` into importable functions that accept parameters and use Python `logging`. The watcher will call these functions directly.

### Changes Required:

#### 1. Refactor `src/marketing_cleanup.py`
**File**: `src/marketing_cleanup.py`
**Changes**: Extract logic into `run_marketing_cleanup()` function that accepts services and config as parameters, uses `logging` instead of `print()`, returns a result dict instead of calling `sys.exit()`.

```python
#!/usr/bin/env python3
"""Marketing email cleanup — classifies emails as MARKETING/PERSONAL, labels and archives marketing."""

import logging
from typing import Dict, Any

from gmail_service import GmailService, GmailTokenExpiredError
from classifier import EmailClassifier
from database import Database

logger = logging.getLogger(__name__)


def run_marketing_cleanup(
    gmail: GmailService,
    classifier: EmailClassifier,
    db: Database,
    account_name: str,
    max_emails: int = 50,
    max_pages: int = 3,
) -> Dict[str, Any]:
    """
    Run marketing email cleanup for a single account.

    Returns dict with keys: processed, skipped, marketing_found, error
    """
    result = {'processed': 0, 'skipped': 0, 'marketing_found': 0, 'error': None}

    # Get or create "AI Assist" label
    try:
        label_result = gmail.get_or_create_label('AI Assist')
        ai_assist_label_id = label_result['labelId']
        if label_result['created']:
            logger.info(f"[{account_name}] Created 'AI Assist' label: {ai_assist_label_id}")
    except Exception as e:
        logger.error(f"[{account_name}] Failed to get/create label: {e}")
        result['error'] = str(e)
        return result

    page_token = None
    pages_processed = 0

    try:
        while pages_processed < max_pages:
            response = gmail.list_messages(
                max_results=max_emails,
                page_token=page_token,
                label_ids=['INBOX']
            )

            emails = response['messages']
            page_token = response.get('nextPageToken')
            pages_processed += 1

            if not emails:
                logger.info(f"[{account_name}] No more emails to process (page {pages_processed})")
                break

            logger.info(f"[{account_name}] Processing page {pages_processed}: {len(emails)} emails")

            email_ids = [e['id'] for e in emails]
            already_processed = db.get_processed_marketing_ids(account_name, email_ids)

            for email in emails:
                if email['id'] in already_processed:
                    result['skipped'] += 1
                    continue

                try:
                    classification = classifier.classify_marketing(email)
                    db.record_marketing_processed(account_name, email['id'], classification)

                    if classification == 'MARKETING':
                        result['marketing_found'] += 1
                        gmail.add_labels(email['id'], [ai_assist_label_id])
                        gmail.archive_message(email['id'])
                        logger.info(f"[{account_name}]   [MARKETING] {email.get('subject', 'No subject')[:60]}")

                    result['processed'] += 1

                except GmailTokenExpiredError:
                    raise
                except Exception as e:
                    logger.error(f"[{account_name}]   Error processing {email['id']}: {e}")

            if not page_token:
                break

    except GmailTokenExpiredError as e:
        logger.error(f"[{account_name}] Gmail token expired during processing: {e}")
        result['error'] = f"Token expired: {e}"

    return result
```

#### 2. Refactor `src/job_app_cleanup.py`
**File**: `src/job_app_cleanup.py`
**Changes**: Same pattern — extract into `run_job_app_cleanup()` function.

```python
#!/usr/bin/env python3
"""Job application email cleanup — classifies job-related emails and applies labels."""

import logging
from typing import Dict, Any

from gmail_service import GmailService, GmailTokenExpiredError
from classifier import EmailClassifier
from database import Database

logger = logging.getLogger(__name__)


def run_job_app_cleanup(
    gmail: GmailService,
    classifier: EmailClassifier,
    db: Database,
    account_name: str,
    max_emails: int = 50,
    max_pages: int = 3,
) -> Dict[str, Any]:
    """
    Run job application email cleanup for a single account.

    Returns dict with keys: processed, skipped, job_related_found, needs_followup_found, error
    """
    result = {
        'processed': 0, 'skipped': 0,
        'job_related_found': 0, 'needs_followup_found': 0,
        'error': None
    }

    # Get or create labels
    try:
        job_app_label = gmail.get_or_create_label('Job Application')
        followup_label = gmail.get_or_create_label('Needs Follow-up')
        job_app_label_id = job_app_label['labelId']
        followup_label_id = followup_label['labelId']

        ai_assist = gmail.find_label_by_name('AI Assist')
        ai_assist_label_id = ai_assist['id'] if ai_assist else None
    except Exception as e:
        logger.error(f"[{account_name}] Failed to get/create labels: {e}")
        result['error'] = str(e)
        return result

    page_token = None
    pages_processed = 0

    try:
        while pages_processed < max_pages:
            response = gmail.list_messages(
                max_results=max_emails,
                page_token=page_token,
                label_ids=['INBOX']
            )

            emails = response['messages']
            page_token = response.get('nextPageToken')
            pages_processed += 1

            if not emails:
                logger.info(f"[{account_name}] No more emails to process (page {pages_processed})")
                break

            logger.info(f"[{account_name}] Processing page {pages_processed}: {len(emails)} emails")

            email_ids = [e['id'] for e in emails]
            already_processed = db.get_processed_job_app_ids(account_name, email_ids)

            for email in emails:
                if email['id'] in already_processed:
                    result['skipped'] += 1
                    continue

                if ai_assist_label_id and ai_assist_label_id in email.get('labelIds', []):
                    result['skipped'] += 1
                    continue

                try:
                    classification = classifier.classify_job_application(email)

                    db.record_job_app_processed(
                        account_name,
                        email['id'],
                        classification['is_job_related'],
                        classification['needs_followup'] if classification['is_job_related'] else None
                    )

                    result['processed'] += 1

                    if not classification['is_job_related']:
                        continue

                    gmail.add_labels(email['id'], [job_app_label_id])
                    result['job_related_found'] += 1

                    if classification['needs_followup']:
                        gmail.add_labels(email['id'], [followup_label_id])
                        result['needs_followup_found'] += 1
                        logger.info(f"[{account_name}]   [JOB:FOLLOWUP] {email.get('subject', 'No subject')[:60]}")
                    else:
                        gmail.archive_message(email['id'])
                        logger.info(f"[{account_name}]   [JOB:ARCHIVED] {email.get('subject', 'No subject')[:60]}")

                except GmailTokenExpiredError:
                    raise
                except Exception as e:
                    logger.error(f"[{account_name}]   Error processing {email['id']}: {e}")

            if not page_token:
                break

    except GmailTokenExpiredError as e:
        logger.error(f"[{account_name}] Gmail token expired during processing: {e}")
        result['error'] = f"Token expired: {e}"

    return result
```

### Success Criteria:

#### Automated Verification:
- [ ] Both modules import without error: `cd src && python -c "from marketing_cleanup import run_marketing_cleanup; from job_app_cleanup import run_job_app_cleanup; print('OK')"`
- [ ] No `sys.exit()` calls remain in either file
- [ ] No `os.environ` calls remain in either file
- [ ] No bare `print()` calls remain — all output goes through `logging`

#### Manual Verification:
- [ ] Review both files to confirm the processing logic is identical to the original (same label names, same classification flow, same archive/skip behavior)

**Pause here for confirmation before proceeding to Phase 3.**

---

## Phase 3: Local Configuration and Token Loading

### Overview
Set up `.env`-based configuration, token file loading from `tokens/` directory, and an account configuration structure.

### Changes Required:

#### 1. Create `src/config.py`
**File**: `src/config.py` (new file)
**Changes**: Configuration loader that reads `.env` and token files

```python
"""Local configuration for Gmail Inbox Helper."""

import json
import os
from pathlib import Path
from dotenv import load_dotenv


# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / '.env')


# Account definitions
ACCOUNTS = [
    {'name': 'conveyour', 'email': 'christianc@conveyour.com', 'token_file': 'conveyour.json'},
    {'name': 'chri5tian', 'email': 'hello@chri5tian.com', 'token_file': 'chri5tian.json'},
    {'name': 'campbell', 'email': 'campbellchristian36@gmail.com', 'token_file': 'campbell.json'},
]

# Feature toggles (read from .env, default to current GitHub Variable values)
ENABLE_MARKETING_CONVEYOUR = os.environ.get('ENABLE_MARKETING_CONVEYOUR', 'true').lower() == 'true'
ENABLE_MARKETING_CHRI5TIAN = os.environ.get('ENABLE_MARKETING_CHRI5TIAN', 'true').lower() == 'true'
ENABLE_MARKETING_CAMPBELL = os.environ.get('ENABLE_MARKETING_CAMPBELL', 'true').lower() == 'true'
ENABLE_JOBAPP_CONVEYOUR = os.environ.get('ENABLE_JOBAPP_CONVEYOUR', 'false').lower() == 'true'
ENABLE_JOBAPP_CHRI5TIAN = os.environ.get('ENABLE_JOBAPP_CHRI5TIAN', 'true').lower() == 'true'
ENABLE_JOBAPP_CAMPBELL = os.environ.get('ENABLE_JOBAPP_CAMPBELL', 'false').lower() == 'true'

# Processing limits
MAX_EMAILS_PER_PAGE = int(os.environ.get('MAX_EMAILS_PER_PAGE', '50'))
MAX_PAGES = int(os.environ.get('MAX_PAGES', '3'))

# Watcher interval in seconds (default: 6 hours)
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', str(6 * 60 * 60)))

# Token directory
TOKENS_DIR = PROJECT_ROOT / 'tokens'


def get_feature_toggles():
    """Return dict of {account_name: {marketing: bool, jobapp: bool}}."""
    return {
        'conveyour': {
            'marketing': ENABLE_MARKETING_CONVEYOUR,
            'jobapp': ENABLE_JOBAPP_CONVEYOUR,
        },
        'chri5tian': {
            'marketing': ENABLE_MARKETING_CHRI5TIAN,
            'jobapp': ENABLE_JOBAPP_CHRI5TIAN,
        },
        'campbell': {
            'marketing': ENABLE_MARKETING_CAMPBELL,
            'jobapp': ENABLE_JOBAPP_CAMPBELL,
        },
    }


def load_token(account_name: str) -> str:
    """Load token JSON string from tokens/ directory.

    Returns the JSON string (same format GmailService expects).
    Raises FileNotFoundError if token file missing.
    """
    for account in ACCOUNTS:
        if account['name'] == account_name:
            token_path = TOKENS_DIR / account['token_file']
            if not token_path.exists():
                raise FileNotFoundError(
                    f"Token file not found: {token_path}\n"
                    f"Run: python scripts/generate_token.py\n"
                    f"Then save output to: {token_path}"
                )
            return token_path.read_text()

    raise ValueError(f"Unknown account: {account_name}")
```

#### 2. Create `tokens/` directory
**File**: `tokens/.gitkeep`
**Changes**: Empty directory for token files. Already covered by `tokens/` in `.gitignore` from Phase 1.

#### 3. Expand `.env` with full local config
**File**: `.env`
**Changes**: Add all configuration (user will need to populate token file paths after generating tokens)

```
# OpenAI
OPENAI_API_KEY="sk-svcacct-..."  # (existing value stays)

# Feature toggles (true/false)
ENABLE_MARKETING_CONVEYOUR=true
ENABLE_MARKETING_CHRI5TIAN=true
ENABLE_MARKETING_CAMPBELL=true
ENABLE_JOBAPP_CONVEYOUR=false
ENABLE_JOBAPP_CHRI5TIAN=true
ENABLE_JOBAPP_CAMPBELL=false

# Processing limits
MAX_EMAILS_PER_PAGE=50
MAX_PAGES=3

# Watcher interval in seconds (21600 = 6 hours)
CHECK_INTERVAL=21600
```

### Success Criteria:

#### Automated Verification:
- [ ] Config loads: `cd src && python -c "from config import ACCOUNTS, get_feature_toggles, MAX_EMAILS_PER_PAGE; print(get_feature_toggles()); print('OK')"`
- [ ] Token loading fails gracefully without token files: `cd src && python -c "from config import load_token; load_token('conveyour')"` should raise `FileNotFoundError` with helpful message

#### Manual Verification:
- [ ] Verify `.env` contains all expected keys
- [ ] Verify `tokens/` directory exists and is gitignored

**Pause here for confirmation before proceeding to Phase 4.**

---

## Phase 4: Menu Bar Watcher App

### Overview
Build `gmail_watcher.py` — the `rumps.App` that ties everything together. Follows the Son's PC Monitor pattern (most robust) with emoji icons and `rumps.MenuItem` objects.

### Changes Required:

#### 1. Create `gmail_watcher.py`
**File**: `gmail_watcher.py` (project root, not in `src/`)
**Changes**: New file — the main application

```python
#!/usr/bin/env python3
"""Gmail Inbox Helper — macOS menu bar watcher."""

import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import rumps

# Add src/ to path so we can import project modules
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from config import (
    ACCOUNTS, CHECK_INTERVAL, MAX_EMAILS_PER_PAGE, MAX_PAGES,
    get_feature_toggles, load_token,
)
from gmail_service import GmailService, GmailTokenExpiredError
from classifier import EmailClassifier
from database import Database

# Logging setup
LOG_FILE = PROJECT_ROOT / 'watcher.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class GmailWatcher(rumps.App):
    def __init__(self):
        super(GmailWatcher, self).__init__("Gmail", quit_button=None)
        self.title = "\U0001F4EC"  # 📬

        self.status_item = rumps.MenuItem("Status: Idle")
        self.last_run_item = rumps.MenuItem("Last Run: Never")
        self.next_run_item = rumps.MenuItem("Next Run: Calculating...")

        self.menu = [
            self.status_item,
            self.last_run_item,
            self.next_run_item,
            None,
            rumps.MenuItem("Run Now", callback=self.run_now),
            rumps.MenuItem("View Logs", callback=self.view_logs),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        self.running = True
        self.is_processing = False
        self.next_run_time = None

        self.start_polling()

    def start_polling(self):
        thread = threading.Thread(target=self.poll_loop, daemon=True)
        thread.start()

    def poll_loop(self):
        # Run immediately on start
        self.run_cleanup()

        while self.running:
            self.next_run_time = time.time() + CHECK_INTERVAL
            self.update_next_run()

            # Sleep in 60s chunks for responsive shutdown
            remaining = CHECK_INTERVAL
            while remaining > 0 and self.running:
                time.sleep(min(60, remaining))
                remaining -= 60
                self.update_next_run()

            if self.running:
                self.run_cleanup()

    def run_now(self, _):
        if self.is_processing:
            rumps.alert("Already Running", "A cleanup cycle is already in progress.")
            return
        thread = threading.Thread(target=self.run_cleanup, daemon=True)
        thread.start()

    def run_cleanup(self):
        if self.is_processing:
            return
        self.is_processing = True
        self.title = "\U0001F504"  # 🔄
        self.status_item.title = "Status: Running..."

        logger.info("=" * 60)
        logger.info("Starting cleanup cycle")
        logger.info("=" * 60)

        toggles = get_feature_toggles()
        db = Database()
        has_errors = False

        try:
            classifier = EmailClassifier()
        except Exception as e:
            logger.error(f"Failed to initialize classifier: {e}")
            self.title = "\u274C"  # ❌
            self.status_item.title = "Status: Error (classifier)"
            self.is_processing = False
            return

        for account in ACCOUNTS:
            name = account['name']
            account_toggles = toggles.get(name, {})

            # Load token
            try:
                token_json = load_token(name)
            except FileNotFoundError as e:
                logger.warning(f"[{name}] Skipping — no token file: {e}")
                continue

            # Init Gmail service
            try:
                gmail = GmailService(token_json)
            except GmailTokenExpiredError as e:
                logger.error(f"[{name}] Token expired: {e}")
                has_errors = True
                continue
            except Exception as e:
                logger.error(f"[{name}] Failed to init Gmail service: {e}")
                has_errors = True
                continue

            # Marketing cleanup
            if account_toggles.get('marketing', False):
                logger.info(f"[{name}] Running marketing cleanup...")
                from marketing_cleanup import run_marketing_cleanup
                result = run_marketing_cleanup(
                    gmail, classifier, db, name,
                    max_emails=MAX_EMAILS_PER_PAGE, max_pages=MAX_PAGES,
                )
                logger.info(
                    f"[{name}] Marketing: {result['processed']} processed, "
                    f"{result['skipped']} skipped, {result['marketing_found']} marketing archived"
                )
                if result.get('error'):
                    has_errors = True
            else:
                logger.info(f"[{name}] Marketing cleanup disabled")

            # Job app cleanup
            if account_toggles.get('jobapp', False):
                logger.info(f"[{name}] Running job app cleanup...")
                from job_app_cleanup import run_job_app_cleanup
                result = run_job_app_cleanup(
                    gmail, classifier, db, name,
                    max_emails=MAX_EMAILS_PER_PAGE, max_pages=MAX_PAGES,
                )
                logger.info(
                    f"[{name}] Job apps: {result['processed']} processed, "
                    f"{result['skipped']} skipped, {result['job_related_found']} job-related, "
                    f"{result['needs_followup_found']} need follow-up"
                )
                if result.get('error'):
                    has_errors = True
            else:
                logger.info(f"[{name}] Job app cleanup disabled")

        db.close()

        now = datetime.now()
        self.last_run_item.title = f"Last Run: {now.strftime('%m/%d %H:%M')}"

        if has_errors:
            self.title = "\u26A0\uFE0F"  # ⚠️
            self.status_item.title = "Status: Completed with errors"
        else:
            self.title = "\U0001F4EC"  # 📬
            self.status_item.title = "Status: Idle"

        logger.info("Cleanup cycle complete")
        logger.info("=" * 60)
        self.is_processing = False

    def update_next_run(self):
        if self.next_run_time:
            remaining = self.next_run_time - time.time()
            if remaining > 0:
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                if hours > 0:
                    self.next_run_item.title = f"Next Run: {hours}h {minutes}m"
                else:
                    self.next_run_item.title = f"Next Run: {minutes}m"
            else:
                self.next_run_item.title = "Next Run: Now"

    def view_logs(self, _):
        subprocess.run(['open', str(LOG_FILE)])

    def quit_app(self, _):
        logger.info("Quitting Gmail Watcher")
        self.running = False
        rumps.quit_application()


def main():
    logger.info("Starting Gmail Inbox Helper watcher")
    app = GmailWatcher()
    app.run()


if __name__ == '__main__':
    main()
```

#### 2. Update `requirements.txt`
**File**: `requirements.txt`
**Changes**: Add `rumps`

```
google-api-python-client==2.114.0
google-auth==2.27.0
google-auth-oauthlib==1.2.0
openai>=1.30.0
python-dotenv==1.0.1
rumps>=0.4.0
```

### Success Criteria:

#### Automated Verification:
- [ ] Import succeeds: `python -c "import rumps; print('rumps OK')"`
- [ ] Config + watcher module loads: `python -c "from gmail_watcher import GmailWatcher; print('OK')"` (will fail without display, but no import error)

#### Manual Verification:
- [ ] Run `python gmail_watcher.py` directly — menu bar icon appears (📬)
- [ ] Click "Run Now" — processing starts (visible in terminal logging and menu status changes to 🔄)
- [ ] Processing completes — icon returns to 📬 (or ⚠️ if errors)
- [ ] "View Logs" opens `watcher.log` in default text editor
- [ ] "Quit" exits the app cleanly
- [ ] `watcher.log` contains detailed per-account, per-email processing output
- [ ] Next Run countdown displays correctly in the menu

**Pause here for confirmation before proceeding to Phase 5.**

---

## Phase 5: Start/Stop Scripts, venv, and Alias

### Overview
Create the shell scripts, set up the virtual environment, and wire into the global `start-watcher`/`stop-watcher` alias chain.

### Changes Required:

#### 1. Create `start_watcher.sh`
**File**: `start_watcher.sh` (project root)

```bash
#!/bin/bash
#
# start_watcher.sh - Start the Gmail Inbox Helper menu bar watcher
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if already running
if [ -f watcher.pid ]; then
    PID=$(cat watcher.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "Gmail watcher is already running with PID $PID"
        exit 0
    else
        echo "Stale PID file found, cleaning up..."
        rm watcher.pid
    fi
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Run:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Start watcher
echo "Starting Gmail Inbox Helper watcher..."
source venv/bin/activate
nohup python3 gmail_watcher.py > /dev/null 2>&1 &
PID=$!
echo $PID > watcher.pid

# Verify startup
sleep 2
if kill -0 "$PID" 2>/dev/null; then
    echo "✓ Gmail watcher started with PID $PID"
    echo "  Look for 📬 icon in your menu bar"
    echo "  Logs: watcher.log"
    echo "  To stop: ./stop_watcher.sh"
else
    echo "✗ Gmail watcher failed to start. Check watcher.log"
    rm -f watcher.pid
    exit 1
fi
```

#### 2. Create `stop_watcher.sh`
**File**: `stop_watcher.sh` (project root)

```bash
#!/bin/bash
#
# stop_watcher.sh - Stop the Gmail Inbox Helper menu bar watcher
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f watcher.pid ]; then
    PID=$(cat watcher.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping Gmail watcher (PID $PID)..."
        kill "$PID"
        sleep 1

        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            echo "Force killing..."
            kill -9 "$PID" 2>/dev/null
        fi

        rm watcher.pid
        echo "✓ Gmail watcher stopped"
    else
        echo "Gmail watcher process not running (stale PID file)"
        rm watcher.pid
    fi
else
    # Try to find and kill by process name
    PIDS=$(pgrep -f "python.*gmail_watcher.py" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "Found Gmail watcher process(es): $PIDS"
        echo "Stopping..."
        kill $PIDS 2>/dev/null
        echo "✓ Gmail watcher stopped"
    else
        echo "Gmail watcher is not running"
    fi
fi
```

#### 3. Make scripts executable
```bash
chmod +x start_watcher.sh stop_watcher.sh
```

#### 4. Create virtual environment and install dependencies
```bash
cd /Users/christian/Documents/GitHub/gmail-inbox-helpper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 5. Update `~/.zshrc` aliases
**File**: `~/.zshrc`
**Changes**: Append gmail-inbox-helpper to the existing `start-watcher` and `stop-watcher` alias chains

Current (lines 64-66):
```bash
alias start-watcher='cd /Users/christian/Documents/GitHub/vector-email-monitoring && ./start_watcher.sh; cd /Users/christian/Documents/GitHub/jobhunter && ./start_jobhunter_watcher.sh; cd /Users/christian/Documents/GitHub/sons-pc-monitor && ./start_watcher.sh'
alias stop-watcher='cd /Users/christian/Documents/GitHub/vector-email-monitoring && ./stop_watcher.sh; cd /Users/christian/Documents/GitHub/jobhunter && ./stop_jobhunter_watcher.sh; cd /Users/christian/Documents/GitHub/sons-pc-monitor && ./stop_watcher.sh'
```

Updated:
```bash
alias start-watcher='cd /Users/christian/Documents/GitHub/vector-email-monitoring && ./start_watcher.sh; cd /Users/christian/Documents/GitHub/jobhunter && ./start_jobhunter_watcher.sh; cd /Users/christian/Documents/GitHub/sons-pc-monitor && ./start_watcher.sh; cd /Users/christian/Documents/GitHub/gmail-inbox-helpper && ./start_watcher.sh'
alias stop-watcher='cd /Users/christian/Documents/GitHub/vector-email-monitoring && ./stop_watcher.sh; cd /Users/christian/Documents/GitHub/jobhunter && ./stop_jobhunter_watcher.sh; cd /Users/christian/Documents/GitHub/sons-pc-monitor && ./stop_watcher.sh; cd /Users/christian/Documents/GitHub/gmail-inbox-helpper && ./stop_watcher.sh'
```

#### 6. Add shell script artifacts to `.gitignore`
**File**: `.gitignore`
**Changes**: Add PID file and log file

```
# Add after existing entries:

# Watcher runtime files
watcher.pid
watcher.log
```

### Success Criteria:

#### Automated Verification:
- [ ] Scripts are executable: `ls -la start_watcher.sh stop_watcher.sh` shows `x` permission
- [ ] venv exists: `ls venv/bin/python`
- [ ] Dependencies installed: `venv/bin/python -c "import rumps, openai, dotenv; print('All deps OK')"`

#### Manual Verification:
- [ ] `./start_watcher.sh` → 📬 appears in menu bar, PID file created
- [ ] `./stop_watcher.sh` → app exits, PID file removed
- [ ] Run `./start_watcher.sh` twice → second call says "already running"
- [ ] `source ~/.zshrc && start-watcher` starts all watchers including gmail
- [ ] `stop-watcher` stops all watchers including gmail

**Pause here for confirmation before proceeding to Phase 6.**

---

## Phase 6: CI/CD Teardown (Separate Branch)

### Overview
Full cleanup of all cloud infrastructure. This is done on a **separate branch** (`cleanup/remove-cloud-infra`) and merged via PR to keep the teardown isolated and reviewable.

### Changes Required:

#### 1. Create branch
```bash
git checkout -b cleanup/remove-cloud-infra
```

#### 2. Delete GitHub Actions workflow files
```bash
rm .github/workflows/marketing-cleanup.yml
rm .github/workflows/job-app-cleanup.yml
rmdir .github/workflows
rmdir .github
```

#### 3. Delete Cloudflare Worker directory
```bash
rm -rf workers/
```

#### 4. Delete the old schema file (schema is now embedded in `database.py`)
```bash
rm scripts/schema.sql
```
Keep `scripts/generate_token.py` and `scripts/credentials.json` — still needed for token generation.

#### 5. Clean up README.md
**File**: `README.md`
**Changes**: Update to reflect local-only operation. Remove GitHub Actions setup instructions, Cloudflare D1 setup, GitHub Secrets/Variables sections. Replace with local setup instructions.

Key sections to update:
- Remove "Scheduled Execution" mention of GitHub Actions
- Remove "Create Cloudflare D1 Database" section
- Remove "Configure GitHub Secrets" section
- Remove "Configure GitHub Variables" section
- Update "Manual Trigger" to reference the menu bar app
- Add "Local Setup" section: venv, pip install, generate tokens, start watcher
- Update "Cost Estimates" to remove GitHub Actions and Cloudflare

#### 6. Remove TOKEN-REFRESH-RUNBOOK.md reference to GitHub Secrets
**File**: `TOKEN-REFRESH-RUNBOOK.md`
**Changes**: Update Step 3 from "Update GitHub Secret" to "Save to tokens/ directory". Remove `gh secret set` commands. Update the verification step to use `./start_watcher.sh` and "Run Now" instead of `gh workflow run`.

#### 7. Manual cloud teardown steps (not automated in code)

These are manual actions the user performs in browser/CLI:

**GitHub:**
- [ ] Go to repo Settings → Secrets → Actions → Delete all secrets: `GMAIL_TOKEN_CONVEYOUR`, `GMAIL_TOKEN_CHRI5TIAN`, `GMAIL_TOKEN_CAMPBELL`, `OPENAI_API_KEY`, `CF_ACCOUNT_ID`, `CF_D1_DATABASE_ID`, `CF_API_TOKEN`
- [ ] Go to repo Settings → Variables → Actions → Delete all variables: `ENABLE_MARKETING_*`, `ENABLE_JOBAPP_*`

**Cloudflare:**
- [ ] Delete the Cloudflare Worker: `npx wrangler delete gmail-cleanup-cron` (or via Dashboard → Workers → gmail-cleanup-cron → Delete)
- [ ] Delete the D1 database: `npx wrangler d1 delete gmail-inbox-helper` (or via Dashboard → D1 → gmail-inbox-helper → Delete)
- [ ] Remove the `GITHUB_TOKEN` secret from the worker: (will be gone when worker is deleted)

#### 8. Commit and create PR
```bash
git add -A
git commit -m "Remove cloud infrastructure (GitHub Actions, CF Worker, D1)"
gh pr create --title "Remove cloud infrastructure" --body "..."
```

### Success Criteria:

#### Automated Verification:
- [ ] No `.github/` directory: `ls .github 2>&1` should fail
- [ ] No `workers/` directory: `ls workers 2>&1` should fail
- [ ] No `scripts/schema.sql`: `ls scripts/schema.sql 2>&1` should fail
- [ ] `scripts/generate_token.py` still exists

#### Manual Verification:
- [ ] GitHub Actions tab shows no workflows (after merge)
- [ ] Cloudflare Dashboard shows no `gmail-cleanup-cron` worker
- [ ] Cloudflare Dashboard shows no `gmail-inbox-helper` D1 database
- [ ] GitHub repo Settings → Secrets shows no leftover secrets
- [ ] GitHub repo Settings → Variables shows no leftover variables
- [ ] Local watcher still runs correctly after merge (no regressions)

---

## Token Setup (One-Time, Post-Migration)

After the code migration is complete, tokens need to be generated and saved locally:

```bash
cd /Users/christian/Documents/GitHub/gmail-inbox-helpper
source venv/bin/activate
python scripts/generate_token.py
# Sign in as christianc@conveyour.com → save output to tokens/conveyour.json
python scripts/generate_token.py
# Sign in as hello@chri5tian.com → save output to tokens/chri5tian.json
python scripts/generate_token.py
# Sign in as campbellchristian36@gmail.com → save output to tokens/campbell.json
```

---

## File Inventory Summary

### New files:
| File | Phase | Purpose |
|------|-------|---------|
| `gmail_watcher.py` | 4 | Main menu bar app |
| `src/config.py` | 3 | Configuration loader |
| `start_watcher.sh` | 5 | Start script |
| `stop_watcher.sh` | 5 | Stop script |
| `data/.gitkeep` | 1 | SQLite database directory |
| `tokens/.gitkeep` | 3 | Token files directory |

### Modified files:
| File | Phase | Changes |
|------|-------|---------|
| `src/database.py` | 1 | Complete rewrite: Cloudflare D1 → SQLite |
| `src/marketing_cleanup.py` | 2 | Refactor: standalone script → callable function with logging |
| `src/job_app_cleanup.py` | 2 | Refactor: standalone script → callable function with logging |
| `.env` | 3 | Add feature toggles and config |
| `.gitignore` | 1, 5 | Add `data/*.db`, `tokens/`, `watcher.pid`, `watcher.log` |
| `requirements.txt` | 4 | Add `rumps>=0.4.0` |
| `~/.zshrc` | 5 | Append to start-watcher / stop-watcher aliases |

### Deleted files (Phase 6, separate branch):
| File | Reason |
|------|--------|
| `.github/workflows/marketing-cleanup.yml` | Replaced by local watcher |
| `.github/workflows/job-app-cleanup.yml` | Replaced by local watcher |
| `workers/cron-trigger/` (entire directory) | Replaced by local watcher |
| `scripts/schema.sql` | Schema now embedded in `database.py._init_schema()` |

### Unchanged files:
| File | Why |
|------|-----|
| `src/gmail_service.py` | No changes needed — accepts token JSON string, works as-is |
| `src/classifier.py` | No changes needed — reads OPENAI_API_KEY from env (loaded by dotenv) |
| `src/__init__.py` | Package init, unchanged |
| `scripts/generate_token.py` | Still needed for generating token files |

---

## References

- Task definition: `tasks/001-migrate-to-local-menubar-app.md`
- Research document: `research-codebase.md`
- Watcher patterns: Vector (`/Users/christian/Documents/GitHub/vector-email-monitoring/watcher.py`), JobHunter (`/Users/christian/Documents/GitHub/jobhunter/jobhunter_watcher.py`), Son's PC (`/Users/christian/Documents/GitHub/sons-pc-monitor/watcher.py`)
- Database schema: `scripts/schema.sql`
