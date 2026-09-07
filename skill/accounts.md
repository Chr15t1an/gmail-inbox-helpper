# Accounts

Which mailboxes to sweep, and what is enabled for each. Replace this file entirely when setting the skill
up for someone else — it is the only file with personal configuration in it.

Access is through this repo's OAuth tokens (`tokens/N.json`, see `SKILL.md`), so all three accounts
are reachable. `connected` records whether `profile` succeeded on the last check. `owner` says which
system sweeps the account — `skill` (this runbook) or `watcher` (the Python menu-bar app). A sweep only
touches accounts owned by `skill`; the watcher's `.env` toggles are set false for those.

## conveyour — christianc@conveyour.com

- `connected`: true (token 1, verified 2026-09-07)
- `owner`: watcher
- `job_apps`: false
- `max_per_run`: 150
- Work mail. Bias toward keeping: an unfamiliar sender at a work address is far more likely to matter than
  the same sender on a personal account.

## chri5tian — hello@chri5tian.com

- `connected`: true (token 2, verified 2026-09-07)
- `owner`: **skill** (since the 2026-09-07 sweep; watcher toggles off)
- `job_apps`: **true**
- `max_per_run`: 150
- The account that receives job correspondence and freelance inquiries. Upwork and job-board *alerts* are
  `MARKETING`; a real conversation about a specific role is `JOB_APP_*`.

## campbell — campbellchristian36@gmail.com

- `connected`: true (token 3, verified 2026-09-07)
- `owner`: watcher
- `job_apps`: false
- `max_per_run`: 150
- Personal mail. The highest-volume marketing account of the three.

## never_archive

Overrides every rule and every classification, on every account. If a message matches, it stays in the
inbox regardless of category.

- Anything from a bank, brokerage, or payment processor about a specific transaction, hold, or account
  change — Schwab, Chase, PayPal, Stripe, Wise.
- Anything about tax, legal, insurance, or medical matters.
- Password resets, MFA changes, and security alerts naming this account's own address.
- Anything from a domain in the user's own contacts or that they have replied to in the last 90 days.
- Airline, hotel, and rental confirmations or changes for travel that has not happened yet.
