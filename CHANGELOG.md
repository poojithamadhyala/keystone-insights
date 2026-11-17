# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). One release per milestone.

## [Unreleased]

## [1.0.0] - 2026-11-16

### Added
- Loading, empty and error (with Retry) states on every chart card; screen-reader summaries;
  "why this chart type" notes (ⓘ), mirrored in the operator brief.
- `npm run check-mobile` (no horizontal scroll at 375 px), `make bench-a11y` (Lighthouse),
  `npm run record-gif` (README walkthrough GIF).
- `/health` reports the deployed commit.
- README rewrite: live demo, GIF, 60-second walkthrough, architecture, results, how it was built
  with Claude Code, limitations, future work. `docs/domo.md` (how it would ship as a Domo app).

### Fixed
- Phone layout: header overflow and the rent-roll table widening the page (grid `min-w-0`).
- Muted text contrast below WCAG AA (#898781 → #65635d); Lighthouse accessibility 100 on all
  three pages (was 95–96).

## [0.5.0] - 2026-11-16

Public demo: https://keystone-insights-nu.vercel.app

### Added
- Public-demo hosting: `render.yaml` (API on Render), `web/vercel.json` (web on Vercel), Neon via
  `DATABASE_URL` and `make seed-remote`; step-by-step `docs/deploy.md`.
- Demo safeguards (`DEMO_MODE`): per-IP rate limits, $2/day Claude spend cap stored in Postgres,
  labeled recorded answers when over budget or without a key, Send now disabled for visitors.
- Wake-up screen while the free API host starts; "Public demo" badge; clearer limit messages.
- CI builds the web app and scans the bundle for secrets.

### Fixed
- Agent queries on managed Postgres (non-superuser): migration 0004 grants the read-only role to
  the app user (`permission denied to set role` on Postgres 16+).
- Digest fallback footer wording.
- Deploy fixes: CORS origins normalised (`https://` added, trailing `/` stripped),
  `CORS_ORIGIN_REGEX` for Vercel preview URLs, non-secret Render values set in `render.yaml`,
  a clear error for production builds without `VITE_API_URL`, and the deploy guide corrected.

## [0.4.0] - 2026-11-16

### Added
- Weekly portfolio digest: SQL facts (delinquency week over week, leases expiring in 90 days,
  work orders breaching SLA), Claude-written summary gated by a number check, facts-only
  fallback, stored runs (`digest_runs`, migration 0003).
- Digest page: preview of exactly what Slack receives, verified/fallback badge, Rebuild preview,
  Send now, oldest SLA breaches, recent runs.
- Slack delivery (Block Kit) and a weekly GitHub Actions schedule calling a token-protected
  `POST /digest/run`.
- `make bench-digest`: how often the written summary passes the number check (10/10).

### Changed
- `common/numbers`: percentages can be restricted to percentage facts; `numeric_values` can
  filter by key.

## [0.3.0] - 2026-11-16

### Added
- "Ask LeaseLens" agent: Claude tool loop with `query_kpis` (guarded read-only text-to-SQL),
  `search_documents` and `generate_report`, streamed over SSE.
- Chat panel: streaming answers, citation chips for query results [S#] and documents [D#],
  "Show SQL", charts from agent results, suggested questions, per-answer cost.
- Versioned system prompt (`prompts/agent/system_v1.md`) with data dictionary, KPI definitions,
  untrusted-content rule and a leak canary.
- `common/numbers.py`: number extraction and grounding checks (shared with the digest).
- `make eval-agent`: live eval (correctness, documents, refusal, injection, faithfulness,
  citation validity) written to BENCHMARKS.md; mocked-LLM tests run in CI.

### Changed
- API image installs search dependencies and bakes the ONNX models (382 MiB in Docker).

## [0.2.0] - 2026-11-16

### Added
- Process: PR template, CLAUDE.md playbook, operator brief, shaping docs, labeled backlog and
  protected `main` (changes land by squash-merged PR only).
- `make bench-rag` reports the search serving footprint (peak RSS of a fresh process).

### Changed
- RAG reduced to one baseline and one improved method (section chunks + cross-encoder rerank).
- Embedding and reranking run on fastembed (ONNX, CPU) instead of torch; same models, same
  retrieval quality, 376 MB serving footprint (fits a 512 MB host).

### Removed
- BM25 hybrid search, metadata filters and the ablation ladder (measured to add nothing;
  see DECISIONS.md D-021, D-022, D-030).

## [0.1.0] - 2026-11-16

### Added
- Monorepo scaffold: uv/Python 3.11, FastAPI, Vite + React + TypeScript + Tailwind,
  docker-compose with profiles, Makefile, GitHub Actions CI.
- Seeded synthetic portfolio generator (20 properties, 3,000 units, 24 months) with seasonality,
  late payments, evictions, maintenance spikes and signal-driven renewals.
- PostgreSQL schema with Alembic migrations; PII-free `reporting` views for a read-only role.
- KPI API: occupancy, rent roll, delinquency aging, lease expirations, NOI, work-order SLA.
- Reporting dashboard: portfolio overview, property drill-down, URL filters, table views,
  dark mode.
- RAG over 150 synthetic documents in Pinecone with a span-labeled eval set and
  `make bench-rag`.
- Secret scan in `make check`, CI and a pre-commit hook.

[Unreleased]: https://github.com/poojithamadhyala/keystone-insights/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/poojithamadhyala/keystone-insights/releases/tag/v0.1.0
