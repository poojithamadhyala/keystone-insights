"""Digest endpoints.

GET  /digest/latest       latest stored digest (preview), or 404
POST /digest/build        build a fresh digest (stored, not sent)
POST /digest/{id}/send    send that exact stored digest to Slack ("Send now")
POST /digest/run          build + send; token-protected, called by the weekly GitHub Action
GET  /digest/runs         recent runs with delivery status
"""

from __future__ import annotations

import hmac
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import Engine

from api import safeguards
from api.db import get_engine
from api.digest import service, slack
from api.kpis.router import dataset_as_of
from common.settings import get_settings

router = APIRouter(prefix="/digest", tags=["digest"])
EngineDep = Annotated[Engine, Depends(get_engine)]


@lru_cache
def get_digest_client() -> Any:
    """Synchronous Anthropic client for the narrative (overridden in tests). Without a key the
    digest still works: build_digest falls back to the facts-only text."""
    import anthropic

    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key or "missing", max_retries=2)


def get_transport() -> Any:
    return None  # real network; tests inject httpx.MockTransport


ClientDep = Annotated[Any, Depends(get_digest_client)]
TransportDep = Annotated[Any, Depends(get_transport)]


def _deliver(engine: Engine, run: dict[str, Any], transport: Any) -> dict[str, Any]:
    status = slack.send(get_settings().slack_webhook_url, run, transport)
    service.record_delivery(engine, run["id"], status, sent=status == "sent")
    return service.get_run(engine, run["id"]) or {}


@router.get("/latest")
def latest(engine: EngineDep) -> dict[str, Any]:
    run = service.get_run(engine)
    if not run:
        raise HTTPException(404, "no digest built yet")
    return run


@router.post("/build")
def build(request: Request, engine: EngineDep, client: ClientDep) -> dict[str, Any]:
    safeguards.enforce_rate_limit(request, "digest", get_settings().digest_builds_per_hour)
    # Over the demo's daily budget: no model call; the digest falls back to the facts-only text.
    use = client if safeguards.budget_available(engine) else None
    run = service.build_digest(engine, use, dataset_as_of(engine), trigger="preview")
    safeguards.record_spend(engine, run.get("cost_usd") or 0)
    return run


@router.post("/{run_id}/send")
def send_now(run_id: int, engine: EngineDep, transport: TransportDep) -> dict[str, Any]:
    if not get_settings().digest_send_enabled:
        raise HTTPException(403, "sending is disabled on this deployment (preview only)")
    run = service.get_run(engine, run_id)
    if not run:
        raise HTTPException(404, f"digest {run_id} not found")
    return _deliver(engine, run, transport)


@router.post("/run")
def scheduled_run(
    engine: EngineDep,
    client: ClientDep,
    transport: TransportDep,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    token = get_settings().digest_run_token
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(supplied, token):  # constant-time comparison
        raise HTTPException(401, "invalid or missing token")
    run = service.build_digest(engine, client, dataset_as_of(engine), trigger="schedule")
    safeguards.record_spend(engine, run.get("cost_usd") or 0)
    return _deliver(engine, run, transport)


@router.get("/runs")
def runs(engine: EngineDep) -> list[dict[str, Any]]:
    return service.list_runs(engine)
