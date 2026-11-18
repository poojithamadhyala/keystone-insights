"""`python -m api.record_samples`: record real agent answers to the suggested questions.

They're served (labeled "Recorded answer") on the public demo when the daily AI budget is spent
or no key is configured. Re-record after changing the prompt, tools or data (costs about $0.15).
The demo database uses the same seed, so these answers match what the live agent would say.
"""

from __future__ import annotations

import asyncio
import json

import anthropic

from api.agent.loop import Conversation, run_turn
from api.agent.router import SUGGESTIONS, get_search
from api.agent.tools import ToolContext
from api.db import get_engine
from api.safeguards import SAMPLES_PATH
from common.settings import get_settings


async def record() -> None:
    client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    samples, total = {}, 0.0
    for q in SUGGESTIONS:
        conv = Conversation(ToolContext(get_engine(), get_search()))
        events = [ev async for ev in run_turn(client, conv, q)]
        ok = not any(e["type"] in ("error", "refusal") for e in events)
        total += events[-1]["cost_usd"]
        print(f"{'ok ' if ok else 'ERR'} ${events[-1]['cost_usd']:.3f}  {q}")
        if ok:
            samples[q] = events
    SAMPLES_PATH.write_text(json.dumps(samples, indent=1, default=str) + "\n")
    print(f"saved {len(samples)}/{len(SUGGESTIONS)} to {SAMPLES_PATH} (cost ${total:.3f})")


if __name__ == "__main__":
    asyncio.run(record())
