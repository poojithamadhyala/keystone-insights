"""`make bench-rag`: baseline vs improved retrieval on the labeled RAG eval set.

Scores the TEST split (the dev split is held back for any future tuning), reports mean and
bootstrap 95% CI per metric, p50 latency and the process's peak memory with both models
loaded (the free API host has 512 MB). Writes artifacts/rag/bench.json and rewrites the RAG
section of BENCHMARKS.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any

from evals.bench_report import hardware, update_benchmarks
from evals.rag.metrics import Gold, Retrieved, mean_ci, score_question
from rag.documents import load_docs
from rag.ingest import chunk_all
from rag.retrieve import BASELINE, IMPROVED, RetrievalConfig, retrieve

QUESTIONS = Path("evals/rag/questions.jsonl")
OUT = Path("artifacts/rag/bench.json")
REVIEW_SUMMARY = Path("evals/rag/review_summary.json")
METRICS = ["recall@5", "mrr@10", "ndcg@10", "dochit@5"]


def load_questions(split: str) -> list[dict]:
    rows = [json.loads(line) for line in QUESTIONS.read_text().splitlines()]
    return [r for r in rows if r["split"] == split and not r.get("rejected")]


def serving_footprint_mb() -> int:
    """Peak RSS of a fresh process holding only the search models (see rag/footprint.py)."""
    out = subprocess.run([sys.executable, "-m", "rag.footprint"], capture_output=True, text=True,
                         check=True).stdout  # fmt: skip
    return int(out.strip().splitlines()[-1])


def run(cfg: RetrievalConfig, questions: list[dict]) -> dict:
    per_q, latencies = [], []
    for q in questions:
        t0 = time.perf_counter()
        hits = retrieve(q["question"], cfg, k=10)
        latencies.append((time.perf_counter() - t0) * 1000)
        retrieved = [Retrieved(h.doc_id, *h.span) for h in hits]
        gold = Gold(q["doc_id"], q["span_start"], q["span_end"])
        per_q.append({"qid": q["qid"], **score_question(retrieved, gold)})
    summary: dict[str, Any] = {}
    for m in METRICS:
        mean, lo, hi = mean_ci([r[m] for r in per_q])
        summary[m] = {"mean": round(mean, 3), "ci95": [round(lo, 3), round(hi, 3)]}
    summary["latency_ms_p50"] = round(median(latencies), 1)
    return {"config": cfg.__dict__, "summary": summary, "per_question": per_q}


def main() -> None:
    test = load_questions("test")
    retrieve("warm up", IMPROVED)  # load both models / open connections before timing
    results = []
    for cfg in (BASELINE, IMPROVED):
        res = run(cfg, test)
        results.append(res)
        s = res["summary"]
        print(f"{cfg.name:9s} " + "  ".join(f"{m}={s[m]['mean']:.3f}" for m in METRICS)
              + f"  p50={s['latency_ms_p50']}ms")  # fmt: skip

    docs = load_docs()
    meta = {
        "command": "make bench-rag",
        "date": time.strftime("%Y-%m-%d"),
        "hardware": hardware(),
        "serving_peak_rss_mb": serving_footprint_mb(),
        "dataset": {
            "documents": len(docs),
            "chunks_fixed": len(chunk_all(docs, "fixed")),
            "chunks_structured": len(chunk_all(docs, "structured")),
            "questions_test": len(test),
        },
        "label_review": (
            json.loads(REVIEW_SUMMARY.read_text()) if REVIEW_SUMMARY.exists() else None
        ),
    }
    print(f"serving footprint {meta['serving_peak_rss_mb']} MB")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"meta": meta, "results": results}, indent=1))
    update_benchmarks("rag", render(meta, results))
    print(f"wrote {OUT} and updated BENCHMARKS.md")


def render(meta: dict, results: list[dict]) -> str:
    d = meta["dataset"]
    review = meta["label_review"]
    lines = [
        "## RAG retrieval\n",
        f"- **Command:** `{meta['command']}`",
        f"- **Date:** {meta['date']}",
        f"- **Hardware:** {meta['hardware']}",
        f"- **Dataset:** {d['documents']} synthetic documents ({d['chunks_fixed']} fixed / "
        f"{d['chunks_structured']} section chunks), {d['questions_test']} test questions. "
        "Labels are verbatim evidence spans; a chunk is relevant if it covers at least 50% "
        "of the span.",
        "- **Label spot-check:** "
        + (
            f"{review['ok']}/{review['reviewed']} sampled questions judged correct by a human "
            "reviewer; rejected items are excluded"
            if review
            else "pending (labels are Claude-generated, span-verified)"
        ),
        "- **Methods:** *baseline* = fixed 1,000-character chunks (200 overlap), dense top-10. "
        "*improved* = one chunk per section with a title/section header, dense top-30, "
        "reranked by a cross-encoder to top-10. Models: bge-small-en-v1.5 and "
        "ms-marco-MiniLM-L-6-v2 via fastembed (ONNX, CPU).",
        "",
        "Brackets are bootstrap 95% CIs.",
        "",
        "| Method | Recall@5 | MRR@10 | nDCG@10 | Right doc @5 | p50 latency |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        s = r["summary"]

        def cell(m: str, s: dict = s) -> str:
            lo, hi = s[m]["ci95"]
            return f"{s[m]['mean']:.3f} [{lo:.2f}, {hi:.2f}]"

        lines.append(
            f"| {r['config']['name']} | {cell('recall@5')} | {cell('mrr@10')} | "
            f"{cell('ndcg@10')} | {cell('dochit@5')} | {s['latency_ms_p50']:.0f} ms |"
        )
    lines += [
        "",
        f"Search serving footprint: **{meta['serving_peak_rss_mb']} MB** peak RSS for a fresh "
        "process holding both models and serving 20 queries (`python -m rag.footprint`, macOS). "
        "The free API host has 512 MB; the deployed API is re-measured there.",
        "Latency includes query embedding, the Pinecone round trip from a home network and, "
        "for *improved*, reranking 30 candidates on CPU. Pinecone serverless search is "
        "approximate (ANN), so repeated runs can move a metric in the third decimal (observed: "
        "baseline MRR 0.551 vs 0.553 on identical index and code).",
        "",
        "BM25 hybrid search and metadata filters were also built and measured in v0.1.0. "
        "Neither improved results on this corpus, so they were removed (DECISIONS.md "
        "D-021, D-022, D-030).",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
