"""Find numbers in generated text and check each one against source values.

Used by the agent eval (faithfulness: every number in an answer must come from a tool result)
and by the weekly digest (the narrative fails if any number doesn't match the SQL facts).

A mention matches a source value v if the mention is v rounded OR truncated to the precision it
was written with, i.e. v in [written - half a unit, written + one unit): "$1.2K" matches
1,150-1,299; "94.4%" matches 0.9435-0.9450 or 94.35-94.50; "$1,845" matches 1,844.5-1,845.99
(cents dropped or rounded). Dates, times, and "0-30"-style bucket labels are ignored, since
they aren't quantitative claims.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

SCALE = {"k": 1e3, "m": 1e6, "b": 1e9}
NUMBER = re.compile(
    r"(?P<money>\$)?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suffix>\s?[KkMmBb](?![A-Za-z]))?(?P<pct>\s?%)?"
)
# Spans that look numeric but aren't claims.
IGNORE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"  # ISO dates
    r"|\b\d{1,2}:\d{2}\b"  # times
    r"|\b(?:19|20)\d{2}\b"  # years
    r"|\b\d{1,2}[-–]\d{1,2}\b"  # ranges such as 0-30 (aging bucket labels)
    r"|\b\d+\+"  # 90+
    r"|\[[SD]\d+\]"  # citation markers [S1] [D2]
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}"
    r"(?:\s?[-–]\s?\d{1,2})?\b"  # Oct 31, September 1–30
)


@dataclass(frozen=True)
class Mention:
    raw: str
    value: float  # in base units (percent kept as written: "94.4%" -> 94.4)
    unit: float  # value of one unit in the last written digit
    percent: bool
    start: int


def _decimals(num: str) -> int:
    return len(num.split(".")[1]) if "." in num else 0


def extract(text: str) -> list[Mention]:
    ignored = [m.span() for m in IGNORE.finditer(text)]
    out = []
    for m in NUMBER.finditer(text):
        if any(a <= m.start() < b for a, b in ignored):
            continue
        num = m.group("num")
        value = float(num.replace(",", ""))
        scale = SCALE[m.group("suffix").strip().lower()] if m.group("suffix") else 1.0
        unit = 10 ** (-_decimals(num)) * scale
        out.append(
            Mention(m.group(0).strip(), value * scale, unit, bool(m.group("pct")), m.start())
        )
    return out


def numeric_values(
    obj: object, key: Callable[[str], bool] | None = None, _parent: str = ""
) -> list[float]:
    """All numbers inside nested JSON-like data (and numbers written inside strings).
    With `key`, only values stored under dict keys for which key(name) is true."""
    vals: list[float] = []
    take = key is None or key(_parent)
    if isinstance(obj, bool) or obj is None:
        return vals
    if isinstance(obj, int | float):
        if take and math.isfinite(obj):
            vals.append(float(obj))
    elif isinstance(obj, str):
        if take:
            vals.extend(m.value for m in extract(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            vals.extend(numeric_values(v, key, str(k)))
    elif isinstance(obj, Iterable):
        for v in obj:
            vals.extend(numeric_values(v, key, _parent))
    return vals


def matches(m: Mention, sources: Iterable[float]) -> bool:
    eps = 1e-9
    for s in sources:
        candidates = [s]
        if m.percent:
            candidates.append(s * 100)  # a fraction 0.944 written as 94.4%
        if any(m.value - 0.5 * m.unit - eps <= c < m.value + m.unit - eps for c in candidates):
            return True
    return False


def ungrounded(
    text: str, sources: Iterable[float], percent_sources: Iterable[float] | None = None
) -> list[Mention]:
    """Mentions in `text` that match no source value. Small integers (0-10) are allowed, since
    they're usually counts in prose ("two properties", "top 5").

    If `percent_sources` is given, a "%" mention may only match those values. Otherwise "18%"
    could be "grounded" by an unrelated fact such as "open 18 days"."""
    src = list(sources)
    pct = list(percent_sources) if percent_sources is not None else src
    return [
        m
        for m in extract(text)
        if not (m.value <= 10 and not m.percent) and not matches(m, pct if m.percent else src)
    ]
