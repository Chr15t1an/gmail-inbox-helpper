# Token Refresh Runbook

## Why This Is Needed

Google OAuth tokens expire after **7 days** when the app is in "Testing" mode. Moving to Production requires a $500-4500/year security audit (CASA), so we stay in Testing mode and refresh tokens weekly.

## When To Refresh

- Tokens expire every 7 days
- Set a weekly reminder (e.g., every Sunday)
- If you see `Token expired` errors in `watcher.log`, tokens need refreshing

## Accounts

| Account | Email | Token File |
|---------|-------|------------|
| conveyour | christianc@conveyour.com | `tokens/conveyour.json` |
| chri5tian | hello@chri5tian.com | `tokens/chri5tian.json` |
| campbell | campbellchristian36@gmail.com | `tokens/campbell.json` |

## Refresh Process

### Step 1: Generate New Token

```bash
cd /Users/christian/Documents/GitHub/gmail-inbox-helpper
python scripts/generate_token.py
```

A browser window opens. Sign in with the Gmail account you want to refresh.

### Step 2: Save the JSON Output

The script prints a JSON blob. Save it to the appropriate token file:

```bash
# Copy the JSON output and save to the correct file:
# conveyour → tokens/conveyour.json
# chri5tian → tokens/chri5tian.json
# campbell  → tokens/campbell.json
```

### Step 3: Verify

Click "Run Now" in the menu bar app (📬), or restart the watcher:

```bash
./stop_watcher.sh && ./start_watcher.sh
```

Check `watcher.log` to confirm the account processes without errors.

### Step 4: Repeat for Each Account

Run steps 1-3 for each of the 3 accounts.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Token expired` in watcher.log | Token expired (7 days) | Refresh the token |
| `insufficient_quota` | OpenAI API limit hit | Add credits at platform.openai.com |
| Script doesn't open browser | Port conflict | Kill other Python processes, retry |
| `Skipping — no token file` | Token file missing | Generate token and save to `tokens/` |
