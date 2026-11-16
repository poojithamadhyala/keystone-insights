"""Two chunkers over the same documents. Every chunk records its [start, end) character span in
the source document, so retrieval can be judged against span labels regardless of how the
document was cut (DECISIONS.md D-019).

* fixed_chunks: the baseline. 1,000-character windows with 200 overlap, snapped to whitespace.
  This is the common default, cut without regard to section boundaries.
* structure_chunks: one chunk per Markdown "## " section (long sections are split on
  paragraphs). The text that gets embedded is prefixed with "<doc title> > <section heading>", so
  a chunk such as "Quiet hours run from 10 p.m." still says which property it belongs to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rag.documents import Doc


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    doc_type: str
    property_id: int
    date: str
    title: str
    section: str
    start: int
    end: int
    text: str  # doc.text[start:end]
    embed_text: str  # what gets embedded / BM25-encoded


def _make(doc: Doc, i: int, start: int, end: int, section: str, header: bool) -> Chunk:
    text = doc.text[start:end].strip()
    embed = f"{doc.title} > {section}\n{text}" if header else text
    return Chunk(
        chunk_id=f"{doc.doc_id}#{i:02d}",
        doc_id=doc.doc_id,
        doc_type=doc.doc_type,
        property_id=doc.property_id,
        date=doc.date,
        title=doc.title,
        section=section,
        start=start,
        end=end,
        text=text,
        embed_text=embed,
    )


def fixed_chunks(doc: Doc, size: int = 1000, overlap: int = 200) -> list[Chunk]:
    out: list[Chunk] = []
    text, start = doc.text, 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):  # don't cut mid-word
            ws = text.rfind(" ", start + size // 2, end)
            end = ws if ws > 0 else end
        out.append(_make(doc, len(out), start, end, "", header=False))
        if end >= len(text):
            break
        nxt = end - overlap
        ws = text.find(" ", nxt)
        start = ws + 1 if 0 <= ws < end else nxt
    return out


SECTION = re.compile(r"^## (.+)$", re.M)


def structure_chunks(doc: Doc, max_chars: int = 1500) -> list[Chunk]:
    marks = [(m.start(), m.group(1).strip()) for m in SECTION.finditer(doc.text)]
    spans = [(0, marks[0][0] if marks else len(doc.text), "Overview")]
    for (s, name), nxt in zip(marks, [*(m[0] for m in marks[1:]), len(doc.text)], strict=True):
        spans.append((s, nxt, name))
    out: list[Chunk] = []
    for s, e, name in spans:
        if not doc.text[s:e].strip():
            continue
        if e - s <= max_chars:
            out.append(_make(doc, len(out), s, e, name, header=True))
            continue
        # long section: greedy paragraph packing
        cur = s
        for para in re.finditer(r"\n\n", doc.text[s:e]):
            cut = s + para.start()
            if cut - cur > max_chars:
                out.append(_make(doc, len(out), cur, cut, name, header=True))
                cur = cut
        out.append(_make(doc, len(out), cur, e, name, header=True))
    return out
