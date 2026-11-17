# Benchmarks

Every number here is produced by a `make bench-*` target and pasted from its output. Nothing is hand-edited. Each entry records the command, dataset size, hardware and date. If an "improved" variant does not beat the baseline, the real result is still reported.

<!-- bench:rag:start -->
## RAG retrieval

- **Command:** `make bench-rag`
- **Date:** 2026-11-16
- **Hardware:** Apple M4, 16 GB RAM, Darwin 25.5.0
- **Dataset:** 150 synthetic documents (399 fixed / 1268 section chunks), 89 test questions. Labels are verbatim evidence spans; a chunk is relevant if it covers at least 50% of the span.
- **Label spot-check:** pending (labels are Claude-generated, span-verified)
- **Methods:** *baseline* = fixed 1,000-character chunks (200 overlap), dense top-10. *improved* = one chunk per section with a title/section header, dense top-30, reranked by a cross-encoder to top-10. Models: bge-small-en-v1.5 and ms-marco-MiniLM-L-6-v2 via fastembed (ONNX, CPU).

Brackets are bootstrap 95% CIs.

| Method | Recall@5 | MRR@10 | nDCG@10 | Right doc @5 | p50 latency |
|---|---|---|---|---|---|
| baseline | 0.629 [0.53, 0.73] | 0.553 [0.46, 0.65] | 0.592 [0.50, 0.68] | 0.921 [0.86, 0.98] | 78 ms |
| improved | 0.989 [0.97, 1.00] | 0.946 [0.91, 0.98] | 0.957 [0.93, 0.98] | 0.989 [0.97, 1.00] | 172 ms |

Search serving footprint: **376 MB** peak RSS for a fresh process holding both models and serving 20 queries (`python -m rag.footprint`, macOS). The free API host has 512 MB; the deployed API is re-measured there.
Latency includes query embedding, the Pinecone round trip from a home network and, for *improved*, reranking 30 candidates on CPU. Pinecone serverless search is approximate (ANN), so repeated runs can move a metric in the third decimal (observed: baseline MRR 0.551 vs 0.553 on identical index and code).

BM25 hybrid search and metadata filters were also built and measured in v0.1.0. Neither improved results on this corpus, so they were removed (DECISIONS.md D-021, D-022, D-030).
<!-- bench:rag:end -->

<!-- bench:agent:start -->
## Agent eval

- **Command:** `make eval-agent`
- **Date:** 2026-11-16
- **Model / prompt:** `claude-opus-5-5` / `prompts/agent/system_v1.md`
- **Cases:** 23 (ground truth from SQL at run time; see `evals/agent/cases.py`)

| Check | Result | How it's scored |
|---|---|---|
| Correctness | 10/10 | every ground-truth value (from SQL) appears in the answer |
| Document answers | 5/5 | gold answer's numbers appear and a cited passage is from the gold document |
| Refusal (out of scope) | 5/5 | Claude judge with a fixed rubric (structured output); contact-detail case also regex-checked |
| Prompt-injection resistance | 3/3 | no canary leak, no compliance with planted instructions, no prompt leak (regex) |
| Faithfulness | 18/18 | every number in the answer matches a tool result (rounding/truncation tolerance) |
| Citation validity | 18/18 | every cited [S#]/[D#] id was issued in that conversation |

Cost: **$0.35** total, $0.015 per question on average. Median latency 5.5 s per question (end to end, including tool calls). Per-case answers are in `artifacts/agent/eval.json`.

**Caveats.** The suite is small: passing every case means no failure was found at this size, not that the failure rate is zero. Cost depends on prompt-cache warmth (cache reads cost 1/20 of fresh input), so a cold run of the same suite costs roughly twice as much. Refusal is the only LLM-judged category.
<!-- bench:agent:end -->

<!-- bench:digest:start -->
## Weekly digest number check

- **Command:** `make bench-digest`
- **Date:** 2026-11-16
- **Model / prompt:** `claude-opus-5-5` / `prompts/digest/narrative_v1.md`
- **Dataset:** digest for the week ending 2026-10-31, built 10 times

| Narratives passing the number check | Rejected numbers | Cost |
|---|---|---|
| 10/10 | none | $0.207 |

Every number in the written summary must match a SQL fact (rounding or truncation to the written precision allowed; percentages only match percentage facts). A failed check doesn't stop the digest: it goes out as the facts-only version, flagged. The pass rate is how often readers get the written summary.
<!-- bench:digest:end -->

<!-- bench:a11y:start -->
## Accessibility (Lighthouse)

- **Command:** `make bench-a11y`
- **Date:** 2026-11-17
- **Tool:** lighthouse@12.2.1, headless Chrome, light mode, desktop viewport
- **Target:** `http://localhost:5174`

| Page | Score | Failing audits |
|---|---|---|
| Welcome page | 100 | none |
| Portfolio dashboard | 100 | none |
| Property drill-down | 100 | none |
| Weekly digest | 100 | none |

Automated checks catch only part of accessibility (contrast, labels, roles, names). Manual keyboard and screen-reader testing hasn't been done.
<!-- bench:a11y:end -->
