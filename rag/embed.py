"""Local models via fastembed (ONNX Runtime, CPU). No torch, so the same code fits the free
512 MB API host, and what we benchmark is what we deploy (DECISIONS.md D-030).

* Dense: BAAI/bge-small-en-v1.5 (384-d). BGE expects an instruction prefix on queries only.
  NOTE: fastembed's `query_embed()` does NOT add this prefix (verified: identical to `embed(q)`),
  so we prepend it ourselves. `test_query_prefix_is_applied` pins this.
* Reranker: ms-marco-MiniLM-L-6-v2 cross-encoder scores (query, passage) pairs jointly. That's
  more accurate than comparing embeddings but too slow for the whole corpus, so it only reorders
  the top candidates. Scores match the sentence-transformers version to 3 decimals.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
DIM = 384
# Small rerank batches keep ONNX Runtime's working memory low: batch 4 peaked at 377 MB vs
# 561 MB at the default 64, and was faster (less padding). Measured in DECISIONS.md D-031.
RERANK_BATCH = 4


@lru_cache
def _embedder() -> Any:
    from fastembed import TextEmbedding

    return TextEmbedding(EMBED_MODEL)


@lru_cache
def _reranker() -> Any:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(RERANK_MODEL)


def query_text(text: str) -> str:
    return QUERY_PREFIX + text


def embed_passages(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    return [v.tolist() for v in _embedder().embed(texts, batch_size=batch_size)]


def embed_query(text: str) -> list[float]:
    return next(iter(_embedder().embed([query_text(text)]))).tolist()


def rerank_scores(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    return [float(s) for s in _reranker().rerank(query, passages, batch_size=RERANK_BATCH)]
