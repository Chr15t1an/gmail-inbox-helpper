---
name: inbox-review
description: Weekly review of what the inbox sweep got wrong — find the mail Christian pulled back out of the archive and turn each miss into a rule.
---

Run the inbox-cleanup skill in review mode. The runbook is `skill/SKILL.md` in this repo.

Find the misses (mail carrying an archive-category label that is back in the inbox, or starred), trace
each one to its entry in `skill/decisions/`, and work out whether a sender rule or a category definition
is at fault.

Then **stop and show Christian the proposed edits to `rules.md` before writing them.** This routine
proposes; it does not silently rewrite its own rules. Include for each proposed change: the message that
prompted it, whether a rule or the model made the original call, and the exact edit.

Report the miss rate for the week — misses divided by messages archived — and whether it moved since last
week.

Constraints: never send, never delete. Do not clear the category label off a pulled-back message until
its rule change is approved and written, or the signal is lost.
