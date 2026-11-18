"""Guard + executor for model-written SQL (the agent's `query_kpis` tool).

Defense in depth; each layer would stop a bad query on its own:
  1. Parse (sqlglot, Postgres dialect): exactly one statement, and it must be a read query.
  2. Walk the tree: no write/DDL nodes, no SELECT INTO, no row locks; every table is an
     allowlisted `reporting` view (or a CTE defined in the query); dangerous functions denied.
  3. Rewrite LIMIT so at most MAX_ROWS (+1, to detect truncation) rows come back.
  4. Execute inside a READ ONLY transaction after `SET LOCAL ROLE leaselens_ro`, with a 5 s
     statement timeout and search_path = reporting. The role can only see PII-free views
     (migration 0002), and dropping to it inside the transaction holds even if the API ever
     connects as a more privileged user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import sqlglot
from sqlalchemy import Engine, text
from sqlglot import exp

from common.settings import get_settings

ALLOWED_VIEWS = frozenset(
    {"properties", "units", "tenants", "leases", "rent_ledger", "vendors", "work_orders",
     "operating_expenses"}
)  # fmt: skip
MAX_ROWS = 200
STATEMENT_TIMEOUT = "5s"

# Functions that read files, run arbitrary SQL strings, sleep, or change settings.
DENIED_FUNCTION = re.compile(
    r"^(pg_|lo_|dblink|set_config|current_setting|query_to_xml|table_to_xml|cursor_to_xml|"
    r"database_to_xml|schema_to_xml|query_to_json|txid_|version$)",
    re.I,
)
FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
    exp.Command, exp.Into, exp.Lock, exp.Grant, exp.Copy, exp.Set, exp.TruncateTable,
)  # fmt: skip


class SqlRejected(ValueError):
    """The query was refused by the guard; the message is safe to show to the model."""


def check_sql(sql: str) -> str:
    """Validate model-written SQL and return the version to execute (with a row limit)."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise SqlRejected(f"could not parse SQL: {str(e).splitlines()[0]}") from e
    if len(statements) != 1:
        raise SqlRejected("exactly one SQL statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise SqlRejected("only SELECT queries are allowed")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlRejected(f"{node.key.upper()} is not allowed; queries are read-only")
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name, schema = table.name.lower(), (table.db or "").lower()
        if not schema and name in cte_names:
            continue
        if table.catalog or schema not in ("", "reporting") or name not in ALLOWED_VIEWS:
            allowed = ", ".join(sorted(f"reporting.{v}" for v in ALLOWED_VIEWS))
            raise SqlRejected(f"table {table.sql()} is not allowed; use only: {allowed}")
    for func in tree.find_all(exp.Func):
        fname = func.sql_name() if not isinstance(func, exp.Anonymous) else func.name
        if DENIED_FUNCTION.match(fname or ""):
            raise SqlRejected(f"function {fname} is not allowed")
    limit = tree.args.get("limit")
    current = _limit_value(limit)
    if current is None or current > MAX_ROWS:
        tree = tree.limit(MAX_ROWS + 1)
    return tree.sql(dialect="postgres")


def _limit_value(limit: exp.Expression | None) -> int | None:
    if limit is None:
        return None
    lit = limit.expression if isinstance(limit, exp.Limit) else limit
    try:
        return int(lit.name) if isinstance(lit, exp.Literal) else None
    except ValueError:
        return None


@dataclass
class QueryResult:
    sql: str  # as executed
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime | date):
        return v.isoformat()
    return v


def run_readonly(engine: Engine, sql: str) -> QueryResult:
    """Guard, then execute as the read-only role. Raises SqlRejected or the DB error."""
    safe_sql = check_sql(sql)
    ro = get_settings().postgres_ro_user
    with engine.connect() as conn, conn.begin():
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text(f"SET LOCAL ROLE {ro}"))
        conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        conn.execute(text("SET LOCAL search_path = reporting"))
        res = conn.execute(text(safe_sql))
        columns = list(res.keys())
        rows = [[_jsonable(v) for v in r] for r in res.fetchmany(MAX_ROWS + 1)]
        conn.rollback()  # nothing to commit; read-only either way
    return QueryResult(safe_sql, columns, rows[:MAX_ROWS], truncated=len(rows) > MAX_ROWS)
