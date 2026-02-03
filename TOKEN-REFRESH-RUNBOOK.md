# Token Refresh Runbook

## Why This Is Needed

Google OAuth tokens expire after **7 days** when the app is in "Testing" mode. Moving to Production requires a $500-4500/year security audit (CASA), so we stay in Testing mode and refresh tokens weekly.

## When To Refresh

- Tokens expire every 7 days
- Set a weekly reminder (e.g., every Sunday)
- If you see `invalid_grant: Token has been expired or revoked` errors in GitHub Actions, tokens need refreshing

## Accounts

| Account | Email | GitHub Secret |
|---------|-------|---------------|
| conveyour | christianc@conveyour.com | `GMAIL_TOKEN_CONVEYOUR` |
| chri5tian | hello@chri5tian.com | `GMAIL_TOKEN_CHRI5TIAN` |
| campbell | campbellchristian36@gmail.com | `GMAIL_TOKEN_CAMPBELL` |

## Refresh Process

### Step 1: Generate New Token

```bash
cd /Users/christian/Documents/GitHub/gmail-inbox-helpper
python scripts/generate_token.py
```

A browser window opens. Sign in with the Gmail account you want to refresh.

### Step 2: Copy the JSON Output

The script prints a JSON blob like:
```json
{
  "token": "ya29...",
  "refresh_token": "1//...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "...",
  "client_secret": "...",
  "scopes": ["https://www.googleapis.com/auth/gmail.modify"]
}
```

### Step 3: Update GitHub Secret

Using GitHub CLI:
```bash
gh secret set GMAIL_TOKEN_<ACCOUNT> --body '<paste JSON here>'
```

Or manually:
1. Go to https://github.com/Chr15t1an/gmail-inbox-helpper/settings/secrets/actions
2. Click on the secret (e.g., `GMAIL_TOKEN_CONVEYOUR`)
3. Click "Update"
4. Paste the JSON
5. Save

### Step 4: Verify

Trigger a test run:
```bash
gh workflow run "Marketing Email Cleanup"
gh run list --limit 3
```

### Step 5: Repeat for Each Account

Run steps 1-4 for each of the 3 accounts.

## Quick Commands

```bash
# Check recent workflow status
gh run list --limit 10

# View failed job logs
gh run view <run-id> --log-failed

# Trigger test runs
gh workflow run "Marketing Email Cleanup"
gh workflow run "Job Application Email Cleanup"
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `invalid_grant: Token has been expired or revoked` | Token expired (7 days) | Refresh the token |
| `insufficient_quota` | OpenAI API limit hit | Add credits at platform.openai.com |
| Script doesn't open browser | Port conflict | Kill other Python processes, retry |
