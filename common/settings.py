"""Single source of configuration for every Python component (read from env / .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "leaselens"
    postgres_password: str = "leaselens"
    postgres_db: str = "leaselens"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_ro_user: str = "leaselens_ro"
    postgres_ro_password: str = "leaselens_ro"

    redis_url: str = "redis://localhost:6379/0"
    pinecone_api_key: str = ""
    pinecone_index: str = "leaselens-docs"
    anthropic_api_key: str = ""
    leaselens_model: str = "claude-opus-5-5"
    agent_prompt_version: str = "v1"
    seed: int = 42

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def readonly_database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_ro_user}:{self.postgres_ro_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
