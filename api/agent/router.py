"""POST /agent/chat: one user message in, a stream of server-sent events out.

Events: conversation, text, tool_start, sql_result, doc_results, report, refusal, error, done.
Conversations live in memory (an LRU of 200, two-hour TTL). That's fine for a single-instance
demo; a restart starts a new chat (see README limitations).
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sse_starlette.sse import EventSourceResponse

from api.agent.loop import Conversation, run_turn
from api.agent.tools import ToolContext
from api.db import get_engine
from common.settings import get_settings

router = APIRouter(prefix="/agent", tags=["agent"])

SUGGESTIONS = [
    "Which properties have the most rent outstanding from current residents?",
    "Show occupancy by property as a bar chart.",
    "What is the late fee and grace period in the Maple Court leases?",
    "Which vendors handled HVAC tickets that breached SLA at Maple Court in July 2026?",
    "What does the SOP say to do about frozen pipes?",
]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None


class _Store:
    def __init__(self, max_items: int = 200, ttl_s: int = 7200) -> None:
        self.items: OrderedDict[str, tuple[float, Conversation]] = OrderedDict()
        self.max_items, self.ttl_s = max_items, ttl_s

    def get(self, cid: str | None) -> Conversation | None:
        if cid and cid in self.items:
            ts, conv = self.items[cid]
            if time.time() - ts < self.ttl_s:
                self.items.move_to_end(cid)
                return conv
            del self.items[cid]
        return None

    def put(self, conv: Conversation) -> None:
        self.items[conv.id] = (time.time(), conv)
        self.items.move_to_end(conv.id)
        while len(self.items) > self.max_items:
            self.items.popitem(last=False)


STORE = _Store()


@lru_cache
def get_client() -> Any:
    import anthropic

    key = get_settings().anthropic_api_key
    if not key:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not configured on the server")
    return anthropic.AsyncAnthropic(api_key=key, max_retries=2)


def get_search() -> Any:
    """Document search for the agent (improved retrieval). Overridden in tests."""
    from rag.retrieve import IMPROVED, retrieve

    def search(query: str, k: int) -> list[dict[str, Any]]:
        return [
            {"doc_id": h.doc_id, "title": h.metadata["title"], "section": h.metadata["section"],
             "text": h.metadata["text"], "score": round(h.score, 3)}
            for h in retrieve(query, IMPROVED, k=k)
        ]  # fmt: skip

    return search


@router.get("/suggestions")
def suggestions() -> list[str]:
    return SUGGESTIONS


@router.post("/chat")
async def chat(
    body: ChatIn,
    engine: Annotated[Engine, Depends(get_engine)],
    client: Annotated[Any, Depends(get_client)],
    search: Annotated[Any, Depends(get_search)],
) -> EventSourceResponse:
    conv = STORE.get(body.conversation_id) or Conversation(ToolContext(engine, search))
    STORE.put(conv)

    async def events() -> AsyncIterator[dict[str, str]]:
        yield {"event": "conversation", "data": json.dumps({"id": conv.id})}
        try:
            async for ev in run_turn(client, conv, body.message):
                yield {"event": ev["type"], "data": json.dumps(ev, default=str)}
        except Exception as e:  # surface API/DB failures to the UI instead of a dead stream
            yield {"event": "error", "data": json.dumps({"type": "error", "message": str(e)})}

    return EventSourceResponse(events())
