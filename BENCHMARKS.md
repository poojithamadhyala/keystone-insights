# Benchmarks

Every number here is produced by a `make bench-*` target and pasted from its output. Nothing is hand-edited. Each entry records the command, dataset size, hardware and date. If an "improved" variant does not beat the baseline, the real result is still reported.

<!-- bench:rag:start -->
## RAG retrieval (component 2)

- **Command:** `make bench-rag`
- **Date:** 2026-11-16
- **Hardware:** Apple M4, 16 GB RAM, Darwin 25.5.0, torch device: mps
- **Dataset:** 150 synthetic documents (399 fixed / 1268 section chunks). 89 test questions (41 dev questions used only to tune alpha). Labels are verbatim evidence spans; a chunk is relevant if it covers at least 50% of the span.
- **Hybrid alpha** (dense weight) tuned on dev: 1.0 (dev nDCG@10 by alpha: {0.3: 0.657, 0.5: 0.744, 0.7: 0.763, 0.85: 0.774, 1.0: 0.799})

Each row adds one change to the row above. Brackets are bootstrap 95% CIs.

| Variant | Recall@5 | MRR@10 | nDCG@10 | Right doc @5 | p50 latency |
|---|---|---|---|---|---|
| baseline | 0.629 [0.53, 0.73] | 0.555 [0.46, 0.65] | 0.594 [0.51, 0.68] | 0.921 [0.86, 0.98] | 95 ms |
| +structure | 0.966 [0.93, 1.00] | 0.805 [0.74, 0.86] | 0.848 [0.79, 0.90] | 0.989 [0.97, 1.00] | 96 ms |
| +hybrid | 0.966 [0.93, 1.00] | 0.805 [0.74, 0.86] | 0.848 [0.79, 0.90] | 0.989 [0.97, 1.00] | 96 ms |
| (ref) hybrid α=0.5, not selected | 0.921 [0.86, 0.98] | 0.699 [0.62, 0.77] | 0.760 [0.70, 0.82] | 0.933 [0.88, 0.98] | 96 ms |
| +filters | 0.966 [0.93, 1.00] | 0.805 [0.74, 0.86] | 0.848 [0.79, 0.90] | 0.989 [0.97, 1.00] | 95 ms |
| +rerank (improved) | 0.989 [0.97, 1.00] | 0.946 [0.91, 0.98] | 0.957 [0.93, 0.98] | 0.989 [0.97, 1.00] | 158 ms |

Latency includes local query embedding, the Pinecone round trip from a home network and, for the last row, cross-encoder reranking of 30 candidates on the local device.

**Reading the table:** alpha tuned on dev came out at 1.0 (dense only), so "+hybrid" is the same as "+structure": BM25 did not improve dev nDCG@10 at any weight. The reference row shows hybrid at alpha 0.5 on test, for comparison only. "+filters" (property filter parsed from the question) also changed no rankings: the title/section header on each chunk already identifies the property. Both stay in the pipeline as switchable options, but the measured gains come from section chunking and reranking. Doc-type filters were dropped after dev analysis showed keyword misfires (DECISIONS.md D-021).
<!-- bench:rag:end -->
