"""Span-based retrieval metrics (DECISIONS.md D-019).

A retrieved chunk is *relevant* to a question if it is from the gold document and contains at
least `min_cover` (50%) of the gold evidence span. Labels are character spans, not chunk ids, so
the same labels score any chunking strategy fairly.

Each question has one gold span, so ranking metrics use the first relevant hit only:
  Recall@k  1 if a relevant chunk is in the top k
  MRR@10    1 / rank of the first relevant chunk (0 if not in the top 10)
  nDCG@10   1 / log2(rank + 1) for the first relevant chunk. With one relevant item the ideal DCG
            is 1, and overlapping chunks that cover the same span are not double-counted.
  DocHit@5  1 if any top-5 chunk is from the gold document (right doc, maybe wrong passage)
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Gold:
    doc_id: str
    start: int
    end: int


@dataclass(frozen=True)
class Retrieved:
    doc_id: str
    start: int
    end: int


def is_relevant(r: Retrieved, g: Gold, min_cover: float = 0.5) -> bool:
    if r.doc_id != g.doc_id:
        return False
    overlap = max(0, min(r.end, g.end) - max(r.start, g.start))
    return overlap >= min_cover * (g.end - g.start)


def first_relevant_rank(hits: Sequence[Retrieved], g: Gold) -> int | None:
    for rank, h in enumerate(hits, start=1):
        if is_relevant(h, g):
            return rank
    return None


def score_question(hits: Sequence[Retrieved], g: Gold) -> dict[str, float]:
    rank = first_relevant_rank(hits, g)
    return {
        "recall@5": 1.0 if rank is not None and rank <= 5 else 0.0,
        "mrr@10": 1.0 / rank if rank is not None and rank <= 10 else 0.0,
        "ndcg@10": 1.0 / math.log2(rank + 1) if rank is not None and rank <= 10 else 0.0,
        "dochit@5": 1.0 if any(h.doc_id == g.doc_id for h in hits[:5]) else 0.0,
    }


def mean_ci(
    values: Sequence[float], n_boot: int = 2000, seed: int = 0
) -> tuple[float, float, float]:
    """Mean and 95% percentile-bootstrap interval."""
    mean = sum(values) / len(values)
    rng = random.Random(seed)
    boots = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n_boot))
    return mean, boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot) - 1]
