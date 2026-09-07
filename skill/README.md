# inbox-cleanup — the skill version

A Claude skill that does what the Python watcher in this repo does, without the Python, the OAuth, or the
database. Drafted 2026-09-01; the Python watcher is still the thing actually running.

## What changed and why

| | Python watcher | This skill |
|---|---|---|
| Gmail access | OAuth app, `credentials.json`, per-account tokens | The same tokens, through `scripts/gmail_cli.py`. The Gmail MCP connector turned out read-only and single-account. |
| Scheduling | `rumps` menu bar app, sleep loop, PID file, start/stop scripts, timeout guards | A routine with a cron expression |
| Dedupe state | SQLite at `data/gmail_helper.db` | The `AI/reviewed` Gmail label |
| Classification | Three prompts frozen in `src/classifier.py`, one API call per email | One taxonomy in `rules.md`, batched 25 at a time |
| Passes over the inbox | Three (marketing, job apps, general), each re-listing the inbox | One |
| Learning | None possible — the prompts are string literals | `rules.md` plus the weekly review mode |
| Setup for a new person | Google Cloud project, OAuth consent screen, test users, credentials download, per-account token generation, weekly refresh | Same OAuth setup once (`scripts/generate_token.py`), then edit `accounts.md`. The weekly refresh has not been needed in practice |
| Lines to maintain | ~1,500 | 4 markdown files |

The unification of the three passes into one is worth calling out separately: the current watcher fetches
the same inbox page two or three times per account per cycle and can classify one message up to three
times. One pass, one verdict.

## Files

- `SKILL.md` — the runbook. Sweep mode and review mode.
- `rules.md` — sender rules and the category definitions. **The file that learns.** Seeded from
  `src/rule_filters.py` and the prompts in `src/classifier.py`.
- `accounts.md` — which mailboxes, what is enabled, and the `never_archive` override. The only file with
  personal config; replace it wholesale when sharing.
- `routines/inbox-sweep/` — every 6 hours, matching the watcher's `CHECK_INTERVAL`. Ships disabled.
- `routines/inbox-review/` — weekly, Monday 08:00. The feedback loop. Ships disabled.
- `decisions/` — append-only monthly logs of what was archived and why. Review mode reads these.

## Install

```bash
cp -r skill ~/.claude/skills/inbox-cleanup
```

Then edit `accounts.md`, and register the routines when you want them running. Both ship with
`"enabled": false` and a `cwd` pointing at this repo — change the `cwd` if you install elsewhere.

## Sharing it with someone else

Send them `SKILL.md`, `rules.md`, and a stripped `accounts.md`. Their setup is: connect the Gmail
connector, list their mailboxes in `accounts.md`, run it. `rules.md` is a starting point they grow —
the sender rules in it are specific to Christian's mail and most will not apply.

## The thing to verify before trusting it

Cost. The watcher costs fractions of a cent per cycle at one `gpt-4o-mini` call per email. This skill
batches 25 messages per classification pass, so a 150-message sweep should be about six passes — but that
is an estimate, not a measurement. Run one sweep against a single account alongside the watcher and
compare both the token cost and the verdicts before scheduling anything.

## What this deliberately does not do

No sending, no replying, no drafting. No deleting, no trashing, no touching spam. No unsubscribing and no
clicking links in mail. Archiving is reversible and that is the whole safety model — every mistake this
skill can make is one the user can undo, and the review mode is built to find exactly those.
