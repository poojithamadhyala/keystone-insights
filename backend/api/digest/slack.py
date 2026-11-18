"""Deliver a stored digest to a Slack incoming webhook (Block Kit, plain mrkdwn).

The digest's stored `text` is sent unchanged, so the Slack message matches the preview.
"""

from __future__ import annotations

from typing import Any

import httpx

SLACK_SECTION_LIMIT = 3000  # Block Kit text limit per section


def blocks(run: dict[str, Any]) -> dict[str, Any]:
    body, _, footer = run["text"].rpartition("\n")
    sections = [body[i : i + SLACK_SECTION_LIMIT] for i in range(0, len(body), SLACK_SECTION_LIMIT)]
    return {
        "text": body.splitlines()[0] if body else "LeaseLens weekly digest",  # notification text
        "blocks": [
            *({"type": "section", "text": {"type": "mrkdwn", "text": s}} for s in sections),
            {"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]},
        ],
    }


def send(
    webhook_url: str, run: dict[str, Any], transport: httpx.BaseTransport | None = None
) -> str:
    """Post to Slack; returns a short delivery status for the run log."""
    if not webhook_url:
        return "skipped: SLACK_WEBHOOK_URL not configured"
    try:
        with httpx.Client(timeout=10, transport=transport) as client:
            r = client.post(webhook_url, json=blocks(run))
    except httpx.HTTPError as e:
        return f"error: {type(e).__name__}"
    # Slack answers 200 "ok"; anything else carries a short error code, never the webhook URL.
    return "sent" if r.status_code == 200 else f"error: slack {r.status_code} {r.text[:80]}"
