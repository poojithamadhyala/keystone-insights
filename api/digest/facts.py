"""Digest facts: every number in the weekly digest comes from these SQL queries.

Point-in-time comparison of this week (as of D) with last week (as of D - 7):
  * delinquency: current residents' outstanding rent, by aging bucket and by property, using the
    dashboard's definitions (charge-month buckets, payments count only if paid_on <= date)
  * lease expirations: active leases whose last day falls in [D, D + 90]
  * work orders breaching SLA at the date: opened by then, not completed or cancelled by then,
    older than their target. Also: tickets completed late in the past 7 days.
The narrative may only use numbers that appear here (checked by api/digest/service.py).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Engine

from api.db import fetch_all

WINDOW_DAYS = 90
SLA = "(VALUES ('emergency', 24), ('high', 72), ('normal', 168), ('low', 336))"
ACTIVE_ON = "{l}.start_date <= {d} AND {d} < COALESCE({l}.move_out_date, {l}.end_date)"

DELINQUENCY = f"""
SELECT p.name AS property,
       CASE WHEN m = 0 THEN '0-30' WHEN m = 1 THEN '31-60' WHEN m = 2 THEN '61-90' ELSE '90+' END
         AS bucket,
       current_resident, round(sum(outstanding), 2)::float AS amount,
       count(DISTINCT tenant_id) AS tenants
FROM (
  SELECT u.property_id, l.tenant_id,
         r.amount_due - CASE WHEN r.paid_on <= :d THEN r.amount_paid ELSE 0 END AS outstanding,
         (extract(year FROM CAST(:d AS date)) * 12 + extract(month FROM CAST(:d AS date)))
         - (extract(year FROM r.due_date) * 12 + extract(month FROM r.due_date)) AS m,
         EXISTS (SELECT 1 FROM leases l3 WHERE l3.tenant_id = l.tenant_id
                 AND {ACTIVE_ON.format(l="l3", d=":d")}) AS current_resident
  FROM rent_ledger r JOIN leases l ON l.id = r.lease_id JOIN units u ON u.id = l.unit_id
  WHERE r.due_date <= :d
) x JOIN properties p ON p.id = x.property_id
WHERE outstanding > 0
GROUP BY 1, 2, 3
"""

EXPIRATIONS = f"""
SELECT to_char(l.end_date - 1, 'YYYY-MM') AS month, p.name AS property,
       count(*) AS leases, sum(l.monthly_rent)::float AS monthly_rent
FROM leases l JOIN units u ON u.id = l.unit_id JOIN properties p ON p.id = u.property_id
WHERE {ACTIVE_ON.format(l="l", d=":d")}
  AND l.end_date - 1 BETWEEN CAST(:d AS date) AND CAST(:d AS date) + :window
GROUP BY 1, 2
"""

OPEN_BREACHES = f"""
SELECT w.id AS work_order_id, p.name AS property, u.unit_number AS unit, w.category,
       w.priority, v.name AS vendor,
       floor(extract(epoch FROM (CAST(:d AS date) + 1 - w.opened_at)) / 86400)::int AS days_open
FROM work_orders w
JOIN {SLA} AS s(priority, hours) ON s.priority = w.priority
JOIN properties p ON p.id = w.property_id
LEFT JOIN units u ON u.id = w.unit_id
LEFT JOIN vendors v ON v.id = w.vendor_id
WHERE w.opened_at < CAST(:d AS date) + 1
  AND w.status <> 'cancelled'
  AND (w.completed_at IS NULL OR w.completed_at >= CAST(:d AS date) + 1)
  AND CAST(:d AS date) + 1 - w.opened_at > s.hours * interval '1 hour'
ORDER BY w.opened_at
"""

COMPLETED_LATE = f"""
SELECT count(*) AS n FROM work_orders w JOIN {SLA} AS s(priority, hours) ON s.priority = w.priority
WHERE w.status = 'completed'
  AND w.completed_at >= CAST(:d AS date) - 6 AND w.completed_at < CAST(:d AS date) + 1
  AND w.completed_at - w.opened_at > s.hours * interval '1 hour'
"""

BUCKETS = ["0-30", "31-60", "61-90", "90+"]


def _r(x: float) -> float:
    return round(x, 2)


def _delinquency(engine: Engine, d: date) -> list[dict[str, Any]]:
    return fetch_all(engine, DELINQUENCY, {"d": d})


def _breaches(engine: Engine, d: date) -> list[dict[str, Any]]:
    return fetch_all(engine, OPEN_BREACHES, {"d": d})


def build_facts(engine: Engine, as_of: date) -> dict[str, Any]:
    prior = as_of - timedelta(days=7)
    now_rows, then_rows = _delinquency(engine, as_of), _delinquency(engine, prior)

    def total(rows: list[dict], key: str = "amount", current: bool = True) -> float:
        return _r(sum(r[key] for r in rows if r["current_resident"] == current))

    by_bucket = []
    for b in BUCKETS:
        tw = _r(sum(r["amount"] for r in now_rows if r["current_resident"] and r["bucket"] == b))
        lw = _r(sum(r["amount"] for r in then_rows if r["current_resident"] and r["bucket"] == b))
        by_bucket.append({"bucket": b, "this_week": tw, "last_week": lw, "change": _r(tw - lw)})

    prop_now: dict[str, float] = defaultdict(float)
    prop_then: dict[str, float] = defaultdict(float)
    for r in now_rows:
        if r["current_resident"]:
            prop_now[r["property"]] += r["amount"]
    for r in then_rows:
        if r["current_resident"]:
            prop_then[r["property"]] += r["amount"]
    changes = {p: _r(prop_now[p] - prop_then[p]) for p in set(prop_now) | set(prop_then)}
    movers: list[dict[str, Any]] = [
        {"property": p, "this_week": _r(prop_now[p]), "last_week": _r(prop_then[p]),
         "change": changes[p]}
        for p in sorted(changes, key=lambda p: (-changes[p], p))  # biggest increase first
    ]  # fmt: skip
    this_week, last_week = total(now_rows), total(then_rows)

    exp = fetch_all(engine, EXPIRATIONS, {"d": as_of, "window": WINDOW_DAYS})
    by_month: dict[str, dict[str, float]] = defaultdict(lambda: {"leases": 0, "monthly_rent": 0.0})
    by_prop: dict[str, int] = defaultdict(int)
    for r in exp:
        by_month[r["month"]]["leases"] += r["leases"]
        by_month[r["month"]]["monthly_rent"] += r["monthly_rent"]
        by_prop[r["property"]] += r["leases"]

    breaches, breaches_prior = _breaches(engine, as_of), _breaches(engine, prior)
    by_priority: dict[str, int] = defaultdict(int)
    for breach in breaches:
        by_priority[breach["priority"]] += 1
    late = fetch_all(engine, COMPLETED_LATE, {"d": as_of})[0]["n"]

    return {
        "as_of": as_of.isoformat(),
        "compared_with": prior.isoformat(),
        "window_days": WINDOW_DAYS,
        "delinquency": {
            "current_residents_this_week": this_week,
            "current_residents_last_week": last_week,
            "change": _r(this_week - last_week),
            "change_pct": _r((this_week - last_week) / last_week * 100) if last_week else None,
            "by_bucket": by_bucket,
            "top_increases": [m for m in movers if m["change"] > 0][:3],
            "top_decreases": [m for m in reversed(movers) if m["change"] < 0][:3],
            "former_residents_this_week": total(now_rows, current=False),
        },
        "expirations": {
            "leases": int(sum(v["leases"] for v in by_month.values())),
            "monthly_rent": _r(sum(v["monthly_rent"] for v in by_month.values())),
            "by_month": [
                {"month": m, "leases": int(v["leases"]), "monthly_rent": _r(v["monthly_rent"])}
                for m, v in sorted(by_month.items())
            ],  # fmt: skip
            "top_properties": [
                {"property": p, "leases": n}
                for p, n in sorted(by_prop.items(), key=lambda x: (-x[1], x[0]))[:3]
            ],  # fmt: skip
        },
        "sla": {
            "open_breaches": len(breaches),
            "open_breaches_last_week": len(breaches_prior),
            "by_priority": [
                {"priority": p, "count": by_priority[p]}
                for p in ("emergency", "high", "normal", "low")
                if by_priority[p]
            ],  # fmt: skip
            "oldest": breaches[:5],
            "completed_late_last_7_days": int(late),
        },
    }
