"""`python -m rag.footprint`: peak memory of what the API holds for document search.

Loads only the two models and serves 20 queries, reranking 30 real section chunks each, in a
fresh process. This is the number to compare with the host's RAM (512 MB on the free API tier).
`make bench-rag` runs it in a subprocess and reports the result.
"""

from __future__ import annotations

import platform
import resource

from rag.chunking import structure_chunks
from rag.documents import load_docs
from rag.embed import embed_query, rerank_scores


def peak_rss_mb() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(rss / 2**20 if platform.system() == "Darwin" else rss / 2**10)  # bytes vs KiB


def main() -> None:
    chunks = [c for d in load_docs()[:40] for c in structure_chunks(d)]
    passages = [c.embed_text for c in chunks]
    for i in range(20):
        embed_query(f"what does the lease say about late fees, question {i}")
        rerank_scores("late fees", passages[i * 30 : i * 30 + 30])
    print(peak_rss_mb())


if __name__ == "__main__":
    main()
