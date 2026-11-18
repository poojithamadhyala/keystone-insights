"""`python -m data.seed`: migrate, regenerate and bulk-load the synthetic dataset.

Idempotent: truncates all tables and reloads from the seed, so the DB always matches
`generate(SEED)` exactly. Uses COPY (one round trip per table) instead of INSERTs.
"""

import argparse
import time

import psycopg
from alembic import command
from alembic.config import Config

from common.settings import get_settings
from data.generate import Dataset, generate


def migrate(url: str | None = None) -> None:
    cfg = Config("data/alembic.ini")
    if url:
        cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def psycopg_url(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")


def load(ds: Dataset, url: str) -> None:
    with psycopg.connect(psycopg_url(url)) as conn, conn.cursor() as cur:
        tables = ", ".join((*Dataset.TABLE_ORDER, "dataset_meta"))
        cur.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
        for table in Dataset.TABLE_ORDER:
            rows = getattr(ds, table)
            cols = list(rows[0])
            with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row([row[c] for c in cols])
            # ids were assigned by the generator; move sequences past them
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"(SELECT max(id) FROM {table}))"
            )
        cur.executemany(
            "INSERT INTO dataset_meta (key, value) VALUES (%s, %s)", list(ds.meta.items())
        )
        cur.execute("ANALYZE")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=get_settings().seed)
    args = parser.parse_args()
    url = get_settings().database_url
    t0 = time.perf_counter()
    migrate()
    ds = generate(args.seed)
    load(ds, url)
    counts = {t: len(getattr(ds, t)) for t in Dataset.TABLE_ORDER}
    print(f"seeded (seed={args.seed}) in {time.perf_counter() - t0:.1f}s: {counts}")


if __name__ == "__main__":
    main()
