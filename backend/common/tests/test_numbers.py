import pytest

from common.numbers import extract, matches, numeric_values, ungrounded


def values(text: str) -> list[float]:
    return [m.value for m in extract(text)]


def test_extracts_money_percent_scales_and_commas() -> None:
    assert values("Delinquent $104.7K, NOI $46.6M, 2,832 units, 94.4% occupied") == [
        pytest.approx(104_700),
        pytest.approx(46_600_000),
        2832,
        94.4,
    ]


def test_ignores_dates_times_years_buckets_and_citations() -> None:
    text = "As of 2026-10-31 (Oct 31, 2026), quiet hours start 11:00; the 0-30 and 90+ buckets [S1]"
    assert values(text) == []


def test_precision_allows_rounding_or_truncation_only() -> None:
    (m,) = extract("$1.2K")
    assert matches(m, [1150.0]) and matches(m, [1299.0])  # rounded / truncated
    assert not matches(m, [1149.0]) and not matches(m, [1300.0])
    (d,) = extract("$1,845")
    assert matches(d, [1845.67]) and matches(d, [1844.5]) and not matches(d, [1846.0])
    (p,) = extract("94.4%")
    assert matches(p, [0.9441]) and matches(p, [94.43]) and not matches(p, [0.946])


def test_numeric_values_walks_nested_data() -> None:
    data = {"rows": [[1, "Maple Court", 1200.5], [2, "x", None]], "note": "late fee $106.02"}
    assert sorted(numeric_values(data)) == [1, 2, 106.02, 1200.5]


def test_ungrounded_flags_only_unsupported_numbers() -> None:
    sources = [93, 0.957, 3322.53]
    text = "Maple Court has 93 units at 95.7% occupancy, owing $3,322.53, up 14% from last week."
    assert [m.raw for m in ungrounded(text, sources)] == ["14%"]
    assert ungrounded("Two properties and the top 5 tenants", []) == []


def test_percent_mentions_can_be_restricted_to_percent_sources() -> None:
    facts = {"change_pct": -17.05, "days_open": 18}
    assert [m.raw for m in ungrounded("up 18%", numeric_values(facts))] == []  # loose: 18 days
    pct = numeric_values(facts, key=lambda k: k.endswith("_pct"))
    assert pct == [-17.05]
    assert [m.raw for m in ungrounded("up 18%", numeric_values(facts), pct)] == ["18%"]
