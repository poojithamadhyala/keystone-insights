from collections.abc import Mapping
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, text

from common.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)


def fetch_all(engine: Engine, sql: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql), dict(params))]
