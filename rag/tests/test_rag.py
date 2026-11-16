"""RAG unit tests. None need torch, Pinecone or an API key, so they run in CI."""

import json
import math
from pathlib import Path

import pytest

from data.generate import generate
from evals.rag.apply_review import parse as parse_review
from evals.rag.generate_questions import locate
from evals.rag.metrics import Gold, Retrieved, is_relevant, score_question
from rag.chunking import fixed_chunks, structure_chunks
from rag.documents import Doc, generate_docs
from rag.retrieve import parse_filters
from rag.sparse import BM25, tokenize


@pytest.fixture(scope="module")
def ds():  # type: ignore[no-untyped-def]
    return generate(42)


@pytest.fixture(scope="module")
def docs(ds) -> list[Doc]:  # type: ignore[no-untyped-def]
    return generate_docs(42, ds)


# ------------------------------------------------------------------ documents
def test_docs_are_deterministic_and_complete(docs: list[Doc], ds) -> None:  # type: ignore[no-untyped-def]
    assert [d.text for d in generate_docs(42, ds)] == [d.text for d in docs]
    counts = {t: sum(d.doc_type == t for d in docs) for t in {d.doc_type for d in docs}}
    assert counts == {"house_rules": 20, "lease": 60, "maintenance_sop": 15,
                      "vendor_contract": 30, "inspection_report": 25}  # fmt: skip
    assert len({d.doc_id for d in docs}) == 150
    assert sum(d.injection for d in docs) == 3


def test_lease_documents_match_database_rows(docs: list[Doc], ds) -> None:  # type: ignore[no-untyped-def]
    leases = {x["id"]: x for x in ds.leases}
    for d in (x for x in docs if x.doc_type == "lease"):
        lease_id = int(d.title.split()[1].rstrip(":"))
        assert f"Monthly rent is ${leases[lease_id]['monthly_rent']:,.2f}" in d.text


# ------------------------------------------------------------------ chunking
def test_chunk_spans_point_into_the_document(docs: list[Doc]) -> None:
    for d in docs[:40]:
        for c in fixed_chunks(d) + structure_chunks(d):
            assert c.text == d.text[c.start : c.end].strip()


def test_fixed_chunks_cover_whole_document(docs: list[Doc]) -> None:
    for d in docs[:40]:
        covered: set[int] = set()
        for c in fixed_chunks(d):
            covered.update(range(c.start, c.end))
        assert covered >= {i for i, ch in enumerate(d.text) if not ch.isspace()}


def test_structure_chunks_follow_sections(docs: list[Doc]) -> None:
    d = next(x for x in docs if x.doc_type == "house_rules")
    chunks = structure_chunks(d)
    assert [c.section for c in chunks][:3] == ["Overview", "1. Quiet Hours", "2. Pets"]
    assert all(c.embed_text.startswith(f"{d.title} > {c.section}\n") for c in chunks)
    assert all(c.text.count("\n## ") == 0 for c in chunks)  # never spans two sections


# ------------------------------------------------------------------ BM25
def test_bm25_scores_term_matches_and_normalises() -> None:
    corpus = ["quiet hours start at ten", "pets require a deposit", "parking permits cost fifty"]
    bm = BM25().fit(corpus)
    q = bm.encode_query("what are the quiet hours")
    scores = []
    for text in corpus:
        dv = bm.encode_doc(text)
        dd = dict(zip(dv["indices"], dv["values"], strict=True))
        assert math.isclose(sum(v * v for v in dv["values"]), 1.0, rel_tol=1e-9)
        scores.append(
            sum(v * dd.get(i, 0.0) for i, v in zip(q["indices"], q["values"], strict=True))
        )
    assert scores[0] > 0 and scores[1] == scores[2] == 0
    assert "the" not in tokenize("the quiet hours")


def test_bm25_roundtrip(tmp_path: Path) -> None:
    bm = BM25().fit(["alpha beta", "beta gamma"])
    bm.save(tmp_path / "b.json")
    assert BM25.load(tmp_path / "b.json").encode_doc("beta gamma") == bm.encode_doc("beta gamma")


# ------------------------------------------------------------------ metrics
def test_relevance_requires_half_the_span() -> None:
    g = Gold("d1", 100, 200)
    assert is_relevant(Retrieved("d1", 0, 150), g)  # covers 50
    assert not is_relevant(Retrieved("d1", 0, 149), g)  # covers 49
    assert not is_relevant(Retrieved("d2", 0, 1000), g)  # wrong doc


def test_score_question_uses_first_relevant_rank() -> None:
    g = Gold("d1", 100, 200)
    hits = [Retrieved("d2", 0, 50), Retrieved("d1", 0, 50), Retrieved("d1", 90, 210),
            Retrieved("d1", 80, 220)]  # fmt: skip
    s = score_question(hits, g)
    assert s["recall@5"] == 1.0 and s["mrr@10"] == pytest.approx(1 / 3)
    assert s["ndcg@10"] == pytest.approx(1 / math.log2(4))  # 2nd relevant hit not counted
    assert score_question([], g) == {"recall@5": 0, "mrr@10": 0, "ndcg@10": 0, "dochit@5": 0}


# ------------------------------------------------------------------ query parsing & review
def test_property_filter_keeps_portfolio_docs() -> None:
    f = parse_filters("What are the quiet hours at Maple Court?")
    assert f == {"property_id": {"$in": [1, 0]}}  # doc-type filter off by default (D-021)
    assert "doc_type" in parse_filters("Maple Court quiet hours", doc_types=True)
    assert parse_filters("How do I handle a frozen pipe?") == {}


def test_review_parser() -> None:
    text = "## q001 (lease)\n\n**Q:** x\n\nverdict: ok\n\n## q002 (sop)\nverdict: bad wrong unit\n"
    assert parse_review(text) == {"q001": "ok", "q002": "bad wrong unit"}


def test_locate_is_whitespace_tolerant(docs: list[Doc]) -> None:
    d = docs[0]
    c = structure_chunks(d)[1]
    snippet = c.text.split("\n\n")[1][:60]
    start = d.text.find(snippet)
    assert locate(d, c, snippet) == (start, start + len(snippet))
    assert locate(d, c, "  " + snippet.replace(" ", "\n", 1)) is not None
    assert locate(d, c, "text that is not in the document") is None


# ------------------------------------------------------------------ eval set integrity
def test_eval_labels_still_match_documents(docs: list[Doc]) -> None:
    """Fails if anyone changes the document generator in a way that shifts labeled spans."""
    by_id = {d.doc_id: d for d in docs}
    rows = [json.loads(x) for x in Path("evals/rag/questions.jsonl").read_text().splitlines()]
    assert len(rows) >= 100
    for r in rows:
        assert by_id[r["doc_id"]].text[r["span_start"] : r["span_end"]] == r["evidence"], r["qid"]
