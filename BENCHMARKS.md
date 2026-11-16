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
