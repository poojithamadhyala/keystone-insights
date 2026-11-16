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

## Milestone 2: RAG over property documents

### D-018 Documents generated from the same dataset as the database
150 Markdown documents (house rules, leases, SOPs, vendor contracts, inspection reports) are rendered from the seeded `Dataset`, so every rent, vendor rate and unit number agrees with SQL. That matters for graph RAG and agent evals later. Three documents carry planted prompt-injection text. The flag lives only in the manifest, never in indexed metadata, so milestone 3 can test the agent's defenses. **Limitation:** templated documents share layout and wording, so they are easier to retrieve from than real ones, and absolute scores are optimistic. Comparisons between variants are still meaningful.

### D-019 Eval labels are verbatim evidence spans, not chunk ids
Each question stores `(doc_id, span_start, span_end)` for its evidence. A retrieved chunk is relevant if it covers at least 50% of the span. **Why:** chunk ids change with the chunking strategy, so chunk-id labels would bake one chunker into the ground truth and make the baseline vs. structured comparison unfair. Ranking metrics count only the first relevant hit, so overlapping fixed chunks covering the same span aren't double-counted. A test fails if the document generator ever shifts a labeled span.

### D-020 Hybrid search: own BM25, L2-normalised, one dotproduct index
BM25 is about 40 lines (`rag/sparse.py`) rather than a library, so every weight can be explained. Dense and sparse vectors are both unit-normalised and mixed as `alpha·dense + (1−alpha)·sparse`. Without normalisation, raw BM25 scores (about 5–30) would swamp cosine similarity ([−1, 1]) and alpha would mean nothing. One serverless index (dotproduct, 384-d) holds both variants in separate namespaces (`fixed`, `structured`), so everything except the chunking is held constant.

### D-021 Doc-type filter removed after dev-split error analysis; property filter kept
The first benchmark run showed "+filters" slightly below "+hybrid". Diagnosed **on the dev split only**: keyword rules misfired ("put on the *lease*" inside a house-rules question, "*smok*e alarm" matching the smoking rule). A wrong hard filter makes the answer unretrievable, and a right one added little because the section headers already disambiguate. The exact-name property filter stays; doc-type filtering is off by default (`parse_filters(doc_types=True)` re-enables it). **Transparency:** the test split was scored once before this change and once after. The change was chosen from dev evidence, not from test numbers.

### D-022 Dev/test split, alpha tuned on dev, bootstrap CIs
There is a stable hash-based 30/70 split (41 dev / 89 test). Alpha is grid-searched on dev nDCG@10 over {0.3, 0.5, 0.7, 0.85, 1.0}. The first grid stopped at 0.85, its edge, so 1.0 (dense only) was added. Dev picked 1.0: **BM25 did not help on this corpus.** Twenty near-identical house-rules documents share vocabulary, so keyword overlap points at the wrong property. With 89 test questions, every metric carries a bootstrap 95% CI, and differences with overlapping CIs aren't claimed as wins.

### D-023 Local models on MPS
Embeddings use `BAAI/bge-small-en-v1.5` (384-d, with an instruction prefix on queries only). Reranking uses `cross-encoder/ms-marco-MiniLM-L-6-v2` over the top 30 candidates. Both run on CUDA, MPS or CPU via `common/device.py`. Reranking costs about 60 ms p50 and gave the largest MRR gain.

### D-024 Eval questions drafted by Claude, checked mechanically and by a human
Claude Opus 5.5 is called through `client.beta.messages.parse` with a Pydantic schema, effort `low` (a simple, well-specified task), and server-side refusal fallbacks (`fallbacks="default"`). For each sampled section it writes a question (half paraphrase, half keyword style) plus a verbatim evidence quote. A candidate is kept only if the quote is found in the document. The run kept 130/130 and cost **$1.03** (193k input / 13k output tokens). A 25-item human spot-check (`evals/rag/REVIEW.md` → `make rag-review`) records label precision in BENCHMARKS.md and excludes rejected items.

### D-025 `anthropic` is a core dependency
The agent (milestone 3) runs inside the API, and CI imports the eval code. Torch and Pinecone stay in the `rag` group, and a fresh no-torch environment passes the full test suite.

### D-026 Secret scan in CI and as a pre-commit hook
API keys were once pasted into `.env.example`, a tracked file. They were caught before any commit. `infra/check_secrets.sh` now fails `make check`, CI and `git commit` if a key-like string (Anthropic, Pinecone, Slack webhook, AWS) appears in a tracked or staged file.

## Re-scope (2026-11-16): small, useful, finished

### D-027 Re-scoped for an AI Solutions Analyst application
The target audience changed to a property-management company that values "small, useful, finished beats big and late" and reviewed PRs. Feature store, Graph RAG, drift monitoring and Ray are deferred to `later` issues. The remaining work is lean RAG → basic agent → weekly digest → public demo → polish, one release each.

### D-028 Process: protected main, squash-merged PRs, shaping first
Every change goes through a feature branch and PR (template + self-review comment), CI must pass, and merges are squash-only. **Solo-repo limit:** GitHub doesn't let authors approve their own PRs, so protection requires a PR and green CI (`python`, `web`), linear history and no force-push, for admins too, but zero approvals. The self-review comment stands in for the approval. Each feature has a one-page shape doc (`docs/shaping/`) with an appetite and go/no-go before any code. Setup is scripted in `infra/github/bootstrap.sh`, so it's reviewable and repeatable.

### D-029 Cuts made while re-scoping
* **Digest via Slack only:** email needs a sending provider plus domain verification; logged as a `later` issue.
* **Render instead of Railway:** Railway has no permanent free tier.
* **fastembed (ONNX) instead of torch:** the free API host has 512 MB of RAM. The same embedding and reranking models are used, and the benchmark is re-run on the deployed code path.
* **Weekly schedule via GitHub Actions cron:** Render's cron jobs aren't free, and Actions runs are visible to reviewers.

## Lean RAG (v0.2.0)

### D-030 One baseline, one improved method, served with fastembed (ONNX)
Retrieval is now exactly two methods: *baseline* (fixed 1,000-character chunks, dense) and *improved* (section chunks with title headers, dense top-30, cross-encoder rerank). BM25, filters and the ablation ladder are removed; their measured null results stay in D-021/D-022. Torch and sentence-transformers are replaced by fastembed, with the same two models run on ONNX Runtime on CPU, so the benchmarked code is the code the 512 MB API host runs. Parity was checked before switching: passage embeddings had cosine 1.0, and reranker scores were identical to 3 decimals. **Trap found:** fastembed's `query_embed()` does *not* add BGE's query instruction prefix (its output equals `embed(q)`), so `embed_query` prepends it explicitly, and a test pins this. Results after the switch: improved method unchanged (Recall@5 0.989, MRR 0.946); baseline MRR 0.555 → 0.553, within ANN run-to-run variation.

### D-031 Rerank in batches of 4 to fit the free host
The first footprint measurement failed the shape doc's go/no-go (around 400 MB). Peak RSS was 561–647 MB, because ONNX Runtime sizes its working memory for the whole batch (fastembed's default is 64). Sweep (20 queries × 30 passages, macOS):

| rerank batch | threads | peak RSS | ms/query |
|---|---|---|---|
| 64 | default | 561 MB | 235 |
| 8 | default | 434 MB | 219 |
| 4 | default | 377 MB | 204 |
| 4 | 2 | 376 MB | 263 |
| 2 | 2 | 366 MB | 247 |

We chose batch 4 with default threads: the lowest peak that fits without a latency cost (it's faster, because there's less padding). `make bench-rag` now reports the serving footprint from a fresh process (`rag/footprint.py`): 376 MB. Linux memory accounting differs from macOS, so it is re-measured on the host in the public-demo step.
