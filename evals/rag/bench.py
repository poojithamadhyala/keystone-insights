"""`make bench-rag`: ablation ladder over the labeled RAG eval set.

1. Tune the hybrid weight `alpha` on the DEV split only (grid search on nDCG@10).
2. Run every ladder step on the TEST split; report mean and bootstrap 95% CI.
3. Write artifacts/rag/bench.json and update the RAG section of BENCHMARKS.md.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from statistics import median
from typing import Any

from evals.bench_report import hardware, update_benchmarks
from evals.rag.metrics import Gold, Retrieved, mean_ci, score_question
from rag.documents import load_docs
from rag.ingest import chunk_all
from rag.retrieve import HYBRID, LADDER, RetrievalConfig, retrieve

QUESTIONS = Path("evals/rag/questions.jsonl")
OUT = Path("artifacts/rag/bench.json")
REVIEW_SUMMARY = Path("evals/rag/review_summary.json")
ALPHAS = [0.3, 0.5, 0.7, 0.85, 1.0]  # 1.0 = dense only
METRICS = ["recall@5", "mrr@10", "ndcg@10", "dochit@5"]


def load_questions(split: str) -> list[dict]:
    rows = [json.loads(line) for line in QUESTIONS.read_text().splitlines()]
    return [r for r in rows if r["split"] == split and not r.get("rejected")]


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
    dev, test = load_questions("dev"), load_questions("test")
    # warm-up: load models / open connections so the first measured query isn't penalised
    retrieve("warm up", replace(LADDER[-1]))

    tuning = {a: run(replace(HYBRID, alpha=a), dev)["summary"]["ndcg@10"]["mean"] for a in ALPHAS}
    alpha = max(tuning, key=lambda a: tuning[a])
    print(f"alpha tuning on dev (nDCG@10): {tuning} -> alpha={alpha}")

    results = []
    ladder = [replace(c, alpha=alpha) for c in LADDER]
    if alpha == 1.0:  # tuned hybrid == dense only; show what BM25 does, clearly labeled
        ladder.insert(3, replace(HYBRID, name="(ref) hybrid α=0.5, not selected", alpha=0.5))
    for cfg in ladder:
        res = run(cfg, test)
        results.append(res)
        s = res["summary"]
        print(f"{cfg.name:20s} " + "  ".join(f"{m}={s[m]['mean']:.3f}" for m in METRICS)
              + f"  p50={s['latency_ms_p50']}ms")  # fmt: skip

    docs = load_docs()
    meta = {
        "command": "make bench-rag",
        "date": time.strftime("%Y-%m-%d"),
        "hardware": hardware(),
        "dataset": {
            "documents": len(docs),
            "chunks_fixed": len(chunk_all(docs, "fixed")),
            "chunks_structured": len(chunk_all(docs, "structured")),
            "questions_test": len(test),
            "questions_dev": len(dev),
        },
        "label_review": (
            json.loads(REVIEW_SUMMARY.read_text()) if REVIEW_SUMMARY.exists() else None
        ),
        "alpha_tuning_dev_ndcg10": tuning,
        "alpha": alpha,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"meta": meta, "results": results}, indent=1))
    update_benchmarks("rag", render(meta, results))
    print(f"wrote {OUT} and updated BENCHMARKS.md")


def render(meta: dict, results: list[dict]) -> str:
    d = meta["dataset"]
    lines = [
        "## RAG retrieval (component 2)\n",
        f"- **Command:** `{meta['command']}`",
        f"- **Date:** {meta['date']}",
        f"- **Hardware:** {meta['hardware']}",
        f"- **Dataset:** {d['documents']} synthetic documents ({d['chunks_fixed']} fixed / "
        f"{d['chunks_structured']} section chunks). {d['questions_test']} test questions "
        f"({d['questions_dev']} dev questions used only to tune alpha). Labels are verbatim "
        "evidence spans; a chunk is relevant if it covers at least 50% of the span.",
        "- **Label spot-check:** "
        + (
            f"{meta['label_review']['ok']}/{meta['label_review']['reviewed']} sampled questions "
            "judged correct by a human reviewer; rejected items are excluded"
            if meta["label_review"]
            else "pending (labels are Claude-generated, span-verified)"
        ),
        f"- **Hybrid alpha** (dense weight) tuned on dev: {meta['alpha']} "
        f"(dev nDCG@10 by alpha: {meta['alpha_tuning_dev_ndcg10']})",
        "",
        "Each row adds one change to the row above. Brackets are bootstrap 95% CIs.",
        "",
        "| Variant | Recall@5 | MRR@10 | nDCG@10 | Right doc @5 | p50 latency |",
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
    lines.append(
        "\nLatency includes local query embedding, the Pinecone round trip from a home network "
        "and, for the last row, cross-encoder reranking of 30 candidates on the local device."
    )
    if meta["alpha"] == 1.0:
        lines.append(
            "\n**Reading the table:** alpha tuned on dev came out at 1.0 (dense only), so "
            '"+hybrid" is the same as "+structure": BM25 did not improve dev nDCG@10 at any '
            "weight. The reference row shows hybrid at alpha 0.5 on test, for comparison only. "
            '"+filters" (property filter parsed from the question) also changed no rankings: '
            "the title/section header on each chunk already identifies the property. Both stay "
            "in the pipeline as switchable options, but the measured gains come from section "
            "chunking and reranking. Doc-type filters were dropped after dev analysis showed "
            "keyword misfires (DECISIONS.md D-021)."
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
