"""`python -m rag.ingest`: parse -> chunk -> embed -> upsert into Pinecone.

One serverless index (384-d) with two namespaces, one per retrieval method:
  fixed       baseline: 1,000-character chunks
  structured  improved: one chunk per section, embedded with a "<title> > <section>" header
Idempotent: each namespace is cleared and rewritten.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Iterable
from typing import Any

from common.settings import get_settings
from rag.chunking import Chunk, fixed_chunks, structure_chunks
from rag.documents import OUT_DIR, generate_docs, load_docs, write_docs
from rag.embed import DIM, embed_passages

NAMESPACES = ("fixed", "structured")


def pinecone_index() -> Any:
    from pinecone import Pinecone, ServerlessSpec

    s = get_settings()
    if not s.pinecone_api_key:
        raise SystemExit("PINECONE_API_KEY is not set in .env")
    pc = Pinecone(api_key=s.pinecone_api_key)
    if not pc.has_index(s.pinecone_index):
        pc.create_index(
            name=s.pinecone_index,
            dimension=DIM,
            # Embeddings are unit-normalised, so dotproduct == cosine. (Kept from v0.1.0, when the
            # hybrid index required dotproduct; no reason to recreate the index.)
            metric="dotproduct",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(s.pinecone_index).status["ready"]:
            time.sleep(1)
    return pc.Index(s.pinecone_index)


def chunk_all(docs: Iterable, namespace: str) -> list[Chunk]:
    fn = fixed_chunks if namespace == "fixed" else structure_chunks
    return [c for d in docs for c in fn(d)]


def metadata(c: Chunk) -> dict[str, Any]:
    """What retrieval needs to cite a passage. Pinecone metadata can't be null, so portfolio-wide
    docs use property_id 0."""
    return {
        "doc_id": c.doc_id,
        "doc_type": c.doc_type,
        "property_id": c.property_id,
        "date": c.date,
        "title": c.title,
        "section": c.section,
        "start": c.start,
        "end": c.end,
        "text": c.text,
    }


def _wait(index: Any, namespace: str, expected: int, timeout: float = 60) -> None:
    """Pinecone is eventually consistent: wait until the namespace holds `expected` vectors."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        ns = index.describe_index_stats().namespaces.get(namespace)
        if (ns.vector_count if ns else 0) == expected:
            return
        time.sleep(1)
    raise TimeoutError(f"namespace {namespace} did not reach {expected} vectors")


def ingest(regenerate: bool = False) -> dict[str, int]:
    if regenerate or not (OUT_DIR / "manifest.jsonl").exists():
        write_docs(generate_docs(get_settings().seed))
    docs = load_docs()
    index = pinecone_index()
    counts = {}
    for ns in NAMESPACES:
        chunks = chunk_all(docs, ns)
        dense = embed_passages([c.embed_text for c in chunks])
        vectors = [
            {"id": c.chunk_id, "values": v, "metadata": metadata(c)}
            for c, v in zip(chunks, dense, strict=True)
        ]
        if ns in index.describe_index_stats().namespaces:
            index.delete(delete_all=True, namespace=ns)
            _wait(index, ns, 0)
        index.upsert(vectors=vectors, namespace=ns, batch_size=100, show_progress=False)
        _wait(index, ns, len(vectors))
        counts[ns] = len(vectors)
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--regenerate", action="store_true", help="rewrite the documents first")
    args = ap.parse_args()
    t0 = time.perf_counter()
    counts = ingest(args.regenerate)
    print(f"ingested {counts} in {time.perf_counter() - t0:.1f}s")
