from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.agent.router import router as agent_router
from api.digest.router import router as digest_router
from api.kpis.router import router as kpis_router
from common.settings import get_settings

app = FastAPI(title="LeaseLens API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,  # the Vercel URL on the public demo
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(kpis_router)
app.include_router(agent_router)
app.include_router(digest_router)


@app.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {"status": "ok", "demo_mode": s.demo_mode, "send_enabled": s.digest_send_enabled}
