# Gmail Inbox Helper

A macOS menu bar app that automatically classifies and cleans up your Gmail inbox using AI.

It connects to your Gmail accounts via the Gmail API, classifies each email using OpenAI's GPT-4o-mini, and takes action:

- **Marketing emails** get labeled "AI Assist" and archived out of your inbox
- **Job application emails** get labeled "Job Application", with emails needing a response flagged as "Needs Follow-up"

Runs every 6 hours in the background. Supports multiple Gmail accounts with per-account toggles.

## Prerequisites

- macOS
- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A Google Cloud project with Gmail API credentials (see below)

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Chr15t1an/gmail-inbox-helpper.git
cd gmail-inbox-helpper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set up Google Cloud credentials

You need OAuth 2.0 credentials so the app can access your Gmail. Follow Google's official guide:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. [Enable the Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com) for your project
4. Go to [APIs & Services > OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
   - Choose **External** user type
   - Fill in the app name and your email
   - Add the scope `https://www.googleapis.com/auth/gmail.modify`
   - Add your Gmail address(es) as test users
5. Go to [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)
   - Click **Create Credentials > OAuth client ID**
   - Choose **Desktop app**
   - Download the JSON file and save it as `scripts/credentials.json`

For more detail, see [Google's Python quickstart](https://developers.google.com/gmail/api/quickstart/python).

> **Note:** While your app is in Google's "Testing" mode, OAuth tokens expire every 7 days. You'll need to regenerate them weekly. See [TOKEN-REFRESH-RUNBOOK.md](TOKEN-REFRESH-RUNBOOK.md) for instructions. Moving to "Production" mode removes this limit but requires Google's verification process.

### 3. Configure `.env`

Create a `.env` file in the project root:

```
OPENAI_API_KEY="sk-..."

# Account 1
ACCOUNT_1_NAME=personal
ACCOUNT_1_EMAIL=me@gmail.com
ACCOUNT_1_MARKETING=true
ACCOUNT_1_JOBAPP=false
```

To add more accounts, continue the pattern (`ACCOUNT_2_*`, `ACCOUNT_3_*`, etc.):

```
# Account 2
ACCOUNT_2_NAME=work
ACCOUNT_2_EMAIL=me@work.com
ACCOUNT_2_MARKETING=true
ACCOUNT_2_JOBAPP=true
```

The app auto-discovers accounts by number and stops when it doesn't find the next one.

**Optional settings** (these are the defaults):

```
MAX_EMAILS_PER_PAGE=50
MAX_PAGES=3
CHECK_INTERVAL=21600    # seconds between runs (21600 = 6 hours)
```

### 4. Generate Gmail tokens

For each account, run the token generator:

```bash
python scripts/generate_token.py
```

A browser window opens. Sign in with the Gmail account, grant access, then save the JSON output to `tokens/N.json` (where N matches the account number in your `.env`):

```bash
# Account 1 → tokens/1.json
# Account 2 → tokens/2.json
```

Repeat for each account.

## Usage

```bash
./start_watcher.sh    # Start the menu bar app
./stop_watcher.sh     # Stop it
```

Look for the 📬 icon in your menu bar:

| Icon | Meaning |
|------|---------|
| 📬 | Idle -- waiting for next run |
| 🔄 | Running -- processing emails |
| ⚠️ | Completed with errors (check logs) |
| ❌ | Fatal error |

Menu options: **Run Now** (trigger immediately), **View Logs** (open `watcher.log`), **Quit**.

## Token Refresh

Because the app runs in Google's "Testing" mode, tokens expire every 7 days. When they do, you'll see `Token expired` in the logs and the ⚠️ icon.

To refresh, re-run `python scripts/generate_token.py` for the affected account and save the new token. See [TOKEN-REFRESH-RUNBOOK.md](TOKEN-REFRESH-RUNBOOK.md) for the full process.

## Cost

OpenAI GPT-4o-mini costs roughly $0.15 per 1M tokens. Processing a few hundred emails costs fractions of a cent.
