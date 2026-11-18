"""Build, check, store and send the weekly digest.

build_digest: SQL facts -> Claude narrative (facts JSON only, no tools) -> NUMBER CHECK.
  Every number in the narrative must match a value in the facts (common.numbers; rounding or
  truncation to the written precision is allowed). If any number is ungrounded, or the model
  call fails, the digest falls back to a deterministic facts-only text and is flagged.
The stored `text` is exactly what the preview shows and what Send now delivers.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

from api.digest.facts import build_facts
from common.numbers import numeric_values, ungrounded
from common.settings import get_settings

PROMPTS = Path("prompts/digest")
PROMPT_VERSION = "v1"
PRICES = {"input": 4.0, "output": 20.0}  # $ per MTok, claude-opus-5-5


def money(v: float) -> str:
    return f"${abs(v):,.0f}"


def facts_only_text(f: dict[str, Any]) -> str:
    """Deterministic digest built straight from the facts: the fallback, and the reference
    the narrative is checked against."""
    d, e, s = f["delinquency"], f["expirations"], f["sla"]
    direction = "down" if d["change"] < 0 else "up"
    lines = [
        f"*Weekly portfolio digest, week ending {f['as_of']}*",
        f"• Delinquency (current residents): {money(d['current_residents_this_week'])}, "
        f"{direction} {money(d['change'])} from {money(d['current_residents_last_week'])} "
        f"last week.",
        f"• Leases expiring in the next {f['window_days']} days: {e['leases']} "
        f"({money(e['monthly_rent'])} monthly rent).",
        f"• Work orders breaching SLA: {s['open_breaches']} open "
        f"(last week {s['open_breaches_last_week']}); "
        f"{s['completed_late_last_7_days']} completed late in the past 7 days.",
    ]
    if s["oldest"]:
        o = s["oldest"][0]
        lines.append(
            f"• Oldest breach: work order {o['work_order_id']} at {o['property']} "
            f"({o['category']}, {o['priority']}), open {o['days_open']} days."
        )
    return "\n".join(lines)


def _with_abs(vals: list[float]) -> list[float]:
    # Decreases may be written as positive amounts ("down $21.5K").
    return vals + [abs(v) for v in vals if v < 0]


def grounding_sources(f: dict[str, Any]) -> tuple[list[float], list[float]]:
    """(all fact values, percentage facts). A "%" in the narrative may only match a *_pct fact."""
    pct = numeric_values(f, key=lambda k: k.endswith("_pct"))
    return _with_abs(numeric_values(f)), _with_abs(pct)


def check_narrative(narrative: str, f: dict[str, Any]) -> list[str]:
    """Return the numbers in `narrative` that don't match any fact (empty list = passes)."""
    values, percents = grounding_sources(f)
    return [m.raw for m in ungrounded(narrative, values, percent_sources=percents)]


def write_narrative(client: Any, f: dict[str, Any]) -> tuple[str, float]:
    s = get_settings()
    system = (PROMPTS / f"narrative_{PROMPT_VERSION}.md").read_text()
    resp = client.beta.messages.create(
        model=s.leaselens_model,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": f"<facts>\n{json.dumps(f, indent=1)}\n</facts>"}],
        output_config={"effort": "low"},  # short, tightly-specified writing task
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    cost = (resp.usage.input_tokens * PRICES["input"]
            + resp.usage.output_tokens * PRICES["output"]) / 1e6  # fmt: skip
    if resp.stop_reason == "refusal":
        raise RuntimeError("narrative request was declined")
    narrative = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    return narrative, cost


def build_digest(engine: Engine, client: Any, as_of: date, trigger: str) -> dict[str, Any]:
    facts = build_facts(engine, as_of)
    narrative, cost, error = "", 0.0, None
    if client is None:  # no API key, or the demo's daily AI budget is spent
        error = "was skipped (AI budget or key unavailable)"
    else:
        try:
            narrative, cost = write_narrative(client, facts)
        except Exception as e:  # API down, refusal, ...: the digest still goes out, facts-only
            error = f"was unavailable ({type(e).__name__})"
    bad = check_narrative(narrative, facts) if narrative else []
    ok = bool(narrative) and not bad
    body = narrative if ok else facts_only_text(facts)
    # Rejected numbers are kept in `ungrounded` for the operator's preview but never put in the
    # delivered text: readers shouldn't see the wrong figure at all.
    reason = "failed the number check" if bad else (error or "was unavailable")
    footer = ("_All numbers verified against SQL. Synthetic data._" if ok else
              f"_Facts-only version: the written summary {reason} and was withheld. "
              "Synthetic data._")  # fmt: skip
    if ok:
        body = f"*Weekly portfolio digest, week ending {facts['as_of']}*\n{body}"
    row = {
        "as_of": as_of, "trigger": trigger, "facts": json.dumps(facts, default=str),
        "text": f"{body}\n{footer}", "narrative_ok": ok, "ungrounded": json.dumps(bad),
        "model": get_settings().leaselens_model, "prompt_version": PROMPT_VERSION,
        "cost_usd": round(cost, 4),
    }  # fmt: skip
    with engine.begin() as c:
        rid = c.execute(text("""
            INSERT INTO digest_runs (as_of, trigger, facts, text, narrative_ok, ungrounded,
                                     model, prompt_version, cost_usd)
            VALUES (:as_of, :trigger, CAST(:facts AS jsonb), :text, :narrative_ok,
                    CAST(:ungrounded AS jsonb), :model, :prompt_version, :cost_usd)
            RETURNING id"""), row).scalar_one()  # fmt: skip
    return get_run(engine, rid) or {}


RUN_COLUMNS = """id, created_at, as_of, trigger, facts, text, narrative_ok, ungrounded, model,
                 prompt_version, cost_usd::float AS cost_usd, sent_at, delivery_status"""


def get_run(engine: Engine, run_id: int | None = None) -> dict[str, Any] | None:
    # The preview is the latest real digest; benchmark runs are never shown or sent.
    where = "WHERE id = :id" if run_id is not None else "WHERE trigger <> 'bench'"
    with engine.connect() as c:
        r = (
            c.execute(
                text(f"SELECT {RUN_COLUMNS} FROM digest_runs {where} ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            .mappings()
            .first()
        )
    return dict(r) if r else None


def list_runs(engine: Engine, limit: int = 10) -> list[dict[str, Any]]:
    with engine.connect() as c:
        rows = (
            c.execute(
                text("""SELECT id, created_at, as_of, trigger, narrative_ok,
            cost_usd::float AS cost_usd, sent_at, delivery_status FROM digest_runs
            WHERE trigger <> 'bench' ORDER BY id DESC LIMIT :n"""),
                {"n": limit},
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]


def record_delivery(engine: Engine, run_id: int, status: str, sent: bool) -> None:
    with engine.begin() as c:
        c.execute(text("UPDATE digest_runs SET delivery_status = :s, "
                       "sent_at = CASE WHEN :sent THEN now() ELSE sent_at END WHERE id = :id"),
                  {"s": status[:200], "sent": sent, "id": run_id})  # fmt: skip
