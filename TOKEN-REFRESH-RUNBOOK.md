# Token Refresh Runbook

## Why This Is Needed

Google documents that OAuth tokens expire after **7 days** when the app is in "Testing" mode. Moving to Production requires a $500-4500/year security audit (CASA), so we stay in Testing mode.

**Observed (2026-09-07):** the three tokens generated in February 2026 still refresh and authenticate seven months later. Whatever the documentation says, this runbook is for *when a token actually fails*, not a weekly chore. The pre-2026-09-07 version of this file told you to refresh every Sunday; that was never necessary.

## When To Refresh

- Only when a token actually fails — see the observed note above
- If you see `Token expired` errors in `watcher.log`, tokens need refreshing

## Refresh Process

### Step 1: Generate New Token

```bash
cd /path/to/gmail-inbox-helpper
python scripts/generate_token.py
```

A browser window opens. Sign in with the Gmail account you want to refresh.

### Step 2: Save the JSON Output

The script prints a JSON blob. Save it to `tokens/N.json`, matching the account number in your `.env`:

```bash
# Account 1 → tokens/1.json
# Account 2 → tokens/2.json
# Account 3 → tokens/3.json
# etc.
```

### Step 3: Verify

Click "Run Now" in the menu bar app (📬), or restart the watcher:

```bash
./stop_watcher.sh && ./start_watcher.sh
```

Check `watcher.log` to confirm the account processes without errors.

### Step 4: Repeat for Each Account

Run steps 1-3 for each account.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Token expired` in watcher.log | Token expired (7 days) | Refresh the token |
| `insufficient_quota` | OpenAI API limit hit | Add credits at platform.openai.com |
| Script doesn't open browser | Port conflict | Kill other Python processes, retry |
| `Skipping — no token file` | Token file missing | Generate token and save to `tokens/` |
