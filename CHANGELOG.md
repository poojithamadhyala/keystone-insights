# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). One release per milestone.

## [Unreleased]

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

[Unreleased]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/poojithamadhyala/keystone-insights/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/poojithamadhyala/keystone-insights/releases/tag/v0.1.0
