# Inbox cleanup rules

Two sections: **sender rules**, which are deterministic and free, and **category definitions**, which the
model applies to everything the sender rules did not catch.

This file is meant to be edited. The review mode proposes changes to it every week, and a rule added here
is a mistake that never happens again. If you are sharing this skill, `accounts.md` gets replaced wholesale
and this file is the starting point you grow from.

## Sender rules

Checked in order, top to bottom, before any classification. First match wins and is final. Match on the
From address unless a subject condition is given.

| Match | Category | Label | Archive? | Notes |
|---|---|---|---|---|
| `@facebookmail.com` | NOTIFICATION | `AI Assist` | Yes | Messenger and Facebook notifications |
| `noreply@github.com` | NOTIFICATION | `github` | Yes | Uses the existing `github` label, not `AI Assist` |
| `gitlab@mg.gitlab.com` | NOTIFICATION | `AI Assist` | Yes | |
| `no-reply@accounts.google.com` **and** subject contains `security alert` **and** the subject does *not* name this account's own address | NOTIFICATION | — | Yes | A security alert about *this* mailbox is never archived — it stays and is `NEEDS_ATTENTION` |
| From contains `airbnb` | *(unchanged)* | `AirBnb` | *(unchanged)* | Labelling rule only — adds the label, then classification proceeds normally |

Rules that add a label without deciding the archive question, like the Airbnb one, are marked
*(unchanged)* and fall through to classification.

Only add a sender here when the verdict is the same every single time. A sender that is sometimes a
receipt and sometimes something you need to read belongs in classification, not in this table.

## Category definitions

Assign exactly one category per message.

**MARKETING** — newsletters, promotions, advertisements, product and feature announcements, event
invitations, drip campaigns, "your monthly update", webinar registrations. Automated mail from a business
that is selling or broadcasting rather than transacting.

**COLD_OUTREACH** — unsolicited sales, partnership and agency pitches, recruiter spam from someone with no
existing relationship, "I noticed your company" emails. A stranger who wants something.

**RECEIPT** — order confirmations, payment receipts, invoices, shipping and delivery notifications,
subscription renewal confirmations. A record of a transaction that already happened.

**NOTIFICATION** — automated alerts from services the user already uses: social notifications, account
activity, service status, CI and monitoring output, report deliveries. Machine-generated and
informational.

**JOB_APP_NO_ACTION** *(only on accounts with `job_apps: true`)* — application received confirmations,
rejections, status updates, and automated "do not reply" mail from an employer or ATS. Job-related with
nothing to do.

**JOB_APP_FOLLOWUP** *(only on accounts with `job_apps: true`)* — interview invitations, scheduling
requests, assessments and coding tests, requests for more information, direct questions from a recruiter
or hiring manager. Job-related and the ball is in the user's court. **Never archived.**

**NEEDS_ATTENTION** — a real person the user knows or does business with, wanting a reply or an action.
Also: anything time-sensitive about the user's own money, accounts, security, legal standing, health, or
travel, even when machine-generated. A password reset, a fraud alert, a flight change, or a payment
failure is `NEEDS_ATTENTION`, never `NOTIFICATION`. **Never archived.**

**OTHER** — does not clearly fit anything above, or you are not confident. **Never archived.**

### Edge cases

- **Job alerts are `MARKETING`, not job mail.** "New job alert: …", "3 new jobs in remote", digests from a
  board — those are broadcasts to a list. `JOB_APP_*` is for correspondence about a specific application
  or role the user is actually in a process for.
- **A receipt with a problem is `NEEDS_ATTENTION`.** Failed payment, declined card, delivery exception,
  refund needing action — the transactional framing does not make it filable.
- **A notification about the user's own security is `NEEDS_ATTENTION`.** New device sign-in, password
  changed, MFA disabled, recovery email changed. When in doubt on anything security-shaped, keep it.
- **Personal mail from a real human is never `MARKETING`,** even when short, even when it reads like a
  template, even when the sender is a company address.
- **A thread the user has replied to is `NEEDS_ATTENTION`** unless it is unmistakably closed. The user
  having participated is strong evidence they care.
- **Unsubscribe footers are not proof of `MARKETING`.** Plenty of transactional and account mail carries
  one.

### The tiebreak

When two categories both fit, pick the one that keeps the message in the inbox. When no category clearly
fits, `OTHER`. An inbox with ten pieces of junk left in it is a working system; an inbox missing one real
email is a broken one.

## Change log

Append a line here whenever review mode changes this file, so the reasoning survives.

- *(2026-09-07)* No rule changes. Audit noted the Gmail tools take label IDs, not names — `SKILL.md` now says to resolve them via `list_labels` first.
- *(2026-09-01)* Seeded from `src/rule_filters.py` and the three prompts in `src/classifier.py` of the
  Python watcher. No behavioural changes yet — the sender rules and taxonomy are as the Python ran them,
  with the marketing, job-app, and general passes unified into one category list.
