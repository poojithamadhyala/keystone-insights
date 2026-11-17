"""Single source of configuration for every Python component (read from env / .env)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # Local Docker Postgres. A hosted database (Neon) is configured with DATABASE_URL instead.
    postgres_user: str = "leaselens"
    postgres_password: str = "leaselens"
    postgres_db: str = "leaselens"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_ro_user: str = "leaselens_ro"
    database_url_override: str = Field(default="", alias="DATABASE_URL")

    redis_url: str = "redis://localhost:6379/0"
    pinecone_api_key: str = ""
    pinecone_index: str = "leaselens-docs"
    anthropic_api_key: str = ""
    leaselens_model: str = "claude-opus-5-5"
    agent_prompt_version: str = "v1"
    slack_webhook_url: str = ""
    digest_run_token: str = ""
    digest_send_enabled: bool = True
    seed: int = 42

    # Public demo (docs/shaping/public-demo.md). Defaults are for local development.
    cors_origins: str = "http://localhost:5173"  # comma-separated; scheme optional (https assumed)
    cors_origin_regex: str = (
        ""  # e.g. Vercel preview URLs: ^https://myproject-[a-z0-9-]+\.vercel\.app$
    )
    demo_mode: bool = False  # labels the UI, enables the guards below
    daily_spend_cap_usd: float = 2.0  # Claude spend per UTC day before cached answers kick in
    agent_questions_per_hour: int = 10  # per client IP
    digest_builds_per_hour: int = 3  # per client IP (each build calls Claude)
    trust_proxy: bool = False  # True behind Render's proxy: client IP from X-Forwarded-For

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            # Neon gives postgresql://...?sslmode=require; SQLAlchemy needs the psycopg driver.
            url = self.database_url_override
            for prefix in ("postgresql://", "postgres://"):
                if url.startswith(prefix):
                    return "postgresql+psycopg://" + url[len(prefix) :]
            return url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """Browsers send Origin as scheme://host with no trailing slash, and CORS needs an exact
        match. So "keystone.vercel.app/" becomes "https://keystone.vercel.app"."""
        out = []
        for raw in self.cors_origins.split(","):
            o = raw.strip().rstrip("/")
            if o:
                out.append(o if "://" in o else f"https://{o}")
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
