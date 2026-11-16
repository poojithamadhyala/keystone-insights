"""`python -m rag.ingest`: parse -> chunk -> embed -> upsert into Pinecone.

One serverless index (dotproduct, 384-d) with two namespaces:
  fixed       baseline chunks, dense vectors only
  structured  section chunks, dense + BM25 sparse vectors (hybrid)
Idempotent: each namespace is cleared and rewritten. The BM25 statistics are saved to
artifacts/ because queries must be encoded with the same vocabulary as the documents.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from common.settings import get_settings
from rag.chunking import Chunk, fixed_chunks, structure_chunks
from rag.documents import OUT_DIR, generate_docs, load_docs, write_docs
from rag.embed import DIM, embed_passages
from rag.sparse import BM25

BM25_PATH = Path("artifacts/rag/bm25.json")
NAMESPACES = ("fixed", "structured")


def pinecone_index():  # type: ignore[no-untyped-def]
    from pinecone import Pinecone, ServerlessSpec

    s = get_settings()
    if not s.pinecone_api_key:
        raise SystemExit("PINECONE_API_KEY is not set in .env")
    pc = Pinecone(api_key=s.pinecone_api_key)
    if not pc.has_index(s.pinecone_index):
        pc.create_index(
            name=s.pinecone_index,
            dimension=DIM,
            metric="dotproduct",  # required for sparse-dense hybrid; equals cosine on unit vectors
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(s.pinecone_index).status["ready"]:
            time.sleep(1)
    return pc.Index(s.pinecone_index)


def chunk_all(docs: Iterable, namespace: str) -> list[Chunk]:
    fn = fixed_chunks if namespace == "fixed" else structure_chunks
    return [c for d in docs for c in fn(d)]


def metadata(c: Chunk) -> dict[str, Any]:
    # Filterable fields + what retrieval needs to show citations. Pinecone metadata can't be null,
    # so portfolio-wide docs use property_id 0.
    return {
        "doc_id": c.doc_id,
        "doc_type": c.doc_type,
        "property_id": c.property_id,
        "date": c.date,
        "date_int": int(c.date.replace("-", "")),  # numeric, so $gte/$lte filters work
        "title": c.title,
        "section": c.section,
        "start": c.start,
        "end": c.end,
        "text": c.text,
    }


def _wait_for_count(index, namespace: str, expected: int, timeout: float = 60) -> None:  # type: ignore[no-untyped-def]
    t0 = time.time()
    while time.time() - t0 < timeout:
        ns = index.describe_index_stats().namespaces.get(namespace)
        if ns and ns.vector_count == expected:
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
        vectors: list[dict[str, Any]] = []
        if ns == "structured":
            bm25 = BM25().fit([c.embed_text for c in chunks])
            bm25.save(BM25_PATH)
        for c, v in zip(chunks, dense, strict=True):
            vec: dict[str, Any] = {"id": c.chunk_id, "values": v, "metadata": metadata(c)}
            if ns == "structured":
                vec["sparse_values"] = bm25.encode_doc(c.embed_text)
            vectors.append(vec)
        if ns in index.describe_index_stats().namespaces:
            index.delete(delete_all=True, namespace=ns)
            _wait_for_count_zero(index, ns)
        index.upsert(vectors=vectors, namespace=ns, batch_size=100, show_progress=False)
        _wait_for_count(index, ns, len(vectors))
        counts[ns] = len(vectors)
    return counts


def _wait_for_count_zero(index, namespace: str, timeout: float = 60) -> None:  # type: ignore[no-untyped-def]
    t0 = time.time()
    while time.time() - t0 < timeout:
        if namespace not in index.describe_index_stats().namespaces:
            return
        time.sleep(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--regenerate", action="store_true", help="rewrite the documents first")
    args = ap.parse_args()
    t0 = time.perf_counter()
    counts = ingest(args.regenerate)
    print(f"ingested {counts} in {time.perf_counter() - t0:.1f}s")
