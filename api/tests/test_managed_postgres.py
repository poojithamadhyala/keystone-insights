"""Regression test for hosting on managed Postgres (Neon): the app's user is NOT a superuser.

Before migration 0004 the agent's `SET LOCAL ROLE <read-only role>` failed there with "permission
denied to set role" (Postgres 16+). This builds that situation locally: a CREATEROLE-only owner
runs every migration, then the agent's SQL executor runs through that owner's connection.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest
from sqlalchemy import create_engine, text

from api.agent.sql_guard import run_readonly
from common.settings import get_settings
from data.seed import load, migrate, psycopg_url

pytestmark = pytest.mark.db

OWNER, RO, DB = "sim_owner", "sim_ro", "leaselens_managed_sim"


@pytest.fixture(scope="module")
def managed_url(test_db_url: str) -> Iterator[str]:
    admin = psycopg_url(get_settings().database_url)
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
        for role in (RO, OWNER):
            c.execute(f"DROP ROLE IF EXISTS {role}")
        c.execute(f"CREATE ROLE {OWNER} LOGIN PASSWORD 'sim' CREATEROLE NOSUPERUSER")
        c.execute(f"CREATE DATABASE {DB} OWNER {OWNER}")
    s = get_settings()
    yield f"postgresql+psycopg://{OWNER}:sim@{s.postgres_host}:{s.postgres_port}/{DB}"
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {DB} WITH (FORCE)")
        for role in (RO, OWNER):
            c.execute(f"DROP ROLE IF EXISTS {role}")


def test_agent_queries_work_when_migrated_by_a_non_superuser(
    managed_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.tests.conftest import fixture_dataset

    monkeypatch.setattr(get_settings(), "postgres_ro_user", RO)  # role must not pre-exist
    migrate(managed_url)
    load(fixture_dataset(), managed_url)
    engine = create_engine(managed_url)
    try:
        with engine.connect() as c:
            assert c.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
                             ).scalar() is False  # fmt: skip
        res = run_readonly(engine, "SELECT count(*) FROM reporting.units")
        assert res.rows == [[5]]
        # The role is still view-only at the database level (SQL guard bypassed to prove it).
        monkeypatch.setattr("api.agent.sql_guard.check_sql", lambda sql: sql)
        with pytest.raises(Exception, match="permission denied"):
            run_readonly(engine, "SELECT email FROM public.tenants")
    finally:
        engine.dispose()
