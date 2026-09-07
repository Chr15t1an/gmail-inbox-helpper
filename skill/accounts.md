# Accounts

Which mailboxes to sweep, and what is enabled for each. Replace this file entirely when setting the skill
up for someone else — it is the only file with personal configuration in it.

Each account needs a connected Gmail account the skill can reach. Verify with `list_labels` before a run.

## conveyour — christianc@conveyour.com

- `job_apps`: false
- `max_per_run`: 150
- Work mail. Bias toward keeping: an unfamiliar sender at a work address is far more likely to matter than
  the same sender on a personal account.

## chri5tian — hello@chri5tian.com

- `job_apps`: **true**
- `max_per_run`: 150
- The account that receives job correspondence and freelance inquiries. Upwork and job-board *alerts* are
  `MARKETING`; a real conversation about a specific role is `JOB_APP_*`.

## campbell — campbellchristian36@gmail.com

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
