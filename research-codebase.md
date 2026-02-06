---
date: 2026-02-06T00:29:27+0000
researcher: Claude Opus 4.6
git_commit: 1af72d0c7983e414670e62e5bb65ea2ba7a4bb38
branch: main
repository: gmail-inbox-helpper
topic: "Codebase research for migration from GitHub Actions to local macOS menu bar app"
tags: [research, codebase, migration, rumps, sqlite, github-actions, gmail-api]
status: complete
last_updated: 2026-02-06
last_updated_by: Claude Opus 4.6
---

# Research: Migration from GitHub Actions to Local macOS Menu Bar App

**Date**: 2026-02-06T00:29:27+0000
**Researcher**: Claude Opus 4.6
**Git Commit**: 1af72d0c7983e414670e62e5bb65ea2ba7a4bb38
**Branch**: main
**Repository**: gmail-inbox-helpper

## Research Question

Full codebase documentation to support the migration defined in `tasks/001-migrate-to-local-menubar-app.md`: moving from GitHub Actions + Cloudflare D1 to a locally-running macOS menu bar app with local SQLite.

## Summary

The Gmail Inbox Helper is an automated email cleanup system that processes 3 Gmail accounts. It classifies emails using OpenAI GPT-4o-mini and organizes them via the Gmail API (labeling, archiving). The system currently runs as two GitHub Actions workflows on a 6-hour cron, triggered by a Cloudflare Worker. Processed email IDs are tracked in Cloudflare D1 (serverless SQLite) to prevent duplicates.

The user has three existing macOS menu bar utilities built with `rumps` that serve as the pattern for the migration. All three follow a consistent architecture: a `rumps.App` subclass with daemon background threads, start/stop shell scripts with PID tracking, and file-based logging. The migration replaces the Cloudflare D1 REST client with a local SQLite database using the same schema, wraps the existing processing logic in a `rumps` menu bar app, and disables the GitHub Actions workflows.

---

## Detailed Findings

### 1. Source Code: Entry Points and Processing Logic

#### 1.1 Marketing Cleanup (`src/marketing_cleanup.py`)

The marketing cleanup entry point follows this flow:

1. **Configuration** — Reads `ACCOUNT_NAME`, `GMAIL_TOKEN`, `MAX_EMAILS_PER_PAGE` (default 50), `MAX_PAGES` (default 3) from environment
2. **Service Init** — Instantiates `GmailService(gmail_token)`, `EmailClassifier()`, `Database()`
3. **Label Setup** — Calls `gmail.get_or_create_label('AI Assist')` to ensure label exists
4. **Paginated Processing** — Loops up to `max_pages` pages:
   - Fetches inbox emails via `gmail.list_messages(max_results=max_emails, label_ids=['INBOX'])`
   - Checks which email IDs are already processed via `db.get_processed_marketing_ids(account_name, email_ids)`
   - For each unprocessed email:
     - Classifies via `classifier.classify_marketing(email)` → `'MARKETING'` or `'PERSONAL'`
     - Records in DB via `db.record_marketing_processed(account_name, email_id, classification)`
     - If MARKETING: adds "AI Assist" label and archives (removes INBOX label)
5. **Summary** — Prints: `Completed: {processed} processed, {skipped} skipped, {marketing_found} marketing found`

**Error handling**: `GmailTokenExpiredError` causes `sys.exit(1)`. Per-email errors are printed but processing continues. `db.close()` called in `finally` block.

#### 1.2 Job Application Cleanup (`src/job_app_cleanup.py`)

Same structure as marketing cleanup with these differences:

1. **Labels** — Creates/retrieves three labels: "Job Application", "Needs Follow-up", and looks up "AI Assist" (to skip already-classified marketing emails)
2. **Skip Logic** — Skips emails that are already in `job_application_emails` DB table OR that carry the "AI Assist" label
3. **Classification** — Uses `classifier.classify_job_application(email)` → `{'is_job_related': bool, 'needs_followup': bool}`
4. **Actions by classification**:
   - NOT job-related: recorded in DB, no Gmail actions
   - JOB_RELATED + NEEDS_FOLLOWUP: labeled "Job Application" + "Needs Follow-up", **stays in inbox**
   - JOB_RELATED + NO_FOLLOWUP: labeled "Job Application", **archived**

#### 1.3 Gmail Service (`src/gmail_service.py`)

Wraps the Gmail API v1 with these methods:

| Method | Signature | Returns |
|--------|-----------|---------|
| `__init__` | `(token_json: str)` | Creates Credentials + builds service |
| `list_messages` | `(max_results=20, query=None, page_token=None, label_ids=None)` | `{'messages': [...], 'nextPageToken': str, 'resultSizeEstimate': int}` |
| `get_message` | `(message_id: str)` | `{'id', 'threadId', 'labelIds', 'snippet', 'from', 'to', 'subject', 'date', 'body', 'isUnread'}` |
| `archive_message` | `(message_id: str)` | `bool` |
| `add_labels` | `(message_id: str, label_ids: List[str])` | `bool` |
| `get_or_create_label` | `(name: str)` | `{'labelId': str, 'created': bool}` |
| `find_label_by_name` | `(name: str)` | `{'id', 'name', 'type'}` or `None` |

**Token handling**: Accepts a JSON string, creates `google.oauth2.credentials.Credentials`, automatically refreshes if expired. Default scope: `gmail.modify`. Raises `GmailTokenExpiredError` on 401 responses or refresh failures.

**Body extraction priority**: direct body data → text/plain parts → text/html parts → None. All text sanitized to remove control characters.

#### 1.4 Classifier (`src/classifier.py`)

| Method | Input | Model | Output | Default on Error |
|--------|-------|-------|--------|------------------|
| `classify_marketing(email)` | `{from, subject, snippet, body}` (body truncated to 500 chars) | gpt-4o-mini, temp=0, max_tokens=10 | `'MARKETING'` or `'PERSONAL'` | `'PERSONAL'` |
| `classify_job_application(email)` | `{from, subject, snippet}` | gpt-4o-mini, temp=0, max_tokens=30 | `{'is_job_related': bool, 'needs_followup': bool}` | `{False, False}` |

Reads `OPENAI_API_KEY` from environment in constructor. Both methods default to the safe/conservative value on any error.

#### 1.5 Database (`src/database.py`) — THE INTERFACE TO REPLACE

Currently a REST client for Cloudflare D1. Uses `urllib.request` to POST SQL queries to the Cloudflare API.

**Constructor**: Reads `CF_ACCOUNT_ID`, `CF_D1_DATABASE_ID`, `CF_API_TOKEN` from environment. Builds base URL: `https://api.cloudflare.com/client/v4/accounts/{id}/d1/database/{id}/query`

**Interface contract (must be preserved in SQLite replacement):**

```python
class Database:
    def __init__(self):
        # Current: reads CF_* env vars, builds REST URL
        # SQLite: open local .db file

    def get_processed_marketing_ids(self, account_name: str, email_ids: List[str]) -> List[str]:
        # SQL: SELECT email_id FROM processed_emails WHERE account_name = ? AND email_id IN (?,?...)
        # Returns: list of already-processed email IDs
        # Edge case: returns [] if email_ids is empty

    def record_marketing_processed(self, account_name: str, email_id: str, classification: str):
        # SQL: INSERT INTO processed_emails (account_name, email_id, classification) VALUES (?,?,?)
        #      ON CONFLICT (account_name, email_id) DO NOTHING
        # classification: 'MARKETING' or 'PERSONAL'

    def get_processed_job_app_ids(self, account_name: str, email_ids: List[str]) -> List[str]:
        # SQL: SELECT email_id FROM job_application_emails WHERE account_name = ? AND email_id IN (?,?...)
        # Returns: list of already-processed email IDs

    def record_job_app_processed(self, account_name: str, email_id: str, is_job_related: bool, needs_followup: Optional[bool]):
        # SQL: INSERT INTO job_application_emails (account_name, email_id, is_job_related, needs_followup) VALUES (?,?,?,?)
        #      ON CONFLICT (account_name, email_id) DO NOTHING
        # is_job_related: stored as INTEGER (1/0)
        # needs_followup: stored as INTEGER (1/0) or NULL

    def close(self):
        # Current: no-op (REST has no connection)
        # SQLite: close connection
```

---

### 2. Database Schema

From `scripts/schema.sql`:

```sql
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
```

This schema is already SQLite-compatible (Cloudflare D1 is SQLite-based). It can be used directly for the local database.

---

### 3. CI/CD Infrastructure (Being Replaced)

#### 3.1 GitHub Actions Workflows

Both workflows share identical structure:

- **Cron**: `0 */6 * * *` (every 6 hours)
- **Manual trigger**: `workflow_dispatch`
- **Runner**: `ubuntu-latest`, Python 3.11
- **Matrix**: 3 accounts (`conveyour`/`CONVEYOUR`, `chri5tian`/`CHRI5TIAN`, `campbell`/`CAMPBELL`)
- **fail-fast**: `false`

**Secret mapping pattern** (dynamic per account):
```yaml
GMAIL_TOKEN: ${{ secrets[format('GMAIL_TOKEN_{0}', matrix.account.secret_suffix)] }}
```

**Feature toggle pattern** (bash indirect variable expansion):
```bash
ENABLED_VAR="ENABLE_MARKETING_${{ matrix.account.secret_suffix }}"
ENABLED="${!ENABLED_VAR:-true}"   # marketing defaults to true
ENABLED="${!ENABLED_VAR:-false}"  # job app defaults to false
```

Current toggle values:
| Toggle | conveyour | chri5tian | campbell |
|--------|-----------|-----------|---------|
| Marketing | true | true | true |
| Job App | false | true | false |

#### 3.2 Cloudflare Worker (`workers/cron-trigger/`)

- **Name**: `gmail-cleanup-cron`
- **Cron**: `0 */6 * * *`
- **Account ID**: `3c935156bf9683f48b9f259010f22622`
- **Function**: Dispatches both GitHub Actions workflows via the GitHub API
- **Workflows dispatched**: IDs `225917809` (marketing) and `225917808` (job app)
- **Auth**: `GITHUB_TOKEN` secret (set via `wrangler secret put`)
- **Endpoints**: `GET /health`, `POST /` (manual trigger), `GET /` (docs)

#### 3.3 Token Generation (`scripts/generate_token.py`)

- Scope: `https://www.googleapis.com/auth/gmail.modify`
- Requires `scripts/credentials.json` (Google OAuth Desktop app credentials)
- Uses `InstalledAppFlow.from_client_secrets_file()` with `run_local_server(port=0)`
- Outputs JSON with: `token`, `refresh_token`, `token_uri`, `client_id`, `client_secret`, `scopes`
- Output is stored as GitHub Secret `GMAIL_TOKEN_<ACCOUNT>`

---

### 4. Existing Menu Bar Watcher Patterns

Three existing watchers provide the architectural pattern:

#### 4.1 Vector Email Monitoring (`/Users/christian/Documents/GitHub/vector-email-monitoring/`)

The simplest and closest pattern to what's needed.

```python
class VectorWatcher(rumps.App):
    def __init__(self):
        super(VectorWatcher, self).__init__("Vector Watcher")
        self.icon = "/Users/christian/Documents/GitHub/vector-email-monitoring/vector_icon.png"
        self.menu = ["Status: Running", None, "Last Check: Never", None, "Quit"]
        self.service = None
        self.running = True
        self.check_thread = None

    @rumps.clicked("Quit")
    def quit_app(self, _):
        self.running = False
        rumps.quit_application()

    def check_emails(self):
        while self.running:
            try:
                # ... do work ...
                self.update_status("Running")
                self.update_last_check()
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                self.update_status("Error")
            time.sleep(900)  # 15 minutes
```

- **Env**: pyenv virtualenv `vector-email-monitoring` (Python 3.10.12)
- **rumps installed**: Yes
- **Logging**: File-only (`watcher.log`), INFO level
- **Threading**: Single daemon thread, `time.sleep()` loop
- **Config**: Hardcoded values
- **Token storage**: `token.pickle` file (persistent credentials)

#### 4.2 JobHunter Watcher (`/Users/christian/Documents/GitHub/jobhunter/`)

More sophisticated — uses `schedule` library and emoji status icons.

```python
class JobHunterWatcher(rumps.App):
    def __init__(self):
        super(JobHunterWatcher, self).__init__("JobHunter")
        self.title = "🔍"  # Emoji as menu bar icon
        self.status_item = rumps.MenuItem("Status: Idle")
        self.menu = [self.status_item, ...]
        self.is_running = False  # Concurrency guard
        self._setup_schedule()
```

- **Env**: Local `venv/` (not pyenv)
- **rumps installed**: Yes
- **Logging**: File + console (dual handlers)
- **Threading**: Scheduler thread (30s check interval) + per-operation threads
- **Scheduling**: `schedule` library — daily at 09:00 and 18:00
- **Icons**: Emoji-based (`🔍` idle, `📥` scraping, `✅` complete, `❌` error)
- **Concurrency**: `is_running` flag prevents overlapping operations
- **Notifications**: macOS notifications via `osascript`
- **Auto-reset**: `threading.Timer(60, ...)` resets status to Idle after 60s

#### 4.3 Son's PC Monitor (`/Users/christian/Documents/GitHub/sons-pc-monitor/`)

Most robust — chunked sleep, force-kill, next-check countdown.

```python
class SonsPCMonitor(rumps.App):
    def __init__(self):
        super(SonsPCMonitor, self).__init__("👁", quit_button=None)
        self.status_item = rumps.MenuItem("Status: Starting...")
        self.menu = [self.status_item, ..., rumps.MenuItem("Run Now", callback=self.run_now), ...]
```

- **Env**: Local `venv/` (not pyenv)
- **rumps installed**: Yes
- **Logging**: File (`logs/watcher.log`) + console
- **Threading**: Single daemon thread with **chunked 60s sleeps** (allows graceful shutdown)
- **Poll interval**: 86400s (24h)
- **Icons**: Emoji (`👁` OK, `🔄` running, `⚠️` issues, `❌` error)
- **Next-check timer**: Displays countdown in menu
- **Start script**: Uses `nohup`, checks for stale PID, verifies startup success
- **Stop script**: Graceful kill → force kill (`kill -9`) fallback → `pkill -f` fallback

#### 4.4 Cross-Watcher Pattern Comparison

| Aspect | Vector | JobHunter | Son's PC |
|--------|--------|-----------|----------|
| **rumps init** | String title | String title | Emoji title, `quit_button=None` |
| **Menu items** | String list | `rumps.MenuItem` objects | `rumps.MenuItem` objects |
| **Icon** | PNG file | Emoji in title | Emoji in title |
| **Background** | Single thread, long sleep | Scheduler + operation threads | Single thread, chunked sleep |
| **Logging** | File only | File + console | File + console |
| **Config** | Hardcoded | Hardcoded | Hardcoded |
| **Env type** | pyenv virtualenv | Local venv | Local venv |
| **Start script shell** | zsh | zsh | bash |
| **PID check** | Basic | `pgrep -f` | `kill -0` + stale check |
| **Stop fallback** | None | `pkill -f` | `kill -9` then `pkill -f` |

---

### 5. Local Environment Configuration

#### 5.1 Shell Aliases (`~/.zshrc` lines 64-66)

```bash
alias start-watcher='cd /Users/christian/Documents/GitHub/vector-email-monitoring && ./start_watcher.sh; cd /Users/christian/Documents/GitHub/jobhunter && ./start_jobhunter_watcher.sh; cd /Users/christian/Documents/GitHub/sons-pc-monitor && ./start_watcher.sh'

alias stop-watcher='cd /Users/christian/Documents/GitHub/vector-email-monitoring && ./stop_watcher.sh; cd /Users/christian/Documents/GitHub/jobhunter && ./stop_jobhunter_watcher.sh; cd /Users/christian/Documents/GitHub/sons-pc-monitor && ./stop_watcher.sh'
```

These chain all watchers together. The new gmail-inbox-helper watcher should be appended to both aliases.

#### 5.2 Pyenv Setup (`~/.zshrc` lines 38-41, `~/.dotfiles/bash/general.sh` lines 46-48)

```bash
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```

All pyenv environments use Python 3.10.12. There are 62 virtual environments total. The `vector-email-monitoring` watcher uses a pyenv virtualenv; the other two use local `venv/` directories.

#### 5.3 Gmail Inbox Helper `.env`

Currently contains only:
```
OPENAI_API_KEY="sk-svcacct-..."
```

#### 5.4 Gmail Inbox Helper `.gitignore`

```
__pycache__/
*.py[cod]
*$py.class
.env
venv/
.venv/
credentials.json
token.json
*.token.json
.idea/
.vscode/
*.swp
.playwright-mcp/
```

Already excludes `.env`, `venv/`, credentials, and token files. A `data/` directory for SQLite would need to be added (or the `.db` file specifically).

#### 5.5 Python Version

No `.python-version` file exists in the project. The project runs Python 3.11 in GitHub Actions. Locally, pyenv defaults to 3.10.12.

---

## Code References

- `src/marketing_cleanup.py:26-34` — Environment variable reading and validation
- `src/marketing_cleanup.py:38-48` — Service initialization (GmailService, EmailClassifier, Database)
- `src/marketing_cleanup.py:67-120` — Main paginated processing loop
- `src/job_app_cleanup.py:50-62` — Triple label setup (Job Application, Needs Follow-up, AI Assist lookup)
- `src/job_app_cleanup.py:94-100` — Skip logic (already processed + AI Assist label check)
- `src/gmail_service.py:20-50` — Constructor and credential creation with token refresh
- `src/gmail_service.py:52-91` — `list_messages()` with pagination support
- `src/gmail_service.py:173-180` — `get_or_create_label()` idempotent label management
- `src/classifier.py:15-66` — Marketing classification prompt, API call, and error default
- `src/classifier.py:68-146` — Job application classification with three-way output
- `src/database.py:13-42` — Database constructor (CF API config) and `_execute()` method
- `src/database.py:48-66` — `get_processed_marketing_ids()` with dynamic IN clause
- `src/database.py:68-79` — `record_marketing_processed()` with ON CONFLICT DO NOTHING
- `src/database.py:81-98` — `get_processed_job_app_ids()`
- `src/database.py:100-120` — `record_job_app_processed()` with bool→int conversion
- `scripts/schema.sql:1-25` — Full database schema (SQLite-compatible)
- `scripts/generate_token.py:20` — Gmail scope: `gmail.modify`
- `.github/workflows/marketing-cleanup.yml:5` — Cron: `0 */6 * * *`
- `.github/workflows/marketing-cleanup.yml:34-43` — Feature toggle bash pattern
- `workers/cron-trigger/src/index.js` — Cloudflare Worker cron trigger
- `workers/cron-trigger/wrangler.toml:7` — Worker cron: `0 */6 * * *`

## Architecture Documentation

### Current Architecture

```
Cloudflare Worker (cron: every 6h)
  ├── POST github.com/.../workflows/marketing-cleanup.yml/dispatches
  └── POST github.com/.../workflows/job-app-cleanup.yml/dispatches
        │
        ▼
GitHub Actions (ubuntu-latest, Python 3.11)
  ├── Matrix: [conveyour, chri5tian, campbell] (parallel)
  ├── Feature toggle check (bash indirect expansion)
  └── Run script:
        ├── marketing_cleanup.py  ──or──  job_app_cleanup.py
        │     │
        │     ├── GmailService(token_json)  ← GMAIL_TOKEN env var
        │     ├── EmailClassifier()         ← OPENAI_API_KEY env var
        │     ├── Database()                ← CF_* env vars
        │     │
        │     ├── gmail.list_messages(INBOX, paginated)
        │     ├── db.get_processed_*_ids(account, ids)  ← dedup check
        │     ├── classifier.classify_*(email)           ← OpenAI API
        │     ├── db.record_*_processed(...)             ← Cloudflare D1 REST
        │     ├── gmail.add_labels(...)                  ← Gmail API
        │     └── gmail.archive_message(...)             ← Gmail API
        │
        └── Cloudflare D1 (SQLite via REST API)
              ├── processed_emails table
              └── job_application_emails table
```

### Target Architecture (Local)

```
macOS Menu Bar (rumps.App)
  ├── "Run Now" button → triggers cleanup cycle
  ├── "View Logs" → opens watcher.log
  ├── Status/Last Check display
  ├── Background thread (6h interval, chunked sleep)
  │
  └── For each enabled account (sequential):
        ├── marketing_cleanup logic (if enabled)
        └── job_app_cleanup logic (if enabled)
              │
              ├── GmailService(token_json)  ← from local .env or token files
              ├── EmailClassifier()         ← OPENAI_API_KEY from .env
              ├── Database()                ← local SQLite file
              │
              └── Same Gmail API + OpenAI calls as before
                    │
                    └── Local SQLite (data/processed_emails.db)
                          ├── processed_emails table
                          └── job_application_emails table
```

### Key Architectural Differences

| Aspect | Current (GitHub Actions) | Target (Local) |
|--------|--------------------------|----------------|
| **Orchestration** | CF Worker → GitHub Actions cron | rumps menu bar app with background thread |
| **Parallelism** | 3 parallel matrix jobs | Sequential per-account processing |
| **Database** | Cloudflare D1 REST API | Local SQLite (stdlib `sqlite3`) |
| **Token storage** | GitHub Secrets (env vars) | Local files or `.env` |
| **Feature toggles** | GitHub Variables + bash expansion | Local config (`.env` or config file) |
| **Logging** | `print()` to GitHub Actions log | Python `logging` to `watcher.log` |
| **Trigger** | Cron (6h) + manual workflow_dispatch | Cron-like interval + "Run Now" menu button |
| **Error visibility** | GitHub Actions run logs | Menu bar status icon + log file |

## Open Questions

1. **Token persistence**: Should refreshed tokens be written back to disk? The current GitHub Actions approach is stateless (refresh happens in-memory each run). Locally, persisting the refreshed token avoids unnecessary refresh API calls and is more resilient to short-lived network issues.

2. **Data migration**: Start fresh with an empty local SQLite database, or export existing data from Cloudflare D1 first? Starting fresh means some emails will be reprocessed once (classified and possibly re-labeled, but ON CONFLICT prevents duplicate DB entries and re-labeling is idempotent).

3. **Python version**: GitHub Actions uses 3.11, local pyenv has 3.10.12. The code uses no 3.11-specific features, so 3.10.12 should work. Need to decide whether to use a pyenv virtualenv (like vector-email-monitoring) or a local venv (like jobhunter/sons-pc-monitor).

4. **Logging migration**: The current scripts use `print()` throughout. The local version should use `logging` module instead. This means updating all `print()` calls in `marketing_cleanup.py` and `job_app_cleanup.py` to use a logger, or wrapping the entry points to capture stdout.

5. **Cloudflare Worker**: Should it be deleted, or just left dormant? If GitHub Actions workflows are disabled (via `if: false`), the worker's dispatch calls will succeed but the workflows won't run. Alternatively, the worker cron can be removed from `wrangler.toml`.

6. **`.gitignore` update**: Should `data/*.db` or `*.db` be added to `.gitignore` to prevent committing the local SQLite database?
