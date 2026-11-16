"""Public-demo safeguards (docs/shaping/public-demo.md). Enforced only when DEMO_MODE=true.

* Per-IP rate limits: an in-memory sliding window. A restart resets it, which is acceptable for a
  rate limit (the free host restarts often).
* Daily spend cap: Claude cost is recorded per UTC day in Postgres (`llm_spend`), so the cap
  survives restarts. Check-then-record means concurrent requests can overshoot the cap by at most
  their own cost (about $0.05 per agent answer, see BENCHMARKS.md); that's acceptable for a demo.
* Cached answers: real agent answers to the suggested questions, recorded with
  `python -m api.record_samples`. Served, clearly labeled, when the budget is spent or no API key
  is configured, so the demo always shows something real.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import Engine, text

from common.settings import get_settings

SAMPLES_PATH = Path(__file__).with_name("demo_samples.json")


class RateLimiter:
    """Sliding-window counter per key. Not shared across processes (one instance on the demo)."""

    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_s: float = 3600, now: float | None = None) -> int:
        """Record a hit; return 0 if allowed, else seconds until the next slot frees up."""
        now = time.monotonic() if now is None else now
        q = self.hits[key]
        while q and now - q[0] >= window_s:
            q.popleft()
        if len(q) >= limit:
            return int(window_s - (now - q[0])) + 1
        q.append(now)
        return 0


LIMITER = RateLimiter()


def client_ip(request: Request) -> str:
    """Behind Render's proxy the client is the first X-Forwarded-For entry. The header is only
    trusted when TRUST_PROXY is set; otherwise anyone could pick their own rate-limit bucket."""
    if get_settings().trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, bucket: str, limit: int) -> None:
    if not get_settings().demo_mode:
        return
    wait = LIMITER.check(f"{bucket}:{client_ip(request)}", limit)
    if wait:
        minutes = max(1, round(wait / 60))
        raise HTTPException(
            429,
            f"Demo limit reached: {limit} per hour. Try again in about {minutes} min.",
            headers={"Retry-After": str(wait)},
        )


def _today() -> Any:
    return datetime.now(UTC).date()


def spent_today(engine: Engine) -> float:
    with engine.connect() as c:
        v = c.execute(text("SELECT usd FROM llm_spend WHERE day = :d"), {"d": _today()}).scalar()
    return float(v or 0)


def record_spend(engine: Engine, usd: float) -> None:
    if usd <= 0:
        return
    with engine.begin() as c:
        c.execute(
            text("""INSERT INTO llm_spend (day, usd, calls) VALUES (:d, :u, 1)
                    ON CONFLICT (day) DO UPDATE
                    SET usd = llm_spend.usd + EXCLUDED.usd, calls = llm_spend.calls + 1"""),
            {"d": _today(), "u": round(usd, 4)},
        )


def budget_available(engine: Engine) -> bool:
    s = get_settings()
    return not s.demo_mode or spent_today(engine) < s.daily_spend_cap_usd


def load_samples() -> dict[str, list[dict[str, Any]]]:
    try:
        return json.loads(SAMPLES_PATH.read_text())
    except (OSError, ValueError):
        return {}
