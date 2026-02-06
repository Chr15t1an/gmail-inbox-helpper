# Task: Migrate Gmail Inbox Helper from GitHub Actions to Local macOS Menu Bar App

## Goal / Objective

Migrate the Gmail Inbox Helper from GitHub Actions to a locally-running macOS menu bar application using `rumps`, following the established pattern of the user's other local utilities (Vector Email Monitoring, JobHunter Watcher, Son's PC Monitor). Replace Cloudflare D1 with local SQLite for processed email tracking. Disable the GitHub Actions workflows. Provide comprehensive logging and a menu bar interface to trigger runs and view status.

---

## Details & Context

### Current Architecture (GitHub Actions)

The project currently runs as two GitHub Actions workflows on a 6-hour cron:

**Workflows:**
- `.github/workflows/marketing-cleanup.yml` — classifies emails as MARKETING/PERSONAL via OpenAI, labels + archives marketing
- `.github/workflows/job-app-cleanup.yml` — classifies job-related emails, labels + archives

**Source files (`src/`):**
| File | Purpose |
|---|---|
| `marketing_cleanup.py` | Main marketing email processing entry point |
| `job_app_cleanup.py` | Main job application processing entry point |
| `gmail_service.py` | Gmail API wrapper (OAuth token refresh, list/get/archive/label) |
| `classifier.py` | OpenAI GPT-4o-mini classification (marketing + job app) |
| `database.py` | Cloudflare D1 REST API client for tracking processed emails |

**Current database (Cloudflare D1 — to be replaced):**

```sql
-- From scripts/schema.sql
CREATE TABLE processed_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    email_id TEXT NOT NULL,
    classification TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(account_name, email_id)
);

CREATE INDEX idx_processed_emails_account_email
ON processed_emails(account_name, email_id);

CREATE TABLE job_application_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL,
    email_id TEXT NOT NULL,
    is_job_related INTEGER NOT NULL DEFAULT 0,
    needs_followup INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(account_name, email_id)
);

CREATE INDEX idx_job_app_emails_account_email
ON job_application_emails(account_name, email_id);
```

**Accounts processed (3 accounts in parallel via matrix strategy):**
| Account Name | Email | Token Secret |
|---|---|---|
| conveyour | christianc@conveyour.com | `GMAIL_TOKEN_CONVEYOUR` |
| chri5tian | hello@chri5tian.com | `GMAIL_TOKEN_CHRI5TIAN` |
| campbell | campbellchristian36@gmail.com | `GMAIL_TOKEN_CAMPBELL` |

**Per-account feature toggles (currently GitHub Variables):**
| Variable | Value |
|---|---|
| `ENABLE_MARKETING_CONVEYOUR` | `true` |
| `ENABLE_MARKETING_CHRI5TIAN` | `true` |
| `ENABLE_MARKETING_CAMPBELL` | `true` |
| `ENABLE_JOBAPP_CONVEYOUR` | `false` |
| `ENABLE_JOBAPP_CHRI5TIAN` | `true` |
| `ENABLE_JOBAPP_CAMPBELL` | `false` |

**Environment variables currently needed:**
```
ACCOUNT_NAME, GMAIL_TOKEN, OPENAI_API_KEY,
CF_ACCOUNT_ID, CF_D1_DATABASE_ID, CF_API_TOKEN,
MAX_EMAILS_PER_PAGE (default: 50), MAX_PAGES (default: 3)
```

### Existing Menu Bar Utility Pattern to Follow

The user has an established pattern for macOS menu bar utilities using `rumps`. The canonical example is the Vector Email Monitoring watcher:

**Pattern: `rumps.App` subclass with threaded background work**

```python
# From /Users/christian/Documents/GitHub/vector-email-monitoring/watcher.py
class VectorWatcher(rumps.App):
    def __init__(self):
        super(VectorWatcher, self).__init__("Vector Watcher")
        self.icon = "/path/to/icon.png"
        self.menu = ["Status: Running", None, "Last Check: Never", None, "Quit"]
        self.running = True

    @rumps.clicked("Quit")
    def quit_app(self, _):
        rumps.quit_application()

    def check_emails(self):
        while self.running:
            # ... do work ...
            time.sleep(900)

def main():
    app = VectorWatcher()
    app.check_thread = threading.Thread(target=app.check_emails)
    app.check_thread.daemon = True
    app.check_thread.start()
    app.run()
```

**Pattern: start/stop shell scripts with PID tracking**

```bash
# start_watcher.sh
#!/bin/zsh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
export PATH="$PYENV_ROOT/shims:$PATH"
export PYENV_SHELL=zsh
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv activate <env-name>
python3 watcher.py &
WATCHER_PID=$!
echo $WATCHER_PID > watcher.pid
echo "Watcher started with PID: $WATCHER_PID"
```

```bash
# stop_watcher.sh
#!/bin/zsh
if [ -f watcher.pid ]; then
    WATCHER_PID=$(cat watcher.pid)
    if ps -p $WATCHER_PID > /dev/null; then
        kill $WATCHER_PID
        echo "Watcher stopped (PID: $WATCHER_PID)"
    else
        echo "Watcher is not running"
    fi
    rm watcher.pid
else
    echo "No watcher process found"
fi
```

**Pattern: aliases in `~/.zshrc` for start/stop**
```bash
# Existing alias pattern:
alias start-watcher='cd /path/to/project && ./start_watcher.sh; ...'
alias stop-watcher='cd /path/to/project && ./stop_watcher.sh; ...'
```

**Pattern: logging to file**
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='watcher.log'
)
```

### Token Storage (Local)

Currently tokens are stored as JSON in GitHub Secrets. For local operation, tokens should be stored as `token.pickle` or JSON files per account (following the existing `generate_token.py` flow which already runs locally). The existing `gmail_service.py` accepts a token JSON string — this can be adapted to read from local files.

### Cloudflare Worker Cron Trigger

There is also a Cloudflare Worker (`workers/cron-trigger/`) that dispatches GitHub Actions workflows. This should be disabled or noted as deprecated alongside the GitHub Actions workflows.

---

## Deliverables

### 1. Local SQLite Database Module
- Replace `src/database.py` (Cloudflare D1 REST client) with a local SQLite implementation
- Use the same schema from `scripts/schema.sql`
- Store the database file locally (e.g., `data/processed_emails.db`)
- Maintain the same interface methods: `get_processed_marketing_ids()`, `record_marketing_processed()`, `get_processed_job_app_ids()`, `record_job_app_processed()`

### 2. macOS Menu Bar App (`watcher.py` or `gmail_watcher.py`)
- `rumps.App` subclass following the Vector Watcher pattern
- Menu items:
  - Status indicator (Idle / Running / Error)
  - Last check timestamp
  - "Run Now" button — manually trigger a full cleanup cycle
  - "View Logs" — open the log file
  - Separator
  - Per-account status or summary
  - Quit
- Background thread running the cleanup on a configurable interval (default: every 6 hours to match current schedule)
- Process all 3 accounts sequentially (no need for matrix parallelism locally)
- Respect per-account feature toggles (can be moved to a local config file or `.env`)

### 3. Comprehensive Logging
- File-based logging (`watcher.log`) following existing pattern
- Log levels: INFO for normal operations, WARNING for skipped items, ERROR for failures
- Log each run: start time, account being processed, emails found, classifications made, actions taken (labeled, archived), errors encountered
- Include summary at end of each run (e.g., "Processed 47 emails: 32 marketing archived, 15 personal kept")
- "View Logs" menu item to open the log file

### 4. Local Configuration
- `.env` file or config file for:
  - `OPENAI_API_KEY`
  - Token file paths per account (or token JSON directly)
  - Per-account feature toggles
  - `MAX_EMAILS_PER_PAGE` (default: 50)
  - `MAX_PAGES` (default: 3)
  - Check interval (default: 6 hours)

### 5. Start/Stop Scripts
- `start_watcher.sh` — activate pyenv env, launch in background, save PID
- `stop_watcher.sh` — read PID file, kill process, clean up

### 6. Shell Alias
- Add to the existing `start-watcher` / `stop-watcher` alias chain in `~/.zshrc`

### 7. Disable GitHub Actions
- Disable or remove the two workflow files (or add `if: false` to prevent runs)
- Note the Cloudflare Worker cron trigger (`workers/cron-trigger/`) as deprecated

### 8. Update Existing Scripts
- Modify `marketing_cleanup.py` and `job_app_cleanup.py` to work with local SQLite instead of Cloudflare D1
- Modify `gmail_service.py` to load tokens from local files instead of environment variables (or keep env var support and load from `.env`)

---

## Success Criteria

1. Running `./start_watcher.sh` launches a menu bar app that appears in the macOS status bar
2. Clicking "Run Now" in the menu triggers a full cleanup cycle across all enabled accounts
3. The cleanup cycle correctly classifies and archives marketing emails (same behavior as GitHub Actions version)
4. The cleanup cycle correctly classifies and labels job application emails (same behavior as GitHub Actions version)
5. Processed emails are tracked in local SQLite — no duplicates on re-runs
6. `watcher.log` contains detailed, readable logs showing what happened during each run and why
7. Errors (expired tokens, API failures, network issues) are logged clearly and surface in the menu bar status
8. `./stop_watcher.sh` cleanly stops the watcher
9. GitHub Actions workflows no longer trigger on cron

---

## Notes / References

- **Existing watcher examples to reference:**
  - `/Users/christian/Documents/GitHub/vector-email-monitoring/watcher.py` (closest pattern)
  - `/Users/christian/Documents/GitHub/jobhunter/jobhunter_watcher.py` (has scheduling features)
  - `/Users/christian/Documents/GitHub/sons-pc-monitor/watcher.py` (has status icons)
- **Python `rumps` library** is already used across the other watchers — should already be available in the pyenv environment or installable via pip
- **Token refresh**: The existing `gmail_service.py` handles token refresh automatically. For local operation with tokens stored as files, the refreshed token can optionally be persisted back to disk (unlike the stateless GitHub Actions approach)
- **The Cloudflare D1 environment variables (`CF_ACCOUNT_ID`, `CF_D1_DATABASE_ID`, `CF_API_TOKEN`) will no longer be needed** once migrated to local SQLite
- **Consider**: whether to keep the Cloudflare D1 data as a one-time import into the local SQLite, or start fresh. If starting fresh, some emails may be reprocessed once.
- **The `.env` file already exists** in the project root with `OPENAI_API_KEY` — extend this for local config
- **pyenv environment**: Will need to create one for this project (e.g., `gmail-inbox-helper`) or reuse an existing one. Add `rumps` and `sqlite3` (stdlib) to requirements.
