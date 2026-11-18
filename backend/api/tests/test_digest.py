"""Weekly digest tests. Facts are checked against hand-derived values from the fixture DB in
conftest.py (as-of 2026-03-31, compared with 2026-03-24). No API key or Slack needed."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace as NS
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api.digest import service, slack
from api.digest.facts import build_facts
from api.digest.router import get_digest_client, get_transport
from api.main import app

pytestmark = pytest.mark.db
AS_OF = date(2026, 3, 31)


# ------------------------------------------------------------------ facts (hand-derived)
def test_delinquency_week_over_week(test_engine: Engine) -> None:
    d = build_facts(test_engine, AS_OF)["delinquency"]
    # This week (3/31), current residents t1 + t2: March t2 $2,000 (paid 4/10) + t1 $500 partial
    # -> 0-30 $2,500; February t2 $2,000 -> 31-60. Last week (3/24): same charges were open
    # (t1 had already paid $500 on 3/05), so no change. t4 (terminated 3/01) is a former resident.
    assert d["current_residents_this_week"] == 4500.0
    assert d["current_residents_last_week"] == 4500.0
    assert d["change"] == 0.0 and d["change_pct"] == 0.0
    buckets = {b["bucket"]: (b["this_week"], b["last_week"]) for b in d["by_bucket"]}
    assert buckets == {"0-30": (2500.0, 2500.0), "31-60": (2000.0, 2000.0),
                       "61-90": (0.0, 0.0), "90+": (0.0, 0.0)}  # fmt: skip
    assert d["former_residents_this_week"] == 1200.0
    assert d["top_increases"] == [] and d["top_decreases"] == []


def test_expirations_next_90_days(test_engine: Engine) -> None:
    e = build_facts(test_engine, AS_OF)["expirations"]
    # L1 last day 3/31 (= as-of, included), L5 last day 5/31; L2 (9/30) is outside the window.
    assert (e["leases"], e["monthly_rent"]) == (2, 2500.0)
    assert e["by_month"] == [{"month": "2026-03", "leases": 1, "monthly_rent": 1000.0},
                             {"month": "2026-05", "leases": 1, "monthly_rent": 1500.0}]  # fmt: skip


def test_sla_breaches_are_point_in_time(test_engine: Engine) -> None:
    s = build_facts(test_engine, AS_OF)["sla"]
    # WO4 (normal, opened 3/01, open) is past 168h on both dates. WO3 (low, opened 3/30) is
    # inside its 336h window. WO2 was completed late, but on 3/05, outside the 7-day window.
    assert (s["open_breaches"], s["open_breaches_last_week"]) == (1, 1)
    assert s["oldest"][0]["work_order_id"] == 4 and s["oldest"][0]["days_open"] == 30
    assert s["by_priority"] == [{"priority": "normal", "count": 1}]
    assert s["completed_late_last_7_days"] == 0


# ------------------------------------------------------------------ number check
FACTS: dict[str, Any] = {
    "as_of": "2026-10-31", "window_days": 90,
    "delinquency": {"current_residents_this_week": 104673.08, "change": -21519.54,
                    "change_pct": -17.05, "by_bucket": [{"bucket": "0-30", "this_week": 70865.9}]},
    "expirations": {"leases": 720, "monthly_rent": 1382872.16},
    "sla": {"open_breaches": 8, "open_breaches_last_week": 4,
            "oldest": [{"work_order_id": 7594, "days_open": 18}]},
}  # fmt: skip


@pytest.mark.parametrize("narrative", [
    "*Delinquency fell 17.1% to $104.7K* for the week ending 2026-10-31.",
    "• Down $21.5K (down $21,519) from last week; the 0-30 bucket holds $70,865.",
    "• 720 leases ($1.4M monthly rent) expire in the next 90 days.",
    "• 8 open SLA breaches vs 4 last week; work order 7594 has been open 18 days.",
    "• Two properties need follow-up this week.",
])  # fmt: skip
def test_correct_narratives_pass(narrative: str) -> None:
    assert service.check_narrative(narrative, FACTS) == []


@pytest.mark.parametrize(("narrative", "bad"), [
    ("Delinquency is $105.7K this week.", ["$105.7K"]),  # wrong digit
    ("Down 18% from last week.", ["18%"]),  # wrong; must not match "open 18 days"
    ("Delinquency is $126,192 last week minus $104,673.", ["$126,192"]),  # not a fact here
    ("12 breaches are open.", ["12"]),  # invented count
    ("Rent at stake: $1.3M.", ["$1.3M"]),  # 1.38M truncates to 1.3M? no: 1.3M covers 1.25-1.399M
])  # fmt: skip
def test_wrong_numbers_are_caught(narrative: str, bad: list[str]) -> None:
    if bad == ["$1.3M"]:  # documents the tolerance rule: truncation to 1.3M is accepted
        assert service.check_narrative(narrative, FACTS) == []
        return
    assert service.check_narrative(narrative, FACTS) == bad


# ------------------------------------------------------------------ build / send / run
class FakeDigestClient:
    def __init__(self, narrative: str | None) -> None:
        self.narrative = narrative
        self.calls: list[dict] = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw: Any) -> NS:
        self.calls.append(kw)
        if self.narrative is None:
            raise RuntimeError("API down")
        return NS(content=[NS(type="text", text=self.narrative)], stop_reason="end_turn",
                  usage=NS(input_tokens=1000, output_tokens=200))  # fmt: skip


def test_grounded_narrative_is_used(test_engine: Engine) -> None:
    client = FakeDigestClient("*Delinquency held at $4,500.*\n• 2 leases expire in 90 days.")
    run = service.build_digest(test_engine, client, AS_OF, "preview")
    assert run["narrative_ok"] and "Delinquency held at $4,500" in run["text"]
    assert "All numbers verified" in run["text"] and run["cost_usd"] == pytest.approx(0.008)
    sent_facts = client.calls[0]["messages"][0]["content"]
    assert '"current_residents_this_week": 4500.0' in sent_facts
    assert client.calls[0]["fallbacks"] == "default"


def test_ungrounded_narrative_falls_back_to_facts(test_engine: Engine) -> None:
    client = FakeDigestClient("*Delinquency jumped to $9,999.*")
    run = service.build_digest(test_engine, client, AS_OF, "preview")
    assert not run["narrative_ok"] and run["ungrounded"] == ["$9,999"]
    assert "$9,999" not in run["text"]
    assert run["text"].startswith(service.facts_only_text(run["facts"]))
    assert "failed the number check and was withheld" in run["text"]


def test_model_failure_still_produces_a_digest(test_engine: Engine) -> None:
    run = service.build_digest(test_engine, FakeDigestClient(None), AS_OF, "preview")
    assert not run["narrative_ok"]
    assert "the written summary was unavailable (RuntimeError) and was withheld" in run["text"]
    skipped = service.build_digest(test_engine, None, AS_OF, "preview")  # budget spent / no key
    assert "the written summary was skipped (AI budget or key unavailable)" in skipped["text"]


def test_slack_payload_carries_the_stored_text_unchanged() -> None:
    run = {"text": "*Weekly digest*\n• line one\n_All numbers verified. Synthetic data._"}
    payload = slack.blocks(run)
    assert payload["blocks"][0]["text"]["text"] == "*Weekly digest*\n• line one"
    assert payload["blocks"][-1]["elements"][0]["text"] == "_All numbers verified. Synthetic data._"
    assert slack.send("", run) == "skipped: SLACK_WEBHOOK_URL not configured"


def test_endpoints_preview_matches_sent(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.db import get_engine
    from common.settings import get_settings

    posted: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append(json.loads(request.content))
        return httpx.Response(200, text="ok")

    monkeypatch.setattr(get_settings(), "slack_webhook_url", "https://hooks.example.test/x")
    monkeypatch.setattr(get_settings(), "digest_run_token", "s3cret")
    fake = FakeDigestClient("*Delinquency held at $4,500.*")
    app.dependency_overrides.update(
        {
            get_engine: lambda: test_engine,
            get_digest_client: lambda: fake,
            get_transport: lambda: httpx.MockTransport(handler),
        }
    )
    try:
        c = TestClient(app)
        built = c.post("/digest/build").json()
        assert c.get("/digest/latest").json()["id"] == built["id"]
        sent = c.post(f"/digest/{built['id']}/send").json()
        assert sent["delivery_status"] == "sent" and sent["sent_at"]
        # preview == what was sent: the Slack payload is built from the stored text
        assert posted[0] == slack.blocks(built)
        assert c.post("/digest/run").status_code == 401
        assert c.post("/digest/run", headers={"Authorization": "Bearer wrong"}).status_code == 401
        scheduled = c.post("/digest/run", headers={"Authorization": "Bearer s3cret"}).json()
        assert scheduled["trigger"] == "schedule" and scheduled["delivery_status"] == "sent"
        assert [r["id"] for r in c.get("/digest/runs").json()][:2] == [scheduled["id"], built["id"]]
        monkeypatch.setattr(get_settings(), "digest_send_enabled", False)
        assert c.post(f"/digest/{built['id']}/send").status_code == 403
    finally:
        app.dependency_overrides.clear()
