"""Document retrieval: one baseline and one improved method (docs/shaping/lean-rag.md).

  baseline  fixed 1,000-character chunks, dense top-k
  improved  section chunks with "<title> > <section>" headers, dense top-30, then a cross-encoder
            reranks to the top k

BM25 hybrid and metadata filters were built and measured in v0.1.0 and added nothing on this
corpus, so they were removed (DECISIONS.md D-021, D-022, D-030).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from rag.embed import embed_query, rerank_scores
from rag.ingest import pinecone_index


@dataclass(frozen=True)
class RetrievalConfig:
    name: str
    namespace: str
    rerank: bool
    pool: int = 30  # candidates fetched before reranking


BASELINE = RetrievalConfig("baseline", namespace="fixed", rerank=False)
IMPROVED = RetrievalConfig("improved", namespace="structured", rerank=True)


@dataclass
class Hit:
    chunk_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def doc_id(self) -> str:
        return str(self.metadata["doc_id"])

    @property
    def span(self) -> tuple[int, int]:
        return int(self.metadata["start"]), int(self.metadata["end"])


@lru_cache
def _index() -> Any:
    return pinecone_index()


def passage_text(h: Hit) -> str:
    return f"{h.metadata['title']} > {h.metadata['section']}\n{h.metadata['text']}"


def retrieve(query: str, cfg: RetrievalConfig = IMPROVED, k: int = 10) -> list[Hit]:
    res = _index().query(
        vector=embed_query(query),
        top_k=cfg.pool if cfg.rerank else k,
        namespace=cfg.namespace,
        include_metadata=True,
    )
    hits = [Hit(m.id, float(m.score), dict(m.metadata)) for m in res.matches]
    if cfg.rerank and hits:
        for h, s in zip(hits, rerank_scores(query, [passage_text(h) for h in hits]), strict=True):
            h.score = s
        hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]
