# Gmail Inbox Helper

Automated email cleanup using GitHub Actions. Classifies and organizes emails from multiple Gmail accounts using AI.

## Features

- **Marketing Email Cleanup**: Classifies emails as MARKETING/PERSONAL, labels marketing emails with "AI Assist" and archives them
- **Job Application Cleanup**: Identifies job-related emails, labels them appropriately, and flags emails needing follow-up
- **Multi-Account Support**: Processes 3 Gmail accounts in parallel
- **Scheduled Execution**: Marketing cleanup every 15 minutes, job app cleanup every 30 minutes
- **Per-Account Toggles**: Enable/disable features per account via GitHub Variables

## Setup

### 1. Prerequisites

- Google Cloud Project with Gmail API enabled
- Cloudflare account with D1 database
- OpenAI API key

### 2. Create Google Cloud OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Gmail API
4. Go to APIs & Services → Credentials
5. Create OAuth 2.0 Client ID (Desktop app)
6. Download `credentials.json`

### 3. Generate Gmail Tokens

For each Gmail account:

```bash
# Place credentials.json in scripts/ directory
python scripts/generate_token.py
```

Follow the OAuth flow and save the output JSON.

### 4. Create Cloudflare D1 Database

```bash
# Install Wrangler CLI
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Create D1 database
npx wrangler d1 create gmail-inbox-helper

# Note the database ID from output
```

Then apply the schema via Cloudflare Dashboard or Wrangler:

```sql
-- Processed marketing emails
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

-- Job application emails
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

### 5. Configure GitHub Secrets

Go to Repository Settings → Secrets → Actions and add:

| Secret Name | Description |
|-------------|-------------|
| `GMAIL_TOKEN_CONVEYOUR` | OAuth token JSON for christianc@conveyour.com |
| `GMAIL_TOKEN_CHRI5TIAN` | OAuth token JSON for hello@chri5tian.com |
| `GMAIL_TOKEN_CAMPBELL` | OAuth token JSON for campbellchristian36@gmail.com |
| `OPENAI_API_KEY` | OpenAI API key |
| `CF_ACCOUNT_ID` | Cloudflare Account ID |
| `CF_D1_DATABASE_ID` | D1 Database ID |
| `CF_API_TOKEN` | Cloudflare API token (with D1 permissions) |

### 6. Configure GitHub Variables

Go to Repository Settings → Variables → Actions and add:

| Variable Name | Value | Description |
|---------------|-------|-------------|
| `ENABLE_MARKETING_CONVEYOUR` | `true` | Enable marketing cleanup for conveyour |
| `ENABLE_MARKETING_CHRI5TIAN` | `true` | Enable marketing cleanup for chri5tian |
| `ENABLE_MARKETING_CAMPBELL` | `true` | Enable marketing cleanup for campbell |
| `ENABLE_JOBAPP_CONVEYOUR` | `false` | Disable job app cleanup for conveyour |
| `ENABLE_JOBAPP_CHRI5TIAN` | `true` | Enable job app cleanup for chri5tian |
| `ENABLE_JOBAPP_CAMPBELL` | `false` | Disable job app cleanup for campbell |

## Manual Trigger

You can manually trigger workflows from the Actions tab:

1. Go to Actions
2. Select "Marketing Email Cleanup" or "Job Application Email Cleanup"
3. Click "Run workflow"

## Labels Created

The system creates these Gmail labels:
- **AI Assist**: Applied to marketing emails before archiving
- **Job Application**: Applied to job-related emails
- **Needs Follow-up**: Applied to job emails requiring action

## Cost Estimates

- **GitHub Actions**: ~2 minutes per run, well within free tier
- **OpenAI**: GPT-4o-mini costs ~$0.15/1M tokens - very cheap
- **Cloudflare D1**: Free tier (5GB storage, 5M reads/day)
