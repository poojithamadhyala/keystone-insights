"""Local models on the best available device (CUDA > MPS > CPU, see common/device.py).

* Dense: BAAI/bge-small-en-v1.5 (384-d, about 33M params). Small enough to embed the whole corpus
  in seconds on an M4 and good on retrieval benchmarks for its size. BGE wants an instruction
  prefix on queries, but not on passages.
* Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2 scores (query, passage) pairs jointly.
  That is more accurate than comparing two independent embeddings, but too slow to run over the
  whole corpus, so it only reorders the top candidates.
"""

from __future__ import annotations

from functools import lru_cache

from common.device import best_device

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DIM = 384


@lru_cache
def _embedder():  # type: ignore[no-untyped-def]
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL, device=best_device())


@lru_cache
def _reranker():  # type: ignore[no-untyped-def]
    from sentence_transformers import CrossEncoder

    return CrossEncoder(RERANK_MODEL, device=best_device())


def embed_passages(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    vecs = _embedder().encode(texts, batch_size=batch_size, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def embed_query(text: str) -> list[float]:
    return _embedder().encode(QUERY_PREFIX + text, normalize_embeddings=True).tolist()


def rerank_scores(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    return [float(s) for s in _reranker().predict([(query, p) for p in passages])]
