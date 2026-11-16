"""Agent tests with a scripted fake Claude client (no API key, no cost; runs in CI).

They exercise the real loop, the real SQL guard and real SQL against the hand-built fixture DB
from conftest.py (as-of 2026-03-31, 'Test Place' has 4 units)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace as NS
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api.agent import loop as agent_loop
from api.agent.loop import CANARY, Conversation, run_turn, sanitize_fallback, system_prompt
from api.agent.router import get_client, get_search
from api.agent.sql_guard import SqlRejected, check_sql, run_readonly
from api.agent.tools import ToolContext
from api.main import app

pytestmark = pytest.mark.db


# ------------------------------------------------------------------ fake Claude
def tool_use(id_: str, name: str, **inp: Any) -> NS:
    return NS(type="tool_use", id=id_, name=name, input=inp)


def turn(*blocks: NS, stop: str | None = None, texts: tuple[str, ...] = ()) -> NS:
    has_tool = any(b.type == "tool_use" for b in blocks)
    content = [*blocks, *(NS(type="text", text=t) for t in texts)]
    usage = NS(input_tokens=1000, output_tokens=100, cache_creation_input_tokens=0,
               cache_read_input_tokens=500)  # fmt: skip
    return NS(content=content, stop_reason=stop or ("tool_use" if has_tool else "end_turn"),
              usage=usage, texts=texts)  # fmt: skip


class FakeStream:
    def __init__(self, msg: NS) -> None:
        self.msg = msg

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def __aiter__(self) -> AsyncIterator[NS]:
        async def gen() -> AsyncIterator[NS]:
            for t in self.msg.texts:
                yield NS(type="text", text=t)

        return gen()

    async def get_final_message(self) -> NS:
        return self.msg


class FakeClient:
    """Returns scripted turns in order; records every request."""

    def __init__(self, turns: list[NS]) -> None:
        self.turns, self.calls = list(turns), []  # type: ignore[var-annotated]
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return FakeStream(self.turns.pop(0))


def fake_search(query: str, k: int) -> list[dict[str, Any]]:
    return [{"doc_id": "lease-001", "title": "Lease 1: Test Place Unit 101",
             "section": "3. Rent and Late Fees",
             "text": "A late fee of $50 will be charged."}]  # fmt: skip


async def collect(client: FakeClient, conv: Conversation, msg: str) -> list[dict]:
    return [ev async for ev in run_turn(client, conv, msg)]


# ------------------------------------------------------------------ loop behaviour
def test_full_turn_with_sql_report_and_citation(test_engine: Engine) -> None:
    client = FakeClient([
        turn(tool_use("t1", "query_kpis", purpose="units at Test Place",
             sql="SELECT p.name, count(*) AS units FROM reporting.units u "
                 "JOIN reporting.properties p ON p.id = u.property_id GROUP BY p.name")),
        turn(tool_use("t2", "generate_report", title="Units", chart="bar", result_id="S1",
                      x="name", y=["units"], summary="Units by property [S1].")),
        turn(texts=("Test Place has 4 units ", "[S1].")),
    ])  # fmt: skip
    conv = Conversation(ToolContext(test_engine, fake_search))
    events = asyncio.run(collect(client, conv, "How many units per property?"))
    kinds = [e["type"] for e in events]
    assert kinds == ["tool_start", "sql_result", "tool_start", "report", "text", "text", "done"]
    sql = next(e for e in events if e["type"] == "sql_result")
    assert sql["id"] == "S1" and sorted(sql["rows"]) == [["Other Place", 1], ["Test Place", 4]]
    assert "LIMIT 201" in sql["sql"]
    report = next(e for e in events if e["type"] == "report")
    assert report["rows"] == [{"name": r[0], "units": r[1]} for r in sql["rows"]]
    # history alternates and tool results are marked untrusted
    roles = [m["role"] for m in conv.messages]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]
    assert 'trust="untrusted"' in conv.messages[2]["content"][0]["content"]
    # request shape: cached prefix, fallbacks on, effort set, as-of date in the system prompt
    first = client.calls[0]
    assert first["cache_control"] == {"type": "ephemeral"} and first["fallbacks"] == "default"
    assert first["output_config"] == {"effort": "medium"} and "2026-03-31" in first["system"]
    done = events[-1]
    assert done["usage"]["input"] == 3000 and done["cost_usd"] == pytest.approx(
        (3000 * 4 + 300 * 20 + 1500 * 0.2) / 1e6
    )


def test_guard_rejection_is_returned_to_the_model(test_engine: Engine) -> None:
    client = FakeClient([
        turn(tool_use("t1", "query_kpis", purpose="x", sql="SELECT email FROM public.tenants")),
        turn(texts=("I can't access contact details.",)),
    ])  # fmt: skip
    conv = Conversation(ToolContext(test_engine, fake_search))
    events = asyncio.run(collect(client, conv, "List tenant emails"))
    assert not any(e["type"] == "sql_result" for e in events)
    result = conv.messages[2]["content"][0]
    assert result["is_error"] and "not allowed" in result["content"]


def test_invalid_tool_input_fails_cleanly(test_engine: Engine) -> None:
    client = FakeClient([
        turn(tool_use("t1", "generate_report", title="x", chart="pie", result_id="S9", x="a",
                      y=["b"], summary="s")),
        turn(texts=("Sorry.",)),
    ])  # fmt: skip
    conv = Conversation(ToolContext(test_engine, fake_search))
    asyncio.run(collect(client, conv, "chart"))
    assert conv.messages[2]["content"][0]["is_error"]


def test_documents_get_passage_ids(test_engine: Engine) -> None:
    client = FakeClient([
        turn(tool_use("t1", "search_documents", query="late fee Test Place", k=3)),
        turn(texts=("The late fee is $50 [D1].",)),
    ])  # fmt: skip
    conv = Conversation(ToolContext(test_engine, fake_search))
    events = asyncio.run(collect(client, conv, "late fee?"))
    docs = next(e for e in events if e["type"] == "doc_results")
    assert docs["passages"][0]["id"] == "D1" and docs["passages"][0]["doc_id"] == "lease-001"


def test_last_round_forces_an_answer(test_engine: Engine) -> None:
    loops = [turn(tool_use(f"t{i}", "search_documents", query="x", k=1))
             for i in range(agent_loop.MAX_TOOL_ROUNDS)]  # fmt: skip
    client = FakeClient([*loops, turn(texts=("Final answer.",))])
    conv = Conversation(ToolContext(test_engine, fake_search))
    asyncio.run(collect(client, conv, "loop forever"))
    assert "tool_choice" not in client.calls[0]
    assert client.calls[-1]["tool_choice"] == {"type": "none"}


def test_refusal_rolls_back_the_turn(test_engine: Engine) -> None:
    client = FakeClient([turn(texts=("partial",), stop="refusal")])
    conv = Conversation(ToolContext(test_engine, fake_search))
    events = asyncio.run(collect(client, conv, "something"))
    assert [e["type"] for e in events] == ["text", "refusal", "done"]
    assert conv.messages == []  # next turn starts from a valid history


def test_truncated_tool_call_is_not_executed(test_engine: Engine) -> None:
    client = FakeClient([turn(tool_use("t1", "query_kpis", sql="SELECT", purpose=""),
                              stop="max_tokens")])  # fmt: skip
    conv = Conversation(ToolContext(test_engine, fake_search))
    events = asyncio.run(collect(client, conv, "q"))
    assert [e["type"] for e in events] == ["error", "done"] and conv.messages == []


def test_sanitize_fallback_drops_pre_boundary_internal_blocks() -> None:
    blocks = [NS(type="thinking"), NS(type="text"), NS(type="tool_use"), NS(type="fallback"),
              NS(type="thinking"), NS(type="text")]  # fmt: skip
    assert [b.type for b in sanitize_fallback(blocks)] == ["text", "fallback", "thinking", "text"]
    assert sanitize_fallback(blocks[:2]) == blocks[:2]


def test_system_prompt_has_canary_and_no_placeholders() -> None:
    from datetime import date

    p = system_prompt("v1", date(2026, 10, 31))
    assert CANARY in p and "{{" not in p and "2026-10-31" in p


# ------------------------------------------------------------------ SQL safety (DB layer)
def test_database_blocks_writes_even_if_the_guard_is_bypassed(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("api.agent.sql_guard.check_sql", lambda sql: sql)  # guard disabled
    with pytest.raises(Exception, match="read-only transaction|permission denied"):
        run_readonly(test_engine, "DELETE FROM public.units")
    with pytest.raises(Exception, match="permission denied"):
        run_readonly(test_engine, "SELECT email FROM public.tenants")
    with test_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM units")).scalar() == 5  # nothing deleted


def test_guard_limits_rows() -> None:
    assert check_sql("SELECT * FROM reporting.units LIMIT 10").endswith("LIMIT 10")
    assert check_sql("SELECT * FROM reporting.units LIMIT 9999").endswith("LIMIT 201")
    with pytest.raises(SqlRejected):
        check_sql("WITH d AS (DELETE FROM reporting.units RETURNING *) SELECT * FROM d")


# ------------------------------------------------------------------ HTTP / SSE
def parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        data = [ln[5:].strip() for ln in block.splitlines() if ln.startswith("data:")]
        if data:
            events.append(json.loads("\n".join(data)))
    return events


def test_chat_endpoint_streams_events(test_engine: Engine) -> None:
    from api.db import get_engine

    fake = FakeClient([turn(texts=("Hello from the fake model.",))])
    app.dependency_overrides.update({get_engine: lambda: test_engine, get_client: lambda: fake,
                                     get_search: lambda: fake_search})  # fmt: skip
    try:
        with TestClient(app) as c:
            r = c.post("/agent/chat", json={"message": "hi"})
            events = parse_sse(r.text)
            assert r.status_code == 200 and "id" in events[0]
            assert [e.get("type") for e in events[1:]] == ["text", "done"]
            cid = events[0]["id"]
            fake.turns.append(turn(texts=("Second.",)))
            r2 = c.post("/agent/chat", json={"message": "again", "conversation_id": cid})
            assert parse_sse(r2.text)[0]["id"] == cid  # same conversation continues
            assert len(fake.calls[-1]["messages"]) == 3  # user, assistant, user
            assert c.post("/agent/chat", json={"message": ""}).status_code == 422
    finally:
        app.dependency_overrides.clear()
