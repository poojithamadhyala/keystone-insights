# Lean RAG

**Problem.** Document search has five switchable variants (fixed/section chunking, BM25 hybrid,
filters, reranking). Hybrid and filters were measured to add nothing on this corpus, but they
still cost code, an index namespace and reviewer attention. Torch also can't run on the free
hosting tier (512 MB RAM).

**Who it's for.** The agent's `search_documents` tool, used by property managers asking about
leases, house rules, SOPs and vendor contracts. Also the reviewer reading the repo.

**Appetite.** 45 minutes.

**Sketch.**
- Keep exactly two methods: **baseline** (fixed 1,000-character chunks, dense top-k) and
  **improved** (section chunks with title headers + cross-encoder rerank of the top 30).
- Remove BM25, the sparse vectors, the property/doc-type filters and the ablation ladder. Their
  findings stay in DECISIONS.md.
- Swap sentence-transformers/torch for **fastembed** (ONNX, CPU): same `bge-small-en-v1.5`
  embedder and `ms-marco-MiniLM-L-6-v2` reranker, so the benchmarked path is the deployed path.
- Re-run `make bench-rag`. The table has two rows.

**Out of scope.** New retrieval ideas; query rewriting; other embedding models.

**Risks.** fastembed's model outputs may differ slightly from sentence-transformers, so scores
may shift. Mitigation: re-run the benchmark and report whatever comes out. Plan: a fastembed
model is missing → fall back to Pinecone hosted inference (document it).

**Go / no-go.** Go if: the benchmark runs end to end on fastembed, the improved method still beats
baseline with non-overlapping CIs on Recall@5, the API process with models loaded stays under
about 400 MB RSS, and `make check` is green. No-go → keep torch locally and use hosted
inference for the demo.
