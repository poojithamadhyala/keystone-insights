"""`make rag-review`: read verdicts from evals/rag/REVIEW.md, mark rejected questions in
questions.jsonl (the benchmark skips them), and record label precision for BENCHMARKS.md."""

from __future__ import annotations

import json
import re
from pathlib import Path

from evals.rag.generate_questions import OUT as QUESTIONS
from evals.rag.generate_questions import REVIEW

SUMMARY = Path("evals/rag/review_summary.json")
ITEM = re.compile(r"^## (q\d+).*?^verdict:[ \t]*([^\n]*)", re.M | re.S)


def parse(text: str) -> dict[str, str]:
    return {qid: verdict.strip() for qid, verdict in ITEM.findall(text)}


def main() -> None:
    verdicts = parse(REVIEW.read_text())
    pending = [q for q, v in verdicts.items() if v == "?"]
    if pending:
        raise SystemExit(
            f"{len(pending)} items still have 'verdict: ?' ({', '.join(pending[:5])}...)"
        )
    bad = {q: v.removeprefix("bad").strip() for q, v in verdicts.items() if v.startswith("bad")}
    rows = [json.loads(line) for line in QUESTIONS.read_text().splitlines()]
    for r in rows:
        if r["qid"] in bad:
            r["rejected"] = bad[r["qid"]] or "rejected in review"
    QUESTIONS.write_text("".join(json.dumps(r) + "\n" for r in rows))
    ok = len(verdicts) - len(bad)
    summary = {"reviewed": len(verdicts), "ok": ok, "bad": len(bad),
               "precision": round(ok / len(verdicts), 3)}  # fmt: skip
    SUMMARY.write_text(json.dumps(summary, indent=1) + "\n")
    print(f"spot-check: {ok}/{len(verdicts)} ok; {len(bad)} rejected -> rerun `make bench-rag`")


if __name__ == "__main__":
    main()
