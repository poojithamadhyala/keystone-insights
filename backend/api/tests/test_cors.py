"""CORS configuration as used on the public demo (no DB needed)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from common.settings import Settings


def test_origins_are_normalised() -> None:
    s = Settings(cors_origins=" keystone-insights-nu.vercel.app/ , http://localhost:5173 ")
    assert s.cors_origin_list == [
        "https://keystone-insights-nu.vercel.app",
        "http://localhost:5173",
    ]


def _app(s: Settings) -> TestClient:
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list,
                       allow_origin_regex=s.cors_origin_regex or None,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])  # fmt: skip

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def allowed(c: TestClient, origin: str) -> bool:
    r = c.options("/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    return r.headers.get("access-control-allow-origin") == origin


def test_production_and_preview_urls_allowed_others_not() -> None:
    preview = r"^https://keystone-insights-[a-z0-9-]+\.vercel\.app$"  # same as render.yaml
    s = Settings(cors_origins="keystone-insights-nu.vercel.app", cors_origin_regex=preview)
    c = _app(s)
    assert allowed(c, "https://keystone-insights-nu.vercel.app")
    assert allowed(c, "https://keystone-insights-git-fix-deploy-config-pooja.vercel.app")
    assert not allowed(c, "https://evil.vercel.app")
    assert not allowed(c, "https://keystone-insights-nu.vercel.app.evil.com")
    assert not allowed(c, "http://keystone-insights-nu.vercel.app")  # wrong scheme
