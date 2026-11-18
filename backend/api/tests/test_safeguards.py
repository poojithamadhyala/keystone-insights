"""Public-demo safeguards: rate limits, daily spend cap, cached answers (no API key needed)."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api import safeguards
from api.agent.router import get_client, get_search
from api.digest.router import get_digest_client
from api.main import app
from api.tests.test_agent import FakeClient, fake_search, parse_sse, turn
from common.settings import get_settings

pytestmark = pytest.mark.db
SAMPLE_Q = "Show occupancy by property as a bar chart."
SAMPLE = [{"type": "text", "delta": "Riverside Station leads at 97.5% [S1]."},
          {"type": "done", "cost_usd": 0.04}]  # fmt: skip


@pytest.fixture
def demo(test_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from api.db import get_engine

    s = get_settings()
    monkeypatch.setattr(s, "demo_mode", True)
    monkeypatch.setattr(s, "daily_spend_cap_usd", 2.0)
    monkeypatch.setattr(safeguards, "load_samples", lambda: {SAMPLE_Q: SAMPLE})
    safeguards.LIMITER.hits.clear()
    with test_engine.begin() as c:
        c.execute(text("DELETE FROM llm_spend"))
    app.dependency_overrides.update({get_engine: lambda: test_engine,
                                     get_search: lambda: fake_search})  # fmt: skip
    yield TestClient(app)
    app.dependency_overrides.clear()
    safeguards.LIMITER.hits.clear()


def test_rate_limiter_window() -> None:
    rl = safeguards.RateLimiter()
    assert rl.check("ip", 2, 60, now=0) == 0 and rl.check("ip", 2, 60, now=1) == 0
    assert rl.check("ip", 2, 60, now=2) == 59  # third hit blocked until t=60
    assert rl.check("other", 2, 60, now=2) == 0  # separate bucket
    assert rl.check("ip", 2, 60, now=61) == 0  # first hit expired


def test_forwarded_for_only_trusted_behind_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    req = NS(headers={"x-forwarded-for": "203.0.113.9, 10.0.0.1"}, client=NS(host="10.0.0.1"))
    assert safeguards.client_ip(req) == "10.0.0.1"  # type: ignore[arg-type]
    monkeypatch.setattr(get_settings(), "trust_proxy", True)
    assert safeguards.client_ip(req) == "203.0.113.9"  # type: ignore[arg-type]


def test_spend_accumulates_and_caps(demo: TestClient, test_engine: Engine) -> None:
    safeguards.record_spend(test_engine, 1.5)
    safeguards.record_spend(test_engine, 0.25)
    assert safeguards.spent_today(test_engine) == pytest.approx(1.75)
    assert safeguards.budget_available(test_engine)
    safeguards.record_spend(test_engine, 0.25)
    assert not safeguards.budget_available(test_engine)  # 2.00 >= cap


def test_live_answers_record_spend(demo: TestClient, test_engine: Engine) -> None:
    app.dependency_overrides[get_client] = lambda: FakeClient([turn(texts=("Hi.",))])
    events = parse_sse(demo.post("/agent/chat", json={"message": "hi"}).text)
    assert events[-1]["type"] == "done" and events[-1]["cost_usd"] > 0
    assert safeguards.spent_today(test_engine) == pytest.approx(events[-1]["cost_usd"])


def test_over_budget_serves_labeled_cached_answers(demo: TestClient, test_engine: Engine) -> None:
    safeguards.record_spend(test_engine, 5.0)
    fake = FakeClient([])  # must never be called
    app.dependency_overrides[get_client] = lambda: fake
    events = parse_sse(demo.post("/agent/chat", json={"message": SAMPLE_Q}).text)
    assert [e.get("type") for e in events[1:]] == ["notice", "text", "done"]
    assert "daily AI budget is used up" in events[1]["message"]
    assert events[-1]["cost_usd"] == 0 and events[-1]["cached"] is True
    other = parse_sse(demo.post("/agent/chat", json={"message": "anything else"}).text)
    assert other[1]["type"] == "error" and "suggested questions" in other[1]["message"]
    assert fake.calls == []


def test_no_api_key_uses_cached_answers_even_outside_demo(
    demo: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    app.dependency_overrides[get_client] = lambda: None
    events = parse_sse(demo.post("/agent/chat", json={"message": SAMPLE_Q}).text)
    assert "no AI key is configured" in events[1]["message"]


def test_rate_limit_returns_429(demo: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "agent_questions_per_hour", 1)
    app.dependency_overrides[get_client] = lambda: FakeClient([turn(texts=("ok",))])
    assert demo.post("/agent/chat", json={"message": "q1"}).status_code == 200
    r = demo.post("/agent/chat", json={"message": "q2"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert "Demo limit reached: 1 per hour" in r.json()["detail"]


def test_digest_over_budget_skips_the_model(demo: TestClient, test_engine: Engine) -> None:
    safeguards.record_spend(test_engine, 5.0)
    called: list[bool] = []
    app.dependency_overrides[get_digest_client] = lambda: NS(
        beta=NS(messages=NS(create=lambda **kw: called.append(True))))  # fmt: skip
    run = demo.post("/digest/build").json()
    assert not called and not run["narrative_ok"]
    assert "skipped (AI budget or key unavailable)" in run["text"]
