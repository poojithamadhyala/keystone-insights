from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.agent.router import router as agent_router
from api.kpis.router import router as kpis_router

app = FastAPI(title="LeaseLens API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(kpis_router)
app.include_router(agent_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
