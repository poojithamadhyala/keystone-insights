"""KPI correctness against the hand-built fixture in conftest.py (as-of 2026-03-31).
Expected values are derived by hand in the comments, not by re-running the SQL."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db
P1 = "property_id=1"


def test_meta_defaults_to_dataset_as_of(client: TestClient) -> None:
    assert client.get("/kpis/meta").json()["as_of"] == "2026-03-31"


def test_occupancy_snapshot_and_filter(client: TestClient) -> None:
    body = client.get(f"/kpis/occupancy?{P1}").json()
    # u1 (L1 last day = as-of) and u2 occupied; u3 moved out Jan 1; u4 terminated Mar 1
    assert body["by_property"] == [
        {"property_id": 1, "property": "Test Place", "units": 4, "occupied": 2, "occupancy": 0.5}
    ]
    trend = {p["month"]: p["occupancy"] for p in body["trend"]}
    assert trend["2026-02-01"] == 0.75  # u1, u2, u4
    assert trend["2026-03-01"] == 0.5  # u4 move_out 2026-03-01 is exclusive


def test_occupancy_whole_portfolio(client: TestClient) -> None:
    rows = client.get("/kpis/occupancy").json()["by_property"]
    assert {r["property"]: r["occupied"] for r in rows} == {"Other Place": 1, "Test Place": 2}


def test_delinquency_aging_by_charge_month(client: TestClient) -> None:
    rows = client.get(f"/kpis/delinquency?{P1}").json()
    got = {(r["bucket"], r["current_resident"]): (r["amount"], r["tenants"]) for r in rows}
    assert got == {
        # Mar: t2 2000 (paid Apr 10, after as-of) + t1 500 (partial)
        ("0-30", True): (2500.0, 2),
        ("31-60", True): (2000.0, 1),  # Feb: t2 unpaid
        ("90+", False): (1200.0, 1),  # Dec: t4, terminated -> former resident
    }


def test_delinquency_is_point_in_time(client: TestClient) -> None:
    # as of Apr 15 the Mar charge for t2 has been paid (Apr 10)
    rows = client.get(f"/kpis/delinquency?{P1}&as_of=2026-04-15").json()
    got = {(r["bucket"], r["current_resident"]): r["amount"] for r in rows}
    # t1's lease ended Mar 31, so on Apr 15 their March remainder is a *former* resident's
    assert got == {
        ("31-60", False): 500.0,
        ("61-90", True): 2000.0,  # t2's February; t2's March was paid Apr 10
        ("90+", False): 1200.0,  # t4's December, now 4 charge-months past
    }


def test_lease_expirations_use_last_day(client: TestClient) -> None:
    rows = client.get("/kpis/lease-expirations?months=3").json()
    got = {(r["property"], r["month"]): r["leases"] for r in rows}
    # L1 end_date 2026-04-01 -> last day 2026-03-31 -> March; L5 end 2026-06-01 -> May;
    # L2 (Sep 30) is outside the 3-month horizon
    assert got == {("Test Place", "2026-03-01"): 1, ("Other Place", "2026-05-01"): 1}


def test_noi_cash_basis(client: TestClient) -> None:
    rows = client.get(f"/kpis/noi?{P1}&start=2026-01-01&end=2026-03-01").json()
    by_month = {r["month"]: r for r in rows}
    assert by_month["2026-01-01"]["noi"] == 2000 - 300  # t2's Jan payment - payroll
    mar = by_month["2026-03-01"]
    # revenue: t1 partial 500 (t2's Mar payment lands Apr 10, after as-of)
    # maintenance: WO1 250 + WO2 100 completed in March
    assert (mar["revenue"], mar["operating_expenses"], mar["maintenance"]) == (500, 100, 350)
    assert mar["noi"] == 50


def test_work_order_sla(client: TestClient) -> None:
    rows = client.get(f"/kpis/work-order-sla?{P1}&start=2026-03-01&end=2026-03-01").json()
    got = {r["grp"]: (r["tickets"], r["judged"], r["met"], r["sla_rate"]) for r in rows}
    assert got == {
        "emergency": (1, 1, 1, 1.0),  # 12h <= 24h
        "high": (1, 1, 0, 0.0),  # 96h > 72h
        "low": (1, 0, 0, None),  # open 38h, still inside 336h window -> not judged
        "normal": (1, 1, 0, 0.0),  # open 30 days > 168h -> breach; cancelled WO excluded
    }


def test_rent_roll_balances(client: TestClient) -> None:
    body = client.get(f"/kpis/rent-roll?{P1}").json()
    assert body["total"] == 4
    bal = {r["unit_number"]: (r["tenant"], r["balance"]) for r in body["rows"]}
    assert bal == {
        "101": ("T1 Test", 500.0),
        "102": ("T2 Test", 4000.0),
        "103": (None, 0.0),
        "104": (None, 0.0),
    }


def test_sla_group_by_rejects_unknown_column(client: TestClient) -> None:
    assert client.get("/kpis/work-order-sla?group_by=1;drop table x").status_code == 422


def test_readonly_role_sees_only_pii_free_views(test_engine: Engine) -> None:
    with test_engine.connect() as conn:
        conn.execute(text("SET ROLE leaselens_ro"))
        cols = conn.execute(text("SELECT * FROM reporting.tenants LIMIT 1")).keys()
        assert list(cols) == ["id", "tenant_label", "credit_score"]
        with pytest.raises(Exception, match="permission denied"):
            conn.execute(text("SELECT email FROM public.tenants"))
        conn.rollback()
