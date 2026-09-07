# Accounts

Which mailboxes to sweep, and what is enabled for each. Replace this file entirely when setting the skill
up for someone else — it is the only file with personal configuration in it.

One Gmail connector reaches one mailbox. As of 2026-09-07 the connector in Claude Code is on
**hello@chri5tian.com** only; the other two accounts below are listed for when they get a connector of
their own and are marked `connected: false`. The skill only sweeps accounts marked `connected: true`.

## conveyour — christianc@conveyour.com

- `connected`: **false** — no connector; still handled by the Python watcher when it runs
- `job_apps`: false
- `max_per_run`: 150
- Work mail. Bias toward keeping: an unfamiliar sender at a work address is far more likely to matter than
  the same sender on a personal account.

## chri5tian — hello@chri5tian.com

- `connected`: **true**
- `job_apps`: **true**
- `max_per_run`: 150
- The account that receives job correspondence and freelance inquiries. Upwork and job-board *alerts* are
  `MARKETING`; a real conversation about a specific role is `JOB_APP_*`.

## campbell — campbellchristian36@gmail.com

- `connected`: **false** — no connector; still handled by the Python watcher when it runs
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
