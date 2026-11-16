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
