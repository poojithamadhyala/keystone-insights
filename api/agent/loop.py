"""Agent loop: Claude + tool use, streamed to the browser as events.

Manual loop (not the SDK tool runner) because each step must also be surfaced to the UI:
text deltas, the SQL that ran and its rows, document citations and charts.

Per turn:
  stream a response -> store the FULL assistant content (thinking blocks included; history is
  append-only so Claude's thinking stays valid across turns) -> stop on refusal / no tool calls
  / truncated tool input -> run tools (inputs validated) -> append tool results -> repeat.
The last allowed round sets tool_choice "none", so Claude has to answer instead of looping.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.agent.tools import TOOLS, ToolContext, execute
from common.settings import get_settings

PROMPTS = Path("prompts/agent")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOOL_ROUNDS = 6
MAX_TOKENS = 4000
CANARY = "LL-CANARY-7f3a91"  # appears only in the system prompt; must never appear in output

# $ per million tokens for claude-opus-5-5 (Anthropic list price). Cache writes billed at
# 1.25x input (5-minute cache), cache reads at $0.20.
PRICES = {"input": 4.0, "output": 20.0, "cache_write": 5.0, "cache_read": 0.20}


@lru_cache
def system_prompt(version: str, as_of: date) -> str:
    template = (PROMPTS / f"system_{version}.md").read_text()
    return template.replace("{{AS_OF}}", as_of.isoformat()).replace("{{CANARY}}", CANARY)


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_read: int = 0

    def add(self, u: Any) -> None:
        self.input += getattr(u, "input_tokens", 0) or 0
        self.output += getattr(u, "output_tokens", 0) or 0
        self.cache_write += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.cache_read += getattr(u, "cache_read_input_tokens", 0) or 0

    @property
    def cost_usd(self) -> float:
        return sum(getattr(self, k) * p for k, p in PRICES.items()) / 1e6


@dataclass
class Conversation:
    ctx: ToolContext
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list[dict[str, Any]] = field(default_factory=list)


def sanitize_fallback(content: list[Any]) -> list[Any]:
    """After a mid-stream server-side fallback, the API rejects thinking/redacted_thinking/
    tool_use blocks that appear BEFORE the last `fallback` block when the turn is echoed back.
    Drop exactly those; keep the fallback block in place and everything after it."""
    idx = [i for i, b in enumerate(content) if getattr(b, "type", None) == "fallback"]
    if not idx:
        return content
    cut = idx[-1]
    drop = {"thinking", "redacted_thinking", "tool_use", "server_tool_use"}
    return [b for i, b in enumerate(content) if i >= cut or getattr(b, "type", None) not in drop]


async def run_turn(client: Any, conv: Conversation, user_text: str) -> AsyncIterator[dict]:
    """Yield UI events for one user message. The client is an AsyncAnthropic (or a test fake)."""
    s = get_settings()
    from api.kpis.router import dataset_as_of  # avoid an import cycle at module load

    as_of = dataset_as_of(conv.ctx.engine)
    system = system_prompt(s.agent_prompt_version, as_of)
    usage = Usage()
    turn_start = len(conv.messages)
    conv.messages.append({"role": "user", "content": user_text})
    aborted = False

    for round_no in range(MAX_TOOL_ROUNDS + 1):
        final_round = round_no == MAX_TOOL_ROUNDS
        kwargs: dict[str, Any] = {
            "model": s.leaselens_model,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "tools": TOOLS,
            "messages": conv.messages,
            "output_config": {"effort": "medium"},
            "cache_control": {"type": "ephemeral"},  # caches tools + system + history prefix
            "betas": [FALLBACK_BETA],
            "fallbacks": "default",
        }
        if final_round:
            kwargs["tool_choice"] = {"type": "none"}
        try:
            async with client.beta.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield {"type": "text", "delta": event.text}
                msg = await stream.get_final_message()
        except ValueError:
            # Tool-input JSON the SDK couldn't parse (eager streaming). No tool_use id exists to
            # answer, so the turn is abandoned rather than retried blindly.
            yield {"type": "error", "message": "The model produced an unreadable tool call."}
            aborted = True
            break
        usage.add(msg.usage)
        conv.messages.append({"role": "assistant", "content": sanitize_fallback(list(msg.content))})

        if msg.stop_reason == "refusal":
            yield {"type": "refusal", "message": "This request was declined by a safety check."}
            aborted = True
            break
        tool_uses = [b for b in msg.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            break
        if msg.stop_reason == "max_tokens":  # a truncated tool input parses as a partial object
            yield {"type": "error", "message": "Response was cut off before a tool call finished."}
            aborted = True
            break

        results = []
        for tu in tool_uses:
            yield {"type": "tool_start", "name": tu.name, "input": tu.input}
            outcome = await asyncio.to_thread(execute, conv.ctx, tu.name, tu.input)
            for ev in outcome.events:
                yield ev
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": outcome.content, "is_error": outcome.is_error})  # fmt: skip
        conv.messages.append({"role": "user", "content": results})

    if aborted:
        # Roll back the whole turn: a dangling tool_use (or a declined partial) would make the
        # next request invalid. Result ids already issued stay valid in the tool context.
        del conv.messages[turn_start:]
    yield {"type": "done", "prompt_version": s.agent_prompt_version, "model": s.leaselens_model,
           "usage": usage.__dict__, "cost_usd": round(usage.cost_usd, 4)}  # fmt: skip
