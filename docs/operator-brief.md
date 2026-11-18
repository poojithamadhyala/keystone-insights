# Operator brief

Who uses each part of LeaseLens, what question it answers, the decision it supports, and what
must be true before an operator signs off on it. All data is synthetic. The as-of date is
2026-10-31.

## Personas

| Persona | Cares about | Typical cadence |
|---|---|---|
| **Asset director** | Portfolio performance vs. plan: NOI, occupancy trend, which assets need attention | Monthly / quarterly |
| **Property manager** | Their property's day-to-day: vacancies, who is behind on rent, renewals coming up, open maintenance | Daily / weekly |
| **Accounting** | Receivables and cash: aging, collections, write-off candidates, NOI that reconciles | Weekly / month-end |

## Welcome page (`/`)

| | |
|---|---|
| **Questions** | What is this app? Is the portfolio healthy right now? Where do I go next? |
| **Personas** | Anyone new: a reviewer, a new property manager, an executive glancing in |
| **Decision** | Which part of the app to open (dashboard, ask a question, weekly summary) |
| **Sign-off** | The four health cards use the same endpoints and 12-month window as the dashboard, so the numbers match the dashboard tiles exactly. Verdicts follow the rules of thumb below and always show a word and an icon, never color alone. *Verified by `web/src/Home.test.tsx` and `web/src/health.test.ts`.* |

**Rules of thumb for "healthy"** (`web/src/health.ts`; shown on the page under "How we judge healthy"):

| Measure | Healthy | Keep an eye on | Needs attention |
|---|---|---|---|
| Apartments rented (occupancy) | ≥ 95% | 90–95% | < 90% |
| Repairs done on time (work-order SLA) | ≥ 90% | 80–90% | < 80% |

Unpaid rent and leases ending soon get no verdict: a fair threshold depends on portfolio size, so
they show their size and this week's change instead. These are judgment calls for a demo, not
industry standards; a real team would set its own.

## Why each chart type

Form follows the data's job (the same notes are behind each chart's ⓘ button, `web/src/chartNotes.ts`):

| View | Form | Why |
|---|---|---|
| Occupancy | Line | One measure changing month to month; the y-axis is zoomed so a one-point move is visible, and the table view gives exact values. |
| Net operating income | Lines on one $ axis | Collected rent, expenses and NOI move together, so a gap opening between lines shows whether revenue or costs drove the change. |
| Delinquency aging | Stacked bars | Each bucket is a total split into current vs. former residents (two audiences: collection calls vs. collections/write-off); buckets keep their natural order. |
| Lease expirations | Bars | A count per month, where spotting heavy months matters more than the trend between them. |
| NOI by property | Horizontal bars, sorted | Long property names stay readable and rank is obvious; click to drill down. |
| Work-order SLA | Table | Four priorities with exact on-time rates and medians; the precise numbers matter more than shape. |

Every chart also has a table view, a screen-reader summary, and a palette validated for
color-vision deficiency on the dark chart surface: bronze #B58E48, blue #507FCD, plum #973F6E
(worst colour-blind separation ΔE 14.7, all pairs). Plum is low-contrast against the card
(2.6:1), so every multi-series chart keeps its legend and table view. Text meets WCAG AA
contrast and nothing is smaller than 14px (Lighthouse accessibility 100 on all four pages; see
BENCHMARKS.md).

## Dashboard views

### Portfolio overview: KPI tiles

| | |
|---|---|
| **Questions** | How full are we? What did we net? How much is current residents' rent overdue? How many leases roll soon? Are vendors on time? |
| **Personas** | Asset director (headline health); property manager (own property via the filter) |
| **Decision** | Where to look first this week |
| **Sign-off** | Each tile equals the matching chart or table for the same filters and as-of date. Occupancy = occupied / units on the as-of date. *Verified by `backend/api/tests/test_kpis.py` (occupancy, aging, expirations, NOI, SLA) against a hand-calculated fixture.* |

### Occupancy trend (line)

| | |
|---|---|
| **Questions** | Is occupancy rising or falling? Is the winter dip normal or worse than last year? |
| **Personas** | Asset director, property manager |
| **Decision** | Adjust concessions or marketing spend before the slow season |
| **Sign-off** | Uses the same "occupied on day D" rule as the tile, measured on the 1st of each month. A move-out on the 1st counts as vacant that day (end date is exclusive). *Verified by `test_occupancy_snapshot_and_filter`.* |

### Net operating income by month (lines: collected rent, expenses, NOI)

| | |
|---|---|
| **Questions** | Is NOI moving because of revenue or expenses? Which month had a maintenance spike? |
| **Personas** | Asset director, accounting |
| **Decision** | Investigate expense outliers; explain variance in the monthly report |
| **Sign-off** | Cash basis: revenue = rent collected in the month by payment date; expenses = operating expenses for the period + work-order cost completed in the month. Accounting confirms the basis matches how they report (accrual would differ). *Verified by `test_noi_cash_basis`.* |

### NOI by property (horizontal bars, click to drill down)

| | |
|---|---|
| **Questions** | Which assets carry the portfolio and which lag? |
| **Personas** | Asset director |
| **Decision** | Which properties get a deep-dive or capital review |
| **Sign-off** | Bars sum to the NOI tile for the same range. Sorted by NOI. Clicking opens that property with the same date range. |

### Delinquency aging (stacked bars: current vs. former residents)

| | |
|---|---|
| **Questions** | How much rent is overdue and how old is it? How much is from people who have already left? |
| **Personas** | Property manager (current residents: collection calls); accounting (former residents: collections or write-off) |
| **Decision** | Who gets a reminder, a notice or a payment plan; what goes to collections |
| **Sign-off** | Buckets are by **charge month** (current month = 0–30), matching standard aging reports. A payment counts only if made on or before the as-of date. Current vs. former is decided by an active lease on the as-of date. *Verified by `test_delinquency_aging_by_charge_month` and `test_delinquency_is_point_in_time`.* |

### Lease expirations, next 12 months (bars)

| | |
|---|---|
| **Questions** | How many leases end each month, and how much rent is at stake? |
| **Personas** | Property manager, asset director |
| **Decision** | When to start renewal outreach; whether a month is over-concentrated |
| **Sign-off** | A lease is counted in the month of its **last day**. Only leases active on the as-of date are included. *Verified by `test_lease_expirations_use_last_day`.* |

### Work-order SLA (tables by priority; by category on the property page)

| | |
|---|---|
| **Questions** | Are tickets completed within target (emergency 24h, high 72h, normal 7d, low 14d)? Which trade is slow? |
| **Personas** | Property manager; asset director for vendor reviews |
| **Decision** | Escalate a vendor; switch to the backup vendor; staff up before a seasonal spike |
| **Sign-off** | Open tickets past target count as misses. Open tickets still inside their window and cancelled tickets are excluded. *Verified by `test_work_order_sla`.* |

### Property drill-down: rent roll

| | |
|---|---|
| **Questions** | Who lives in each unit, on what rent vs. market, when does the lease end, what do they owe? |
| **Personas** | Property manager, accounting |
| **Decision** | Renewal pricing (rent vs. market); collection follow-up per unit |
| **Sign-off** | Unit count matches the property's units. The balance is that tenant's outstanding charges on that unit as of the as-of date. Vacant units show no tenant. *Verified by `test_rent_roll_balances`.* |

## AI agent: "Ask LeaseLens" (v0.3.0)

| | |
|---|---|
| **Questions** | Ad-hoc questions the dashboard doesn't answer directly: "Which Maple Court units owe more than one month's rent?", "Which vendor handled the most HVAC tickets that breached SLA in July?", "What does lease 383 say about late fees?", "Chart occupancy by property." |
| **Personas** | Property manager (unit and lease detail, documents); asset director (cross-property comparisons, charts); accounting (ad-hoc AR questions) |
| **Decision** | Same decisions as the dashboard, without waiting for an analyst to write SQL or dig through documents |
| **What it can't do** | Change records, send messages, reveal tenant contact details (not in its data at all), answer questions outside the portfolio |
| **Sign-off** | Every number traces to a cited query result [S#] (rows and SQL one click away) or document passage [D#]. Agent KPIs use the dashboard's definitions (charge-month aging, exclusive end dates, cash-basis NOI). Read-only by construction: SQL guard, then a read-only transaction as a view-only role. *Verified by `make eval-agent` (correctness, document answers, refusal, injection, faithfulness, citation validity; results in BENCHMARKS.md) and `backend/api/tests/test_agent.py` (writes blocked even with the SQL guard disabled).* |
| **Manual work it replaces (estimate)** | An analyst writing and checking a one-off SQL query or searching leases for a clause. *Estimate, not measured:* 10–30 minutes per question in a typical team, versus a median of about 5.5 s for the agent in the eval. |

## Weekly portfolio digest (v0.4.0)

| | |
|---|---|
| **Questions** | What changed in delinquency this week, and where? Which leases expire in the next 90 days? Which work orders are breaching SLA right now, and which is the oldest? |
| **Personas** | Asset director (Monday read in Slack); property managers (their property's movers, breaches to chase) |
| **Decision** | Where to spend this week's follow-up time: collection calls, renewal outreach, vendor escalation |
| **Sign-off** | Every number comes from SQL using the dashboard's definitions. The current-resident delinquency total equals the dashboard's "Delinquent (current residents)" tile for the same as-of date ($104,673.08 on 2026-10-31). The written summary is sent only if every number in it matches a fact; otherwise the facts-only version goes out, flagged. The preview is the exact stored text Slack receives. *Verified by `backend/api/tests/test_digest.py` (hand-derived facts, planted wrong numbers, preview == payload) and `make bench-digest` (pass rate of the written summary).* |

**Manual work it replaces.** Each Monday someone currently:
1. exports the aging report, filters to current residents, and compares it with last week's export;
2. runs the lease-expiration report for the next 90 days, then counts and totals rent by month and property;
3. pulls open work orders, works out each one's age against its priority's SLA, and sorts by oldest;
4. writes a summary for the team, copying numbers by hand, and posts it.

*Estimate, not measured:* 45–90 minutes a week for an analyst or property manager, plus the
risk of a mistyped number. The digest automates steps 1–4. A person only reviews the preview,
or doesn't, since it's scheduled.
