# Design decisions

Short log of choices and their reasons. Newest at the bottom. Each entry: **decision → why → trade-off**.

## Milestone 0: scaffold

### D-001 Synthetic data only
All data, documents, names and companies are generated with seeded Faker. **Why:** no licensing or privacy concerns, and every result is reproducible from `SEED`. **Trade-off:** synthetic patterns are cleaner than real ones, so model and retrieval numbers are optimistic. This is stated in the README limitations.

### D-002 One `pyproject.toml` with uv dependency groups
A single lockfile for all Python code. Heavy dependencies (torch, ray, feast, lightgbm) go in optional groups (`rag`, `ml`, `graph`, `bench`), so the API image installs only the core. **Why:** one environment is simpler to reason about than seven packages, and groups still keep the images small. **Trade-off:** all components share version constraints.

### D-003 docker-compose profiles
`make up` starts only postgres, redis, api and web. Neo4j, MLflow and the monitoring stack are opt-in profiles. **Why:** running everything takes roughly 6–8 GB on a 16 GB laptop. **Trade-off:** `make demo` has to start all profiles explicitly.

### D-004 Read-only database role created at container init
`leaselens_ro` has `default_transaction_read_only=on` and a `statement_timeout` of 5 s. Migrations later grant it SELECT on the curated `reporting` schema only. **Why:** text-to-SQL safety is enforced by the database itself, not only by prompts or parsers.

### D-005 TypeScript pinned to 6.0.x
The Vite template installs TypeScript 7, but typescript-eslint 8.x requires TypeScript below 6.1. **Why:** the spec requires ESLint in CI. **Trade-off:** we miss the faster TypeScript 7 compiler until typescript-eslint supports it.

### D-006 Vite dev proxy `/api → FastAPI`
The browser talks to a single origin. **Why:** no CORS configuration in the demo, and the same relative URLs work locally and in compose.

### D-007 MLflow on host port 5001
On macOS, port 5000 is used by the AirPlay Receiver.

### D-008 Node 24 LTS in Docker and CI
The lockfile is written by npm 11, and npm 10 (bundled with Node 20) rejects it with `npm ci`. Vite 8 also needs Node 20.19 or newer. **Why:** Node 24 is the current LTS and ships npm 11, so local, CI and container installs match.

### D-009 npm `overrides` for `@emnapi/*`
Rolldown (inside Vite 8) and Tailwind's oxide both ship WASM fallback bindings that pin different `@emnapi` versions. npm then writes a lockfile that `npm ci` rejects. **Why:** pin the family to 1.x, which Rolldown's peer range allows. Neither WASM fallback runs on macOS or Linux (native binaries are used). **Revisit** when Rolldown's binding moves off the 2.0 beta.
Also: npm 11.19 (Docker/CI) is stricter than npm 11.6 about this tree, so the lockfile is generated inside `node:24-alpine` via `make lock-web`.

## Milestone 1: synthetic data, KPIs, dashboard

### D-010 Fixed as-of date (2026-10-31), not `today()`
The generator simulates the 24 months ending on 2026-10-31 and stores that date in `dataset_meta`. The API defaults every query to it. **Why:** the same seed always produces identical KPIs, so tests and benchmarks are reproducible no matter when they run.

### D-011 Agent-facing `reporting` schema without PII
Migration 0002 creates views over the operational tables. Tenant email and phone and vendor phone are dropped, and tenant names become "First L." `leaselens_ro` gets USAGE and SELECT on `reporting` only. A test confirms it is denied on `public`. **Why:** the text-to-SQL agent (milestone 3) can't leak data it can't see. This is enforced by the database, not by a prompt.

### D-012 KPI definitions
* **Occupied on day D:** `start_date ≤ D < COALESCE(move_out_date, end_date)`. `end_date` is exclusive (the first day the unit is free).
* **Lease expirations** are counted in the month of the last day (`end_date - 1`).
* **NOI is cash basis:** rent collected (by `paid_on`) − operating expenses − completed work-order cost. **Trade-off:** accrual NOI would smooth out late payments. Cash basis is simpler and matches the ledger.
* **Point-in-time:** a payment counts as of D only if `paid_on ≤ D`.
* **SLA:** met if completed within the target (24h, 72h, 7d, 14d by priority). Open tickets past target count as misses. Open tickets still inside their window, and cancelled tickets, are excluded.

### D-013 Delinquency aging by charge month, split by current vs. former residents
Rent is due on the 1st, so day-based buckets measured at month-end put every charge at exactly 30, 60 or 91 days, and the 61–90 bucket is always empty. This was found while checking the data. Standard property-management aging reports bucket by charge month, so we do the same. Balances of former residents (move-outs and evictions) are reported separately, because they are collections or write-off candidates rather than an operating signal.

### D-014 Renewal behavior is driven by observable signals plus one hidden trait
At each lease end the generator decides renewal with a logistic function of: late payments in the 6 months before notice, SLA breaches on the unit, work-order count, tenure, the renewal offer vs. market rent, summer seasonality, and a hidden tenant "reliability" trait that is never stored. Tenants owing more than one month's rent are not offered renewal. **Why:** milestone 4's model has a real, partly recoverable signal. The model can't reach perfect accuracy, because the hidden trait is only visible through behavior.

### D-015 KPI tests use a hand-built fixture, not the random seed
`api/tests/conftest.py` builds a 5-unit portfolio in a throwaway `leaselens_test` database. Every expected value in `test_kpis.py` is derived by hand in comments. **Why:** checking SQL against SQL proves nothing. Writing the hand derivations also caught one of my own reasoning errors (former vs. current resident on Apr 15).

### D-016 Bulk load via Postgres COPY with ids from the generator
The generator assigns ids, so foreign keys are known before load. The loader truncates, then runs `COPY` per table and resets sequences. Seeding takes about 2 s for about 100k rows. `make seed` runs inside the API container, so only Docker is needed.

### D-017 Dashboard charts
Colors use the reference categorical palette as CSS tokens, with a separate dark-mode set. Every chart card has a chart/table toggle, so no value is reachable only by hovering. Chart animations are off (a reporting tool should show final values immediately, and the draw-in animation was caught mid-way in screenshots). Filters live in the URL, so a filtered view can be shared. `useApi` keys on the query string and keeps previous data while refetching, so charts don't flash.

### Known limitation
When a tenant catches up on a partial payment, the generator overwrites `amount_paid` and `paid_on` on the earlier ledger row. Point-in-time balances for historical as-of dates therefore treat a partly paid charge as fully unpaid until the catch-up date. A payments table separate from charges would fix this, at the cost of schema complexity.

### Gotcha
After any local `npm install`, run `make lock-web` (D-009). Otherwise the Docker and CI `npm ci` will reject the lockfile.
