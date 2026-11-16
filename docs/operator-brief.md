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

## Dashboard views

### Portfolio overview: KPI tiles

| | |
|---|---|
| **Questions** | How full are we? What did we net? How much is current residents' rent overdue? How many leases roll soon? Are vendors on time? |
| **Personas** | Asset director (headline health); property manager (own property via the filter) |
| **Decision** | Where to look first this week |
| **Sign-off** | Each tile equals the matching chart or table for the same filters and as-of date. Occupancy = occupied / units on the as-of date. *Verified by `api/tests/test_kpis.py` (occupancy, aging, expirations, NOI, SLA) against a hand-calculated fixture.* |

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
| **Sign-off** | Every number traces to a cited query result [S#] (rows and SQL one click away) or document passage [D#]. Agent KPIs use the dashboard's definitions (charge-month aging, exclusive end dates, cash-basis NOI). Read-only by construction: SQL guard, then a read-only transaction as a view-only role. *Verified by `make eval-agent` (correctness, document answers, refusal, injection, faithfulness, citation validity; results in BENCHMARKS.md) and `api/tests/test_agent.py` (writes blocked even with the SQL guard disabled).* |
| **Manual work it replaces (estimate)** | An analyst writing and checking a one-off SQL query or searching leases for a clause. *Estimate, not measured:* 10–30 minutes per question in a typical team, versus a median of about 5.5 s for the agent in the eval. |

## Weekly digest (step 3)

_Filled in when it ships._
