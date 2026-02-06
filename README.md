# Gmail Inbox Helper

Automated email cleanup running as a local macOS menu bar app. Classifies and organizes emails from multiple Gmail accounts using AI.

## Features

- **Marketing Email Cleanup**: Classifies emails as MARKETING/PERSONAL, labels marketing emails with "AI Assist" and archives them
- **Job Application Cleanup**: Identifies job-related emails, labels them appropriately, and flags emails needing follow-up
- **Multi-Account Support**: Processes 3 Gmail accounts sequentially
- **Menu Bar App**: Runs as a macOS menu bar utility with status icon, "Run Now" button, and log viewer
- **Scheduled Execution**: Runs every 6 hours (configurable via `.env`)
- **Per-Account Toggles**: Enable/disable features per account via `.env`

## Setup

### 1. Prerequisites

- macOS
- Python 3.10+
- Google Cloud Project with Gmail API enabled
- OpenAI API key

### 2. Create Google Cloud OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Gmail API
4. Go to APIs & Services → Credentials
5. Create OAuth 2.0 Client ID (Desktop app)
6. Download `credentials.json` to `scripts/` directory

### 3. Create Virtual Environment

```bash
cd /Users/christian/Documents/GitHub/gmail-inbox-helpper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure `.env`

The `.env` file contains all configuration:

```
OPENAI_API_KEY="sk-..."

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

### 5. Generate Gmail Tokens

For each Gmail account, run the token generator and save the output:

```bash
python scripts/generate_token.py
# Sign in as christianc@conveyour.com → save output to tokens/conveyour.json

python scripts/generate_token.py
# Sign in as hello@chri5tian.com → save output to tokens/chri5tian.json

python scripts/generate_token.py
# Sign in as campbellchristian36@gmail.com → save output to tokens/campbell.json
```

See [TOKEN-REFRESH-RUNBOOK.md](TOKEN-REFRESH-RUNBOOK.md) for weekly refresh instructions.

## Usage

### Start/Stop

```bash
./start_watcher.sh    # Start the menu bar app
./stop_watcher.sh     # Stop it
```

Or use the global alias (starts all watchers):
```bash
start-watcher         # Starts Vector, JobHunter, Son's PC Monitor, and Gmail
stop-watcher          # Stops all
```

### Menu Bar

Look for the 📬 icon in the menu bar:
- **Status**: Shows Idle / Running / Error state
- **Last Run**: Timestamp of the last cleanup cycle
- **Next Run**: Countdown to the next scheduled run
- **Run Now**: Manually trigger a cleanup cycle
- **View Logs**: Open `watcher.log`
- **Quit**: Stop the app

### Status Icons

| Icon | Meaning |
|------|---------|
| 📬 | Idle — waiting for next run |
| 🔄 | Running — processing emails |
| ⚠️ | Completed with errors (check logs) |
| ❌ | Fatal error (e.g., classifier init failed) |

## Labels Created

The system creates these Gmail labels:
- **AI Assist**: Applied to marketing emails before archiving
- **Job Application**: Applied to job-related emails
- **Needs Follow-up**: Applied to job emails requiring action

## Accounts

| Account | Email | Token File |
|---------|-------|------------|
| conveyour | christianc@conveyour.com | `tokens/conveyour.json` |
| chri5tian | hello@chri5tian.com | `tokens/chri5tian.json` |
| campbell | campbellchristian36@gmail.com | `tokens/campbell.json` |

## Cost Estimates

- **OpenAI**: GPT-4o-mini costs ~$0.15/1M tokens — very cheap
