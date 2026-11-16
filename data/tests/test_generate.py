"""Generator tests: determinism, referential integrity, and the realistic patterns the
rest of the project depends on (seasonality, lateness, renewal signal). No DB needed."""

from collections import Counter, defaultdict
from datetime import date

import pytest

from data.generate import AS_OF, N_UNITS, SLA_HOURS, WINDOW_START, Dataset, generate


@pytest.fixture(scope="module")
def ds() -> Dataset:
    return generate(42)


def _late(r: dict) -> bool:
    return r["paid_on"] is None or (r["paid_on"] - r["due_date"]).days > 5


def test_deterministic_for_seed(ds: Dataset) -> None:
    again = generate(42)
    for t in Dataset.TABLE_ORDER:
        assert getattr(ds, t) == getattr(again, t), t
    assert generate(7).leases != ds.leases


def test_shape(ds: Dataset) -> None:
    assert len(ds.properties) == 20
    assert len(ds.units) == N_UNITS
    assert "Maple Court" in {p["name"] for p in ds.properties}


def test_referential_integrity_and_no_overlapping_leases(ds: Dataset) -> None:
    units = {u["id"] for u in ds.units}
    tenants = {t["id"] for t in ds.tenants}
    leases = {lease["id"]: lease for lease in ds.leases}
    by_unit = defaultdict(list)
    for lease in ds.leases:
        assert lease["unit_id"] in units and lease["tenant_id"] in tenants
        by_unit[lease["unit_id"]].append(lease)
    for ls in by_unit.values():
        ls.sort(key=lambda x: x["start_date"])
        for a, b in zip(ls, ls[1:], strict=False):
            assert (a["move_out_date"] or a["end_date"]) <= b["start_date"]
    for r in ds.rent_ledger:
        lease = leases[r["lease_id"]]
        assert lease["start_date"] <= r["period"] < (lease["move_out_date"] or lease["end_date"])
        assert r["paid_on"] is None or r["paid_on"] <= AS_OF  # nothing from the future
    assert all(w["opened_at"].date() <= AS_OF for w in ds.work_orders)


def test_occupancy_and_renewal_rates_are_realistic(ds: Dataset) -> None:
    occ = sum(
        1 for x in ds.leases if x["start_date"] <= AS_OF < (x["move_out_date"] or x["end_date"])
    )
    assert 0.88 <= occ / N_UNITS <= 0.97
    renewed = {x["renewal_of_lease_id"] for x in ds.leases if x["renewal_of_lease_id"]}
    ends = [x for x in ds.leases if WINDOW_START <= x["end_date"] <= AS_OF]
    assert 0.45 <= sum(x["id"] in renewed for x in ends) / len(ends) <= 0.75


def test_hvac_seasonality(ds: Dataset) -> None:
    by_month = Counter(w["opened_at"].month for w in ds.work_orders if w["category"] == "hvac")
    assert by_month[7] > 2 * by_month[4]  # summer peak
    assert by_month[1] > by_month[4]  # winter bump


def test_maple_court_heatwave_spike(ds: Dataset) -> None:
    july = sum(
        1
        for w in ds.work_orders
        if w["property_id"] == 1 and w["category"] == "hvac" and w["opened_at"].date().replace(
            day=1) == date(2026, 7, 1)
    )  # fmt: skip
    assert july >= 25


def test_january_lateness_exceeds_june(ds: Dataset) -> None:
    def rate(month: int) -> float:
        rows = [r for r in ds.rent_ledger if r["period"].month == month]
        return sum(map(_late, rows)) / len(rows)

    assert rate(1) > rate(6) + 0.03


def test_sla_breach_rate_is_nontrivial(ds: Dataset) -> None:
    done = [w for w in ds.work_orders if w["completed_at"]]
    breach = sum(
        (w["completed_at"] - w["opened_at"]).total_seconds() / 3600 > SLA_HOURS[w["priority"]]
        for w in done
    )
    assert 0.08 <= breach / len(done) <= 0.30


def test_late_payers_renew_less(ds: Dataset) -> None:
    """The renewal signal milestone 4's model must learn: lateness -> lower renewal."""
    renewed = {x["renewal_of_lease_id"] for x in ds.leases if x["renewal_of_lease_id"]}
    late_by_lease: dict[int, list[bool]] = defaultdict(list)
    for r in ds.rent_ledger:
        late_by_lease[r["lease_id"]].append(_late(r))
    ends = [
        x for x in ds.leases if WINDOW_START <= x["end_date"] <= AS_OF and late_by_lease[x["id"]]
    ]
    punctual = [x for x in ends if not any(late_by_lease[x["id"]])]
    late = [x for x in ends if sum(late_by_lease[x["id"]]) >= 2]

    def rate(xs: list) -> float:
        return sum(x["id"] in renewed for x in xs) / len(xs)

    assert rate(punctual) > rate(late) + 0.15
