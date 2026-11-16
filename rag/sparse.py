"""Minimal BM25 sparse encoder for Pinecone hybrid search.

Document vector: one weight per term, idf * tf*(k1+1) / (tf + k1*(1 - b + b*len/avg_len)).
Query vector: the term counts. The dot product of the two is then the BM25 score.

Both vectors are L2-normalised before upsert/query (DECISIONS.md D-020). Raw BM25 scores are
unbounded (roughly 5-30 here) while cosine similarity is in [-1, 1], so without normalisation the
`alpha` weighting between dense and sparse would mean nothing.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

TOKEN = re.compile(r"[a-z0-9]+(?:[.'][a-z0-9]+)*")
STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is",
    "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "were", "will", "with",
    "what", "which", "who", "when", "where", "how", "do", "does", "i", "my", "our", "we", "you",
    "your",
}  # fmt: skip


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


def _l2(d: dict[int, float]) -> dict[str, list]:
    norm = math.sqrt(sum(v * v for v in d.values())) or 1.0
    items = sorted(d.items())
    return {"indices": [i for i, _ in items], "values": [v / norm for _, v in items]}


class BM25:
    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.avg_len = 0.0

    def fit(self, texts: list[str]) -> BM25:
        docs = [tokenize(t) for t in texts]
        df = Counter(term for d in docs for term in set(d))
        n = len(docs)
        self.vocab = {t: i for i, t in enumerate(sorted(df))}
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.avg_len = sum(map(len, docs)) / max(n, 1)
        return self

    def encode_doc(self, text: str) -> dict[str, list]:
        toks = tokenize(text)
        tf = Counter(toks)
        denom_len = self.k1 * (1 - self.b + self.b * len(toks) / self.avg_len)
        weights = {
            self.vocab[t]: self.idf[t] * c * (self.k1 + 1) / (c + denom_len)
            for t, c in tf.items()
            if t in self.vocab
        }
        return _l2(weights)

    def encode_query(self, text: str) -> dict[str, list]:
        tf = Counter(t for t in tokenize(text) if t in self.vocab)
        return _l2({self.vocab[t]: float(c) for t, c in tf.items()})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {"k1": self.k1, "b": self.b, "avg_len": self.avg_len, "idf": self.idf}
        path.write_text(json.dumps(state))

    @classmethod
    def load(cls, path: Path) -> BM25:
        s = json.loads(path.read_text())
        m = cls(s["k1"], s["b"])
        m.idf, m.avg_len = s["idf"], s["avg_len"]
        m.vocab = {t: i for i, t in enumerate(sorted(m.idf))}
        return m
