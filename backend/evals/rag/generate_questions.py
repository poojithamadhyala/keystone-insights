"""Generate candidate RAG eval questions with Claude, labeled by verbatim evidence spans.

`python -m evals.rag.generate_questions` -> evals/rag/questions.jsonl + evals/rag/REVIEW.md

For each sampled document section, Claude writes a question plus a verbatim evidence quote.
The quote is located in the document text to produce a gold [start, end) span. Candidates whose
quote isn't found verbatim are retried once and then dropped, so labels are mechanically checked
rather than taken on trust. A human then spot-checks a random sample (REVIEW.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

from common.settings import get_settings
from rag.chunking import Chunk, structure_chunks
from rag.documents import Doc, load_docs

OUT = Path("evals/rag/questions.jsonl")
REVIEW = Path("evals/rag/REVIEW.md")
PER_TYPE = {
    "house_rules": 30,
    "lease": 35,
    "maintenance_sop": 20,
    "vendor_contract": 25,
    "inspection_report": 20,
}
PRICE_IN, PRICE_OUT = 4.0, 20.0  # $/MTok for claude-opus-5-5 (Anthropic list price)

SYSTEM = """You write evaluation questions for a document-retrieval system used by property \
managers. You are given one document and one TARGET SECTION of it.

Write ONE question that:
- is answerable from the target section alone, and its answer is a specific fact there \
(a number, time, name, amount, rule or step);
- sounds like a property manager or leasing agent typing into an assistant;
- names the property, unit, lease ID or vendor when the fact is specific to this document \
(many documents share the same section layout, so a question without that context would be \
ambiguous). For portfolio-wide SOPs, don't invent a property;
- follows the requested STYLE:
  * paraphrase: avoid reusing the section's distinctive wording; ask the way a person would \
who has never seen the document;
  * keyword: may use exact names, terms and numbers from the document.

Return the question, a short answer, and EVIDENCE: the shortest verbatim substring of the \
target section (copied exactly, including punctuation, at most 300 characters) that supports \
the answer."""


class Candidate(BaseModel):
    question: str = Field(description="The question")
    answer: str = Field(description="Short answer")
    evidence: str = Field(description="Verbatim substring of the target section")


def sample_sections(docs: list[Doc], seed: int) -> list[tuple[Doc, Chunk]]:
    rng = random.Random(seed)
    out = []
    for doc_type, n in PER_TYPE.items():
        pool = [
            (d, c)
            for d in docs
            if d.doc_type == doc_type
            for c in structure_chunks(d)
            if len(c.text) >= 120 and c.section not in ("Additional Notes", "Signatures")
        ]
        out.extend(rng.sample(pool, n))
    return out


def locate(doc: Doc, chunk: Chunk, evidence: str) -> tuple[int, int] | None:
    """Exact match inside the target section, else whitespace-insensitive match."""
    i = doc.text.find(evidence, chunk.start, chunk.end)
    if i >= 0:
        return i, i + len(evidence)
    pattern = r"\s+".join(re.escape(tok) for tok in evidence.split())
    m = re.compile(pattern).search(doc.text, chunk.start, chunk.end)
    return (m.start(), m.end()) if m else None


def ask(client: anthropic.Anthropic, doc: Doc, chunk: Chunk, style: str) -> tuple[Candidate, dict]:
    prompt = (
        f"<document title={json.dumps(doc.title)}>\n{doc.text}\n</document>\n\n"
        f"<target_section>\n{chunk.text}\n</target_section>\n\nSTYLE: {style}"
    )
    resp = client.beta.messages.parse(
        model=get_settings().leaselens_model,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_format=Candidate,
        output_config={"effort": "low"},  # simple, well-specified task
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    usage = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise ValueError(f"no parsed output (stop_reason={resp.stop_reason})")
    return resp.parsed_output, usage


def split_for(qid: str) -> str:
    # stable 30/70 dev/test split by hash (independent of generation order)
    return "dev" if int(hashlib.sha1(qid.encode()).hexdigest(), 16) % 10 < 3 else "test"


def build(seed: int, workers: int = 8) -> None:
    s = get_settings()
    if not s.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set in .env")
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    docs = load_docs()
    items = sample_sections(docs, seed)
    totals = {"in": 0, "out": 0, "dropped": 0}

    def work(i_item: tuple[int, tuple[Doc, Chunk]]) -> dict | None:
        i, (doc, chunk) = i_item
        style = "paraphrase" if i % 2 == 0 else "keyword"
        for _attempt in range(2):
            try:
                cand, usage = ask(client, doc, chunk, style)
            except (anthropic.APIError, ValueError) as e:
                print(f"  {doc.doc_id}/{chunk.section}: {e}")
                continue
            totals["in"] += usage["in"]
            totals["out"] += usage["out"]
            span = locate(doc, chunk, cand.evidence)
            if span:
                qid = f"q{i:03d}"
                return {
                    "qid": qid, "split": split_for(qid), "doc_id": doc.doc_id,
                    "doc_type": doc.doc_type, "property_id": doc.property_id,
                    "section": chunk.section, "style": style, "question": cand.question,
                    "answer": cand.answer, "evidence": doc.text[span[0]:span[1]],
                    "span_start": span[0], "span_end": span[1],
                }  # fmt: skip
        totals["dropped"] += 1
        return None

    with ThreadPoolExecutor(workers) as pool:
        rows = [r for r in pool.map(work, enumerate(items)) if r]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows))
    write_review(rows, seed)
    cost = totals["in"] / 1e6 * PRICE_IN + totals["out"] / 1e6 * PRICE_OUT
    print(
        f"kept {len(rows)}/{len(items)} (dropped {totals['dropped']} without a verbatim span); "
        f"tokens in={totals['in']:,} out={totals['out']:,}; est. cost ${cost:.2f}"
    )


def write_review(rows: list[dict], seed: int, n: int = 25) -> None:
    docs = {d.doc_id: d for d in load_docs()}
    sample = random.Random(seed).sample(rows, min(n, len(rows)))
    parts = [
        "# RAG eval spot-check\n",
        "For each item, replace `verdict: ?` with `verdict: ok` or `verdict: bad <reason>`. "
        "Bad = the question is ambiguous, unanswerable from the evidence, or the answer is "
        "wrong. Then run `make rag-review` to record precision and drop bad items.\n",
    ]
    for r in sorted(sample, key=lambda x: x["qid"]):
        d = docs[r["doc_id"]]
        parts.append(
            f"\n## {r['qid']} ({r['doc_type']}, {r['style']})\n\n"
            f"**Q:** {r['question']}\n\n**A:** {r['answer']}\n\n"
            f"**Evidence** ({d.title} > {r['section']}):\n\n> {r['evidence']}\n\n"
            "verdict: ?\n"
        )
    REVIEW.write_text("".join(parts))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    build(ap.parse_args().seed)
