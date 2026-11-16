"""`make bench-digest`: how often does the LLM narrative pass the number check?

Builds the digest N times against the real dataset (trigger 'bench', never shown or sent) and
reports the pass rate, every rejected number, and cost. A failed check is not a broken digest
(it falls back to the facts-only text), but the pass rate says how often readers get the written
summary instead of the fallback.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import anthropic

from api.db import get_engine
from api.digest import service
from api.kpis.router import dataset_as_of
from common.settings import get_settings
from evals.bench_report import update_benchmarks

OUT = Path("artifacts/digest/bench.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=10)
    n = ap.parse_args().n
    s = get_settings()
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    engine = get_engine()
    as_of = dataset_as_of(engine)
    runs = []
    for i in range(n):
        r = service.build_digest(engine, client, as_of, trigger="bench")
        runs.append({"id": r["id"], "ok": r["narrative_ok"], "ungrounded": r["ungrounded"],
                     "cost_usd": r["cost_usd"], "text": r["text"]})  # fmt: skip
        print(f"run {i + 1}/{n}: {'PASS' if r['narrative_ok'] else 'FAIL ' + str(r['ungrounded'])}")
    passed = sum(r["ok"] for r in runs)
    meta = {"date": time.strftime("%Y-%m-%d"), "model": s.leaselens_model, "n": n,
            "prompt_version": service.PROMPT_VERSION, "as_of": as_of.isoformat(),
            "passed": passed, "cost_usd": round(sum(r["cost_usd"] for r in runs), 3),
            "rejected_numbers": [u for r in runs for u in r["ungrounded"]]}  # fmt: skip
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"meta": meta, "runs": runs}, indent=1))
    update_benchmarks("digest", render(meta))
    print(json.dumps(meta, indent=1))


def render(m: dict) -> str:
    rejected = ", ".join(f"`{x}`" for x in m["rejected_numbers"]) or "none"
    return "\n".join([
        "## Weekly digest number check\n",
        "- **Command:** `make bench-digest`",
        f"- **Date:** {m['date']}",
        f"- **Model / prompt:** `{m['model']}` / "
        f"`prompts/digest/narrative_{m['prompt_version']}.md`",
        f"- **Dataset:** digest for the week ending {m['as_of']}, built {m['n']} times",
        "",
        "| Narratives passing the number check | Rejected numbers | Cost |",
        "|---|---|---|",
        f"| {m['passed']}/{m['n']} | {rejected} | ${m['cost_usd']} |",
        "",
        "Every number in the written summary must match a SQL fact (rounding or truncation to the "
        "written precision allowed; percentages only match percentage facts). A failed check "
        "doesn't stop the digest: it goes out as the facts-only version, flagged. The pass rate "
        "is how often readers get the written summary.",
    ]) + "\n"  # fmt: skip


if __name__ == "__main__":
    main()
