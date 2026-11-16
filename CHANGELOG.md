# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). One release per milestone.

## [Unreleased]

### Added
- Process: PR template, CLAUDE.md playbook, operator brief, shaping docs, labeled backlog and
  protected `main` (changes land by squash-merged PR only).

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

[Unreleased]: https://github.com/OWNER/leaselens/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/leaselens/releases/tag/v0.1.0
