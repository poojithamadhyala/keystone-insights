# Weekly portfolio digest

**Problem.** Every Monday someone pulls the aging report, the lease-expiration list and open
work orders, compares them with last week, and writes a summary for the team. It's repetitive,
and copy-paste errors in the numbers erode trust.

**Who it's for.** Asset director and property managers (readers); whoever writes the weekly
email today (the work it replaces).

**Appetite.** 2 hours.

**Sketch.**
- `build_digest(as_of)` runs SQL only: delinquency this week vs. last week (by bucket and
  property), leases expiring in the next 90 days, and work orders currently breaching SLA.
  These are the facts.
- Claude writes a short narrative from the facts JSON only (no tools, no database).
- **Number check:** every number in the narrative is extracted and must match a value in the
  facts (with formatting tolerance: $1.2K, 1,200, 12.5%). Any unmatched number fails the digest,
  and the narrative is replaced by a facts-only template and flagged. Covered by tests.
- Dashboard page: preview of this week's digest, a **Send now** button (to Slack), and the last
  send status.
- Weekly schedule: a GitHub Actions cron that calls a token-protected `POST /digest/run`.
- Operator brief: the manual steps it replaces. Time saved is labeled as an estimate.

**Out of scope.** Email delivery (needs a sending provider and domain verification; backlog),
per-user subscriptions, custom schedules, attachments.

**Risks.** Number-check false positives (dates, unit numbers, "90 days"). Mitigation: whitelist
numbers that appear in the facts' labels and dates, and test against tricky narratives. Slack
formatting: use Block Kit with plain mrkdwn and keep it simple.

**Go / no-go.** Go if: the number check catches every planted wrong number in tests and passes
every correct narrative; the preview matches what is sent; Send now posts to Slack; the scheduled
run is visible in Actions. No-go → ship the facts-only digest (no LLM narrative).
