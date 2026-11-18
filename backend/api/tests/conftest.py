"""DB fixtures: a throwaway `<db>_test` database migrated to head and loaded with a tiny
hand-built portfolio whose KPI values are computed by hand in test_kpis.py."""

from collections.abc import Iterator
from datetime import date, datetime

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine

from api.db import get_engine
from api.main import app
from common.settings import get_settings
from data.generate import Dataset
from data.seed import load, migrate, psycopg_url

AS_OF = date(2026, 3, 31)


def _lease(id_, unit, tenant, start, end, rent, status="active", move_out=None):  # type: ignore[no-untyped-def]
    return {
        "id": id_, "unit_id": unit, "tenant_id": tenant, "start_date": start, "end_date": end,
        "move_out_date": move_out, "monthly_rent": rent, "security_deposit": rent,
        "status": status, "renewal_of_lease_id": None,
    }  # fmt: skip


def _ledger(id_, lease, period, due, paid=0.0, paid_on=None):  # type: ignore[no-untyped-def]
    return {
        "id": id_, "lease_id": lease, "period": period, "due_date": period,
        "amount_due": due, "amount_paid": paid, "paid_on": paid_on,
    }  # fmt: skip


def _wo(id_, unit, prio, opened, completed, status, cost, cat="hvac", prop=1):  # type: ignore[no-untyped-def]
    return {
        "id": id_, "property_id": prop, "unit_id": unit, "vendor_id": 1, "category": cat,
        "priority": prio, "status": status, "opened_at": opened, "completed_at": completed,
        "cost": cost, "description": "test",
    }  # fmt: skip


def fixture_dataset() -> Dataset:
    d = date
    ds = Dataset(meta={"seed": "0", "as_of": AS_OF.isoformat()})
    ds.properties = [
        {"id": 1, "name": "Test Place", "city": "A", "state": "TX", "property_type": "garden",
         "year_built": 2000, "acquired_on": d(2015, 1, 1)},
        {"id": 2, "name": "Other Place", "city": "B", "state": "TX", "property_type": "garden",
         "year_built": 2000, "acquired_on": d(2015, 1, 1)},
    ]  # fmt: skip
    ds.units = [
        {"id": i, "property_id": 1 if i <= 4 else 2, "unit_number": str(100 + i),
         "unit_type": "1br", "bedrooms": 1, "bathrooms": 1.0, "sqft": 700, "market_rent": 1000}
        for i in range(1, 6)
    ]  # fmt: skip
    ds.tenants = [
        {"id": i, "first_name": f"T{i}", "last_name": "Test", "email": "x@example.com",
         "phone": "0", "credit_score": 700}
        for i in range(1, 6)
    ]  # fmt: skip
    ds.vendors = [{"id": 1, "name": "V", "trade": "hvac", "phone": "0", "hourly_rate": 100}]
    ds.leases = [
        _lease(1, 1, 1, d(2025, 4, 1), d(2026, 4, 1), 1000),  # last day 2026-03-31
        _lease(2, 2, 2, d(2025, 10, 1), d(2026, 10, 1), 2000),
        _lease(3, 3, 3, d(2025, 1, 1), d(2026, 1, 1), 1100, "expired", d(2026, 1, 1)),
        _lease(4, 4, 4, d(2025, 6, 1), d(2026, 6, 1), 1200, "terminated", d(2026, 3, 1)),
        _lease(5, 5, 5, d(2025, 6, 1), d(2026, 6, 1), 1500),  # property 2
    ]
    ds.rent_ledger = [
        _ledger(1, 2, d(2026, 1, 1), 2000, 2000, d(2026, 1, 3)),
        _ledger(2, 2, d(2026, 2, 1), 2000),  # unpaid
        _ledger(3, 2, d(2026, 3, 1), 2000, 2000, d(2026, 4, 10)),  # paid AFTER as-of
        _ledger(4, 1, d(2026, 3, 1), 1000, 500, d(2026, 3, 5)),  # partial
        _ledger(5, 4, d(2025, 12, 1), 1200),  # former resident, unpaid
    ]
    t = datetime
    ds.work_orders = [
        _wo(1, 1, "emergency", t(2026, 3, 10, 8), t(2026, 3, 10, 20), "completed", 250),
        _wo(2, 2, "high", t(2026, 3, 1, 8), t(2026, 3, 5, 8), "completed", 100, "plumbing"),
        _wo(3, 1, "low", t(2026, 3, 30, 10), None, "open", None, "general"),
        _wo(4, 2, "normal", t(2026, 3, 1, 9), None, "open", None, "general"),
        _wo(5, 2, "normal", t(2026, 3, 2, 9), None, "cancelled", None, "general"),
    ]  # fmt: skip
    ds.operating_expenses = [
        {"id": 1, "property_id": 1, "period": d(2026, 1, 1), "category": "payroll", "amount": 300},
        {"id": 2, "property_id": 1, "period": d(2026, 3, 1), "category": "payroll", "amount": 100},
    ]
    return ds


@pytest.fixture(scope="session")
def test_db_url() -> Iterator[str]:
    s = get_settings()
    admin = psycopg_url(s.database_url)
    name = f"{s.postgres_db}_test"
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
            conn.execute(f"CREATE DATABASE {name}")
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable (run `make up`)")
    url = s.database_url.rsplit("/", 1)[0] + f"/{name}"
    migrate(url)
    load(fixture_dataset(), url)
    yield url


@pytest.fixture(scope="session")
def test_engine(test_db_url: str) -> Iterator[Engine]:
    engine = create_engine(test_db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def client(test_engine: Engine) -> Iterator[TestClient]:
    app.dependency_overrides[get_engine] = lambda: test_engine
    yield TestClient(app)
    app.dependency_overrides.clear()
