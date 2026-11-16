"""Retriever with each improvement behind its own flag, so the benchmark can add them one at a
time (an ablation ladder):

  baseline     fixed chunks, dense top-k
  +structure   section chunks with title/section headers
  +hybrid      dense + BM25 sparse, mixed by alpha
  +filters     property / doc-type filters parsed from the question
  +rerank      cross-encoder reorders the top `pool` candidates
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any

from rag.embed import embed_query, rerank_scores
from rag.ingest import BM25_PATH, pinecone_index
from rag.sparse import BM25


@dataclass(frozen=True)
class RetrievalConfig:
    name: str = "baseline"
    namespace: str = "fixed"
    hybrid: bool = False
    alpha: float = 0.5  # weight on dense; 1 - alpha on sparse
    filters: bool = False
    rerank: bool = False
    pool: int = 30  # candidates fetched before reranking


BASELINE = RetrievalConfig()
STRUCTURE = replace(BASELINE, name="+structure", namespace="structured")
HYBRID = replace(STRUCTURE, name="+hybrid", hybrid=True)
FILTERS = replace(HYBRID, name="+filters", filters=True)
IMPROVED = replace(FILTERS, name="+rerank (improved)", rerank=True)
LADDER = [BASELINE, STRUCTURE, HYBRID, FILTERS, IMPROVED]


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


# ---------------------------------------------------------------- query understanding
DOC_TYPE_HINTS: list[tuple[str, str]] = [
    (r"\bhouse rules?\b|\bquiet hours\b|\bpool\b|\bpets?\b|\bparking\b|\bguests?\b"
     r"|\bsmok", "house_rules"),
    (r"\blease\b|\blate fee\b|\bsecurity deposit\b|\bearly termination\b", "lease"),
    (r"\bsop\b|\bprocedure\b|\bstandard operating\b", "maintenance_sop"),
    (r"\bcontract\b|\bagreement\b|\bvendor\b|\btrip charge\b|\bhourly rate\b", "vendor_contract"),
    (r"\binspection\b|\binspected\b|\binspector\b", "inspection_report"),
]  # fmt: skip


@lru_cache
def _property_names() -> dict[str, int]:
    from data.generate import generate  # names are deterministic for the seed

    return {p["name"].lower(): p["id"] for p in generate().properties}


def parse_filters(query: str, doc_types: bool = False) -> dict[str, Any]:
    """Rule-based metadata extraction. It's deliberately simple, and that's the honest version: a
    production system might use an LLM or a gazetteer, but this already covers the case that
    matters (questions naming a property).

    Doc-type filtering is OFF by default: on the dev split, keyword rules misfired ("put on the
    lease" in a house-rules question, "smoke alarm" matching the smoking rule). A wrong hard
    filter makes the answer unretrievable, while a right one added little because section
    headers already disambiguate (DECISIONS.md D-021)."""
    q = query.lower()
    flt: dict[str, Any] = {}
    pids = [pid for name, pid in _property_names().items() if name in q]
    if pids:
        # portfolio-wide SOPs (property_id 0) stay eligible
        flt["property_id"] = {"$in": [*pids, 0]}
    if doc_types:
        types = sorted({t for pat, t in DOC_TYPE_HINTS if re.search(pat, q)})
        if len(types) == 1:  # ambiguous mentions -> don't restrict
            flt["doc_type"] = {"$eq": types[0]}
    return flt


# ---------------------------------------------------------------- retrieval
@lru_cache
def _bm25() -> BM25:
    return BM25.load(BM25_PATH)


@lru_cache
def _index():  # type: ignore[no-untyped-def]
    return pinecone_index()


def retrieve(query: str, cfg: RetrievalConfig = IMPROVED, k: int = 10) -> list[Hit]:
    dense = embed_query(query)
    kwargs: dict[str, Any] = {}
    if cfg.hybrid:
        sparse = _bm25().encode_query(query)
        if sparse["indices"]:  # convex combination; both sides are unit-normalised
            dense = [v * cfg.alpha for v in dense]
            kwargs["sparse_vector"] = {
                "indices": sparse["indices"],
                "values": [v * (1 - cfg.alpha) for v in sparse["values"]],
            }
    if cfg.filters and (flt := parse_filters(query)):
        kwargs["filter"] = flt
    top_k = cfg.pool if cfg.rerank else k
    res = _index().query(
        vector=dense, top_k=top_k, namespace=cfg.namespace, include_metadata=True, **kwargs
    )
    hits = [Hit(m.id, float(m.score), dict(m.metadata)) for m in res.matches]
    if cfg.rerank and hits:
        passages = [f"{h.metadata['title']} > {h.metadata['section']}\n{h.metadata['text']}"
                    for h in hits]  # fmt: skip
        for h, s in zip(hits, rerank_scores(query, passages), strict=True):
            h.score = s
        hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]
