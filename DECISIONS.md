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

## AI agent (v0.3.0)

### D-032 Hand-written tool loop on the Anthropic SDK, streamed over SSE
A manual loop (rather than the SDK's tool runner) because every step is also a UI event: text deltas, the SQL that ran and its rows, document passages and charts. It follows the SDK's documented streaming pattern: eager tool-input streaming with Pydantic validation before execution, stop on `refusal` or on `max_tokens` with a pending tool call, and a turn **rollback** on any abnormal end so a dangling `tool_use` can't break the next request. At most 6 tool rounds; the last round sets `tool_choice: none`, so the model must answer. Full assistant turns (thinking blocks included) are stored append-only. Server-side refusal fallbacks are on (`fallbacks: "default"`), with a tested sanitizer for the "echo after a mid-stream fallback" rule. Conversations are kept in an in-memory LRU (200 conversations, 2 h): fine for a single-instance demo, and listed as a limitation.

### D-033 Text-to-SQL safety in four independent layers
(1) sqlglot parse: a single read query; (2) tree walk: no write/DDL/INTO/locks, tables must be allowlisted `reporting` views or the query's own CTEs, deny functions that read files or run SQL strings (`pg_*`, `query_to_xml`, `dblink`, …); (3) LIMIT rewritten to at most 200 (+1 to detect truncation); (4) execution in a READ ONLY transaction after `SET LOCAL ROLE leaselens_ro`, with a 5 s timeout and `search_path=reporting`. Layer 4 holds even if the API connects as a superuser, and a test proves writes and PII reads fail **with the guard disabled**. `SELECT email FROM tenants` passes the guard by design but fails in the database, because the view has no such column: PII is excluded by schema, not by prompt.

### D-034 Prompt as a versioned file, tool output marked untrusted, canary for leak detection
`prompts/agent/system_v1.md` holds a data dictionary and the dashboard's KPI definitions (so agent numbers agree with the dashboard), plus rules for citations, scope, privacy, untrusted content and style. Every tool result reaches the model wrapped in `<tool_result trust="untrusted">`. The prompt contains a canary string that must never appear in output, which makes prompt-leak detection a deterministic check. The `done` event reports the model and prompt version, so every answer is traceable.

### D-035 Number grounding is shared code (`common/numbers.py`)
It extracts numbers from text (`$1.2K`, `94.4%`, `1,234.56`; dates, times, bucket labels and citation ids ignored) and checks each against source values. The tolerance accepts a value written either rounded or truncated to its stated precision. The agent eval uses it for faithfulness, and the weekly digest's number check will reuse it. The first live run caught the model streaming "$9,777.77" and then correcting it to "$9,777.57". Prompt rule 1 now says to copy numbers exactly, because streamed text can't be taken back.

### D-036 Agent eval: SQL ground truth, mostly deterministic scoring, scorer bugs fixed in the open
23 cases: 10 correctness (ground truth computed by SQL at run time), 5 document answers (every 8th numeric test question from the RAG set, not hand-picked), 5 refusals (the only LLM-judged category: Claude with a fixed rubric and structured output), 3 injection cases targeting the planted documents. Faithfulness and citation validity are scored on every answered case. **First run:** injection 2/3 and faithfulness 16/18. Reading the answers showed all three flags were *scorer* false positives: the agent had correctly *reported* the planted instruction while ignoring it; "of the 20 properties" was a row count that wasn't in the grounding sources; and "September 1–30" was half-consumed by the month-day ignore rule. Each fix has a regression test built from the exact answer. The suite was then **re-run in full** rather than re-scoring the saved answers, giving 23/23 with $0.35 cost (warm prompt cache; the cold first run cost $0.71). Runs now save tool payloads, so future scorer fixes can re-score offline. The suite is small, so 23/23 means no failure was found at this size, not a zero failure rate.

### D-037 API image bakes the ONNX models; memory measured on Linux
The API image installs the `rag` group and downloads both models at build time, so a cold start never fetches ~100 MB on the first question. Measured in Docker (Linux) after document questions: **382 MiB** for the API container, under Render's 512 MB. This matches the macOS footprint benchmark (376 MB).

## Weekly digest (v0.4.0)

### D-038 Facts from SQL, narrative from Claude, gate in code
`api/digest/facts.py` computes a point-in-time comparison of this week (as of D) with last week (D − 7): current-resident delinquency by bucket and property (dashboard definitions), leases whose last day falls in [D, D + 90], and work orders breaching SLA *at that date* (a ticket completed later still counts as open on the earlier date). Claude gets only the facts JSON (no tools, no database) and a versioned prompt (`prompts/digest/narrative_v1.md`) that forbids arithmetic: differences and percentages must be the ones in the facts. The code, not the model, decides what ships: every number in the narrative must match a fact, or the deterministic facts-only text is sent instead, flagged. A model or API failure takes the same fallback path, so the digest always goes out.

### D-039 Typed percentage matching
Building the tests surfaced a real hole in the shared number check: "down 18%" was accepted because an unrelated fact ("open 18 days") matched the bare number 18. `common/numbers.ungrounded` now takes optional `percent_sources`. In the digest, a "%" may only match `*_pct` facts. The agent eval keeps the loose default, because tool results don't label percentages. **Known limit:** money vs. count can still cross-match (for example "$18" vs. 18 days). A tighter check would need typed facts, which wasn't worth it for this appetite.

### D-040 Rejected numbers never reach readers
The fallback footer first named the rejected numbers ("used numbers not in the data ($9,999)"), which would have shown the wrong figure to the very people the check protects. Rejected numbers are now stored in `digest_runs.ungrounded` and shown only as an operator note on the preview page. The Slack text just says the summary was withheld.

### D-041 Stored runs make "preview == sent" structural
Every build is a row in `digest_runs` (facts, exact text, check result, cost, delivery status). **Send now** and the scheduled run deliver the stored `text` unchanged, and a test asserts the Slack payload equals the payload built from the previewed run. `make bench-digest` builds the narrative N times with trigger `bench`, which is never shown or sent. First run: **10/10** passed the number check, $0.207 in total.

### D-042 Schedule via GitHub Actions; token-protected endpoint
`.github/workflows/weekly-digest.yml` runs Mondays 13:00 UTC (and on demand). It calls `POST /digest/run` with a bearer token, compared in constant time. If the repo secrets aren't set (no deployed API yet), it skips with a notice instead of failing weekly. `DIGEST_SEND_ENABLED=false` turns the public demo into preview-only.

## Public demo (v0.5.0)

### D-043 Managed Postgres: the app user must be granted the read-only role
On Neon the app's user isn't a superuser. Since Postgres 16, a non-superuser that creates a role gets ADMIN on it but not the right to `SET ROLE` to it, so every agent query would have failed in production with "permission denied to set role". This was **found before deploying** by reproducing Neon's setup locally (a `CREATEROLE`-only owner). Migration 0004 runs `GRANT leaselens_ro TO current_user`. The role's own privileges are unchanged: still `reporting` views only. `api/tests/test_managed_postgres.py` migrates and queries as a non-superuser. It fails without 0004 (verified) and passes with it, and it also proves the role stays view-only at the database level.

### D-044 Demo safeguards live in the API, enabled by DEMO_MODE
* **Per-IP rate limits** (10 agent questions, 3 digest builds per hour): an in-memory sliding window, so a restart resets it (acceptable). The client IP comes from `X-Forwarded-For` only when `TRUST_PROXY` is set; otherwise anyone could choose their own bucket.
* **Daily spend cap** ($2): Claude cost per UTC day in Postgres (`llm_spend`), so it survives the free host's restarts. Check-then-record can overshoot by the cost of requests already in flight (about $0.05 each), which is acceptable for a demo.
* **Over budget or no key:** real answers to the five suggested questions, recorded once (`api/record_samples.py`, $0.199) and labeled "Recorded answer", so the demo never shows a dead chat. Free-form questions get a polite pause message. The digest falls back to its facts-only text without calling the model.
* **Send now** is off on the demo (`DIGEST_SEND_ENABLED=false`); the token-protected weekly schedule still sends.
* In demo mode, errors shown to visitors are generic (details go to the server log).
All of it was exercised against the real Docker image in demo mode at $0 (spend cap 0): recorded answer, pause message, 429 with `Retry-After`, Send now refused, facts-only digest, CORS limited to the configured origin.

### D-045 Hosting shape
Vercel serves the static build (`web/vercel.json`, SPA rewrites); `VITE_API_URL` is the only value the browser gets. Render runs the existing API image from `render.yaml`; secrets are `sync: false`, so they're entered in Render's dashboard. The container runs Alembic on boot (idempotent) and binds `$PORT`. Neon holds the seeded data (23 MB of the 0.5 GB free tier), seeded from a laptop with `make seed-remote` over a direct (non-pooled) connection. Render's free plan sleeps when idle, so the web app gates on `/health` and shows a "Waking up the demo API" screen with elapsed seconds instead of errors. CI now builds the web app and scans the bundle for key-like strings and server-side variable names; a planted fake key was caught.

### D-046 Deploy fixes from the first real deploy
Four problems came up while deploying to Vercel, Render and Neon. Each is now fixed in code or in `docs/deploy.md`:
* **Render didn't prompt for every `sync: false` key** (`DIGEST_RUN_TOKEN`, `CORS_ORIGINS`). I can't see from here why Render skipped those two prompts. Non-secret values (`CORS_ORIGINS`, `CORS_ORIGIN_REGEX`) now live in `render.yaml`, and the guide has an explicit "check all five secrets exist" step.
* **`CORS_ORIGINS` without `https://` silently blocked the app.** Browsers send `Origin: https://host` and CORS needs an exact match. The API now normalises entries (adds `https://`, strips a trailing `/`); tested.
* **`VITE_API_URL` missing from the first Vercel build.** Vite inlines it at build time, so it must be set before the first deploy, or the app redeployed. A production build without it now says so instead of showing "waking up" for 150 s. If `/health` returns HTML (the URL points at the web app), that's reported too.
* **Vercel preview URLs were blocked by CORS.** `CORS_ORIGIN_REGEX` admits `keystone-insights-*.vercel.app`; tests show that look-alikes (`….vercel.app.evil.com`, `http://`) are rejected. CORS isn't the security boundary for this public, unauthenticated demo API; the rate limits and spend cap are.

**Also found:** the "Facts-only fallback" preview reported after deploy came from the *local* app. My demo-mode simulation (D-044, run with the spend cap at $0) had written a facts-only digest into the local database. The live database had never stored a fallback, and its first real build verified (all numbers matched, $0.02). Lesson: run simulations against a throwaway database. The local preview was rebuilt.

**Not yet measured:** Render memory after a document question, and cold-start time. 382 MiB was measured locally in Docker, not on Render. The steps are in `docs/deploy.md` §5; the numbers will be recorded here once measured.
