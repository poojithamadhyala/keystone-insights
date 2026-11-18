"""Seeded synthetic portfolio generator.

Pure function: `generate(seed) -> Dataset` (rows as dicts, explicit ids). No DB access, so it
is unit-testable and byte-for-byte reproducible for a given seed.

Simulation order per unit (chronological, so causes precede effects):
  1. maintenance work orders for the whole window (seasonal rates + property spikes)
  2. tenancy: leases, monthly rent ledger, late/missed payments, evictions
  3. renewal decisions driven by *observable* signals (lateness, SLA breaches on the unit,
     tenure, offer vs. market rent) plus a latent tenant trait that is never stored.
     Milestone 4's renewal model must recover this signal from the observable data.
  4. turnover (make-ready) work orders at each move-out
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

import numpy as np
from faker import Faker

AS_OF = date(2026, 10, 31)
WINDOW_START = date(2024, 11, 1)
N_MONTHS = 24
N_PROPERTIES = 20
N_UNITS = 3000
MARKET_GROWTH = 0.035  # annual market-rent growth

Row = dict[str, Any]


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def month_index(d: date) -> int:
    """Months since WINDOW_START (negative before the window)."""
    return (d.year - WINDOW_START.year) * 12 + d.month - WINDOW_START.month


PERIODS = [add_months(WINDOW_START, i) for i in range(N_MONTHS)]
WINDOW_END = add_months(WINDOW_START, N_MONTHS)  # exclusive

# type: (share, bedrooms, bathrooms, mean sqft, base monthly rent at AS_OF)
UNIT_TYPES: dict[str, tuple[float, int, float, int, int]] = {
    "studio": (0.15, 0, 1.0, 480, 1250),
    "1br": (0.40, 1, 1.0, 720, 1550),
    "2br": (0.35, 2, 2.0, 1050, 1950),
    "3br": (0.10, 3, 2.0, 1350, 2450),
}

SLA_HOURS = {"emergency": 24, "high": 72, "normal": 168, "low": 336}
PRIORITIES = ["emergency", "high", "normal", "low"]

# category: (monthly rate per unit, {month: seasonal multiplier}, vendor trade)
WO_CATEGORIES: dict[str, tuple[float, dict[int, float], str]] = {
    "hvac": (0.020, {6: 2.6, 7: 3.0, 8: 2.6, 12: 1.6, 1: 1.9, 2: 1.6}, "hvac"),
    "plumbing": (0.026, {1: 1.6, 2: 1.4}, "plumbing"),
    "electrical": (0.010, {}, "electrical"),
    "appliance": (0.020, {}, "appliance"),
    "general": (0.022, {}, "general"),
    "pest": (0.007, {6: 1.8, 7: 2.0, 8: 2.0, 9: 1.5}, "pest"),
}

DESCRIPTIONS: dict[str, list[str]] = {
    "hvac": [
        "AC not cooling, thermostat reads {n}F",
        "No heat in unit, resident reports {n}F inside",
        "HVAC unit making loud rattling noise",
        "Condensate line clogged, water near air handler",
        "Thermostat unresponsive",
    ],
    "plumbing": [
        "Kitchen sink clogged",
        "Toilet running constantly",
        "Leak under bathroom vanity",
        "Low water pressure in shower",
        "Water heater not producing hot water",
    ],
    "electrical": [
        "Breaker trips when microwave runs",
        "Outlet in bedroom not working",
        "Flickering lights in living room",
    ],
    "appliance": [
        "Refrigerator not cooling",
        "Dishwasher not draining",
        "Oven igniter failing",
        "Washer leaking during spin cycle",
    ],
    "general": [
        "Closet door off track",
        "Window screen torn",
        "Drywall damage in hallway",
        "Front door lock sticking",
    ],
    "pest": ["Ants in kitchen", "Roaches reported in bathroom", "Mice droppings in pantry"],
    "turnover": ["Make-ready: paint, clean, inspect after move-out"],
}

TREES = [
    "Maple", "Cedar", "Willow", "Birch", "Aspen", "Juniper", "Harbor", "Summit", "Riverside",
    "Lakeview", "Oak", "Pine", "Elm", "Magnolia", "Sycamore", "Hawthorne", "Briar", "Linden",
    "Alder", "Cypress",
]  # fmt: skip
SUFFIXES = ["Commons", "Flats", "Gardens", "Terrace", "Place", "Lofts", "Heights", "Station"]
TRADE_WORDS = {
    "hvac": ["Heating & Air", "Climate Services", "HVAC"],
    "plumbing": ["Plumbing", "Pipe & Drain", "Plumbing Co"],
    "electrical": ["Electric", "Electrical Services"],
    "appliance": ["Appliance Repair", "Appliance Service"],
    "general": ["Property Services", "Handyman", "Maintenance"],
    "pest": ["Pest Control", "Exterminating"],
}
VENDOR_COUNTS = {"hvac": 8, "plumbing": 8, "electrical": 6, "appliance": 6, "general": 8, "pest": 4}


@dataclass
class Dataset:
    properties: list[Row] = field(default_factory=list)
    units: list[Row] = field(default_factory=list)
    tenants: list[Row] = field(default_factory=list)
    leases: list[Row] = field(default_factory=list)
    rent_ledger: list[Row] = field(default_factory=list)
    vendors: list[Row] = field(default_factory=list)
    work_orders: list[Row] = field(default_factory=list)
    operating_expenses: list[Row] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)

    TABLE_ORDER = (
        "properties", "units", "tenants", "vendors", "leases", "rent_ledger", "work_orders",
        "operating_expenses",
    )  # fmt: skip


def _money(x: float) -> float:
    return round(float(x), 2)


class _Gen:
    def __init__(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)
        self.fake = Faker("en_US")
        self.fake.seed_instance(seed)
        self.ds = Dataset(meta={"seed": str(seed), "as_of": AS_OF.isoformat()})
        self.ids: dict[str, int] = {}

    def next_id(self, table: str) -> int:
        self.ids[table] = self.ids.get(table, 0) + 1
        return self.ids[table]

    # ---------------------------------------------------------------- reference data
    def properties(self) -> None:
        rng = self.rng
        sizes = rng.integers(70, 230, N_PROPERTIES).astype(float)
        sizes = np.floor(sizes / sizes.sum() * N_UNITS).astype(int)
        sizes[0] += N_UNITS - sizes.sum()  # exact total
        trees = list(rng.permutation(TREES))
        trees.remove("Maple")
        names = ["Maple Court"] + [f"{t} {rng.choice(SUFFIXES)}" for t in trees[: N_PROPERTIES - 1]]
        self.prop_traits: dict[int, dict[str, float]] = {}
        for i, (name, n_units) in enumerate(zip(names, sizes, strict=True)):
            pid = self.next_id("properties")
            ptype = str(rng.choice(["garden", "midrise", "highrise"], p=[0.5, 0.35, 0.15]))
            year_built = int(rng.integers(1972, 2021))
            self.ds.properties.append(
                {
                    "id": pid,
                    "name": name,
                    "city": self.fake.city(),
                    "state": self.fake.state_abbr(include_territories=False),
                    "property_type": ptype,
                    "year_built": year_built,
                    "acquired_on": date(int(rng.integers(2012, 2022)), int(rng.integers(1, 13)), 1),
                }
            )
            self.prop_traits[pid] = {
                "n_units": int(n_units),
                "rent_level": float(rng.uniform(0.82, 1.38)),
                "mgmt": float(rng.uniform(0.8, 1.3)),  # >1 = slower maintenance response
                "desirability": float(rng.uniform(0.85, 1.1)),
                "age_factor": 1.0 + max(0, 2010 - year_built) / 60,
                "index": i,
            }

    def vendors(self) -> None:
        self.vendors_by_trade: dict[str, list[int]] = {}
        self.vendor_traits: dict[int, dict[str, float]] = {}
        used: set[str] = set()
        for trade, n in VENDOR_COUNTS.items():
            for _ in range(n):
                name = ""
                while not name or name in used:
                    word = self.rng.choice(TRADE_WORDS[trade])
                    suffix = self.rng.choice(["LLC", "Inc", "Co", "Group"])
                    name = f"{self.fake.last_name()} {word} {suffix}"
                used.add(name)
                vid = self.next_id("vendors")
                rate = {"hvac": 115, "plumbing": 105, "electrical": 110}.get(trade, 80)
                self.ds.vendors.append(
                    {
                        "id": vid,
                        "name": name,
                        "trade": trade,
                        "phone": self.fake.phone_number(),
                        "hourly_rate": _money(rate * self.rng.uniform(0.85, 1.25)),
                    }
                )
                self.vendors_by_trade.setdefault(trade, []).append(vid)
                self.vendor_traits[vid] = {
                    "speed": float(self.rng.lognormal(0, 0.3)),
                    "rate": self.ds.vendors[-1]["hourly_rate"],
                }
        # each property contracts a primary + backup vendor per trade
        self.prop_vendors: dict[tuple[int, str], list[int]] = {}
        for p in self.ds.properties:
            for trade, vids in self.vendors_by_trade.items():
                pick = self.rng.choice(vids, size=2, replace=False)
                self.prop_vendors[(p["id"], trade)] = [int(v) for v in pick]

    def units(self) -> None:
        types = list(UNIT_TYPES)
        shares = [UNIT_TYPES[t][0] for t in types]
        self.unit_traits: dict[int, dict[str, Any]] = {}
        for p in self.ds.properties:
            tr = self.prop_traits[p["id"]]
            per_floor = int(self.rng.integers(8, 16))
            for i in range(int(tr["n_units"])):
                uid = self.next_id("units")
                ut = str(self.rng.choice(types, p=shares))
                _, beds, baths, sqft, base = UNIT_TYPES[ut]
                market = base * tr["rent_level"] * self.rng.uniform(0.95, 1.05)
                self.ds.units.append(
                    {
                        "id": uid,
                        "property_id": p["id"],
                        "unit_number": str(100 * (1 + i // per_floor) + i % per_floor + 1),
                        "unit_type": ut,
                        "bedrooms": beds,
                        "bathrooms": baths,
                        "sqft": int(sqft * self.rng.uniform(0.88, 1.12)),
                        "market_rent": _money(market),
                    }
                )
                self.unit_traits[uid] = {"market_asof": market, "property_id": p["id"]}

    @staticmethod
    def market_rent(market_asof: float, d: date) -> float:
        years = (d - AS_OF).days / 365.25
        season = 1 + 0.02 * math.cos(2 * math.pi * (d.month - 7) / 12)  # peaks in July
        return market_asof * (1 + MARKET_GROWTH) ** years * season

    def new_tenant(self) -> tuple[int, float]:
        tid = self.next_id("tenants")
        reliability = float(self.rng.beta(5, 1.6))  # latent; never stored
        first, last = self.fake.first_name(), self.fake.last_name()
        self.ds.tenants.append(
            {
                "id": tid,
                "first_name": first,
                "last_name": last,
                "email": f"{first}.{last}{tid}@example.com".lower(),
                "phone": self.fake.phone_number(),
                "credit_score": int(
                    np.clip(560 + 240 * reliability + self.rng.normal(0, 35), 500, 850)
                ),
            }
        )
        return tid, reliability

    # ---------------------------------------------------------------- maintenance
    def spikes(self) -> None:
        """Property-wide maintenance spikes (e.g. chiller failure in a heat wave)."""
        self.spike: dict[tuple[int, int, str], float] = {
            (1, month_index(date(2026, 7, 1)), "hvac"): 5.0
        }
        for _ in range(3):
            pid = int(self.rng.integers(2, N_PROPERTIES + 1))
            m = int(self.rng.integers(0, N_MONTHS))
            cat = str(self.rng.choice(["plumbing", "hvac", "electrical"]))
            self.spike[(pid, m, cat)] = float(self.rng.uniform(3.5, 6.0))

    def work_order(
        self,
        pid: int,
        uid: int | None,
        category: str,
        opened: datetime,
        priority: str | None = None,
    ) -> Row:
        rng = self.rng
        trade = WO_CATEGORIES[category][2] if category != "turnover" else "general"
        m = month_index(opened.date())
        spike = self.spike.get((pid, m, category), 1.0)
        if priority is None:
            harsh = category == "hvac" and opened.month in (1, 2, 6, 7, 8, 12)
            p = [0.18, 0.32, 0.40, 0.10] if harsh or spike > 1 else [0.07, 0.20, 0.50, 0.23]
            priority = str(rng.choice(PRIORITIES, p=p))
        options = self.prop_vendors[(pid, trade)]
        vid = options[0] if rng.random() < 0.7 else options[1]
        load = 1.7 if spike > 1 else 1.0  # vendors overloaded during spikes
        median = (
            SLA_HOURS[priority] * 0.55 * self.vendor_traits[vid]["speed"]
            * self.prop_traits[pid]["mgmt"] * load
        )  # fmt: skip
        hours = median * rng.lognormal(0, 0.6)
        completed: datetime | None = opened + timedelta(hours=float(hours))
        status = "completed"
        if rng.random() < 0.03:
            status, completed = "cancelled", None
        elif completed is not None and completed.date() > AS_OF:
            status, completed = "open", None
        cost = None
        if status == "completed":
            on_site = 1 + rng.gamma(2, 1)
            parts = rng.lognormal(4.2 if category == "hvac" else 3.6, 0.7)
            premium = 1.5 if priority == "emergency" else 1.0
            cost = _money((self.vendor_traits[vid]["rate"] * on_site + parts) * premium)
        desc = str(rng.choice(DESCRIPTIONS[category]))
        if "{n}" in desc:
            desc = desc.format(n=int(rng.integers(84, 92)) if opened.month in (5, 6, 7, 8, 9)
                               else int(rng.integers(52, 60)))  # fmt: skip
        row = {
            "id": self.next_id("work_orders"),
            "property_id": pid,
            "unit_id": uid,
            "vendor_id": vid,
            "category": category,
            "priority": priority,
            "status": status,
            "opened_at": opened,
            "completed_at": completed,
            "cost": cost,
            "description": desc,
        }
        self.ds.work_orders.append(row)
        return row

    def random_open_time(self, period: date) -> datetime:
        days = (add_months(period, 1) - period).days
        d = period + timedelta(days=int(self.rng.integers(0, days)))
        return datetime.combine(
            d, time(int(self.rng.integers(7, 21)), int(self.rng.integers(0, 60)))
        )

    def unit_work_orders(self, pid: int, uid: int | None, scale: float = 1.0) -> list[Row]:
        out = []
        age = self.prop_traits[pid]["age_factor"]
        for m, period in enumerate(PERIODS):
            for cat, (rate, seasonal, _) in WO_CATEGORIES.items():
                lam = (
                    rate
                    * age
                    * seasonal.get(period.month, 1.0)
                    * self.spike.get((pid, m, cat), 1.0)
                )
                for _ in range(self.rng.poisson(lam * scale)):
                    opened = self.random_open_time(period)
                    if opened.date() <= AS_OF:
                        out.append(self.work_order(pid, uid, cat, opened))
        return out

    # ---------------------------------------------------------------- tenancy
    def add_lease(
        self, uid: int, tid: int, start: date, months: int, rent: float, renewal_of: int | None
    ) -> Row:
        row = {
            "id": self.next_id("leases"),
            "unit_id": uid,
            "tenant_id": tid,
            "start_date": start,
            "end_date": add_months(start, months),
            "move_out_date": None,
            "monthly_rent": _money(rent),
            "security_deposit": _money(rent),
            "status": "active",
            "renewal_of_lease_id": renewal_of,
        }
        self.ds.leases.append(row)
        return row

    def simulate_unit(self, unit: Row) -> None:
        rng, uid, pid = self.rng, unit["id"], unit["property_id"]
        market_asof = self.unit_traits[uid]["market_asof"]
        unit_wos = self.unit_work_orders(pid, uid)
        breaches = [
            w["opened_at"].date()
            for w in unit_wos
            if w["completed_at"] is None
            and w["status"] == "open"
            or w["completed_at"] is not None
            and (w["completed_at"] - w["opened_at"]).total_seconds() / 3600
            > SLA_HOURS[w["priority"]]
        ]
        wo_dates = [w["opened_at"].date() for w in unit_wos]
        ledger: dict[date, Row] = {}  # period -> ledger row, for the current tenancy
        desirability = self.prop_traits[pid]["desirability"]

        # --- initial state at window start
        lease: Row | None = None
        tenant_rel = 0.0
        tenant_move_in = WINDOW_START
        if rng.random() < 0.94:
            tid, tenant_rel = self.new_tenant()
            tenure_months = int(rng.integers(1, 72))
            tenant_move_in = add_months(WINDOW_START, -tenure_months)
            start, prev = tenant_move_in, None
            while True:  # 12-month chain up to the lease that covers WINDOW_START
                rent = self.market_rent(market_asof, start) * rng.uniform(0.96, 1.02)
                lease = self.add_lease(uid, tid, start, 12, rent, prev)
                if lease["end_date"] > WINDOW_START:
                    break
                lease["status"] = "expired"
                prev, start = lease["id"], lease["end_date"]
        vacant_since: date | None = None if lease else WINDOW_START

        hardship = False
        unpaid_streak = 0
        for period in PERIODS:
            # ---- lease end / renewal decision at the first of the month
            if lease is not None and lease["end_date"] == period:
                renewed = self.decide_renewal(lease, ledger, wo_dates, breaches, tenant_rel,
                                              tenant_move_in, market_asof)  # fmt: skip
                lease["status"] = "expired"
                if renewed is not None:
                    lease = renewed
                else:
                    lease["move_out_date"] = period
                    if rng.random() < 0.7:  # balance settled at move-out (e.g. from deposit)
                        self.catch_up(ledger, add_months(period, -1))
                    self.turnover(pid, uid, period)
                    lease, vacant_since, ledger, hardship, unpaid_streak = (
                        None,
                        period,
                        {},
                        False,
                        0,
                    )
            # ---- vacancy: try to lease up (seasonal demand)
            if lease is None:
                assert vacant_since is not None
                if period > vacant_since:  # at least one month make-ready
                    fill = {5: 0.72, 6: 0.75, 7: 0.75, 8: 0.7, 11: 0.4, 12: 0.35, 1: 0.38, 2: 0.42}
                    if rng.random() < fill.get(period.month, 0.55) * desirability:
                        tid, tenant_rel = self.new_tenant()
                        tenant_move_in = period
                        months = int(rng.choice([12, 6, 18], p=[0.8, 0.1, 0.1]))
                        rent = self.market_rent(market_asof, period) * rng.uniform(0.97, 1.03)
                        lease = self.add_lease(uid, tid, period, months, rent, None)
                        vacant_since = None
                if lease is None:
                    continue
            # ---- bill and (maybe) collect rent
            row = self.bill(lease, period, tenant_rel, hardship)
            ledger[period] = row
            if row["paid_on"] is None:
                unpaid_streak += 1
            else:
                unpaid_streak = 0
            # hardship episodes create 60/90+ day delinquency
            if hardship:
                if rng.random() < 0.35:
                    hardship = False
                    if rng.random() < 0.55:
                        self.catch_up(ledger, period)
                        unpaid_streak = 0
            elif rng.random() < 0.002 + 0.04 * (1 - tenant_rel) ** 2:
                hardship = True
            elif rng.random() < 0.5:  # pay down older balances when not in hardship
                self.catch_up(ledger, period)
            # eviction after 3 consecutive unpaid months
            if unpaid_streak >= 3:
                lease["status"] = "terminated"
                lease["move_out_date"] = add_months(period, 1)
                self.turnover(pid, uid, add_months(period, 1))
                lease, vacant_since, ledger, hardship, unpaid_streak = (
                    None, add_months(period, 1), {}, False, 0,
                )  # fmt: skip

        if lease is not None and lease["end_date"] <= AS_OF:
            lease["status"] = "expired"

    def bill(self, lease: Row, period: date, rel: float, hardship: bool) -> Row:
        rng = self.rng
        due = lease["monthly_rent"]
        paid_on: date | None
        amount_paid = 0.0
        if hardship:
            paid_on = None
        elif rng.random() < 0.01 + 0.05 * (1 - rel) ** 2:
            # missed due date: most are paid a month or so later, the rest stay outstanding
            if rng.random() < 0.7:
                paid_on = period + timedelta(days=int(rng.integers(25, 56)))
                amount_paid = due
            else:
                paid_on = None
        else:
            on_time = 0.55 + 0.42 * rel - (0.10 if period.month in (12, 1) else 0.0)
            if rng.random() < on_time:
                paid_on = period + timedelta(days=int(rng.integers(0, 5)))  # within grace
            else:
                paid_on = period + timedelta(days=5 + 1 + int(rng.poisson(2 + 14 * (1 - rel))))
            amount_paid = due if rng.random() > 0.05 * (1 - rel) else _money(due * 0.5)
        if paid_on is not None and paid_on > AS_OF:  # hasn't happened yet as of the data date
            paid_on, amount_paid = None, 0.0
        row = {
            "id": self.next_id("rent_ledger"),
            "lease_id": lease["id"],
            "period": period,
            "due_date": period,
            "amount_due": due,
            "amount_paid": _money(amount_paid),
            "paid_on": paid_on,
        }
        self.ds.rent_ledger.append(row)
        return row

    def catch_up(self, ledger: dict[date, Row], period: date) -> None:
        pay_day = period + timedelta(days=int(self.rng.integers(5, 25)))
        if pay_day > AS_OF:
            return
        for row in ledger.values():
            if row["amount_paid"] < row["amount_due"]:
                row["amount_paid"], row["paid_on"] = row["amount_due"], pay_day

    def decide_renewal(
        self, lease: Row, ledger: dict[date, Row], wo_dates: list[date], breaches: list[date],
        rel: float, move_in: date, market_asof: float,
    ) -> Row | None:  # fmt: skip
        """Return the renewal lease, or None if the tenant moves out."""
        rng, end = self.rng, lease["end_date"]
        lo, hi = add_months(end, -8), add_months(end, -2)  # signals visible at notice time
        recent = [r for p, r in ledger.items() if lo <= p < hi]
        late = sum(
            1 for r in recent if r["paid_on"] is None or (r["paid_on"] - r["due_date"]).days > 5
        )
        late_frac = late / len(recent) if recent else 0.0
        n_breach = sum(1 for d in breaches if lo <= d < hi)
        n_wo = sum(1 for d in wo_dates if lo <= d < hi)
        owed = sum(r["amount_due"] - r["amount_paid"] for r in ledger.values())
        if owed > lease["monthly_rent"]:  # landlord won't renew tenants in arrears
            return None
        market = self.market_rent(market_asof, end)
        offer = min(lease["monthly_rent"] * rng.uniform(1.02, 1.07), market * 1.03)
        gap = offer / market - 1
        tenure = (end - move_in).days / 365.25
        logit = (
            0.55 - 3.0 * late_frac - 0.45 * n_breach - 0.08 * n_wo + 0.18 * min(tenure, 6)
            - 6.0 * gap + (-0.35 if end.month in (5, 6, 7, 8) else 0.0) + 1.0 * (rel - 0.76)
        )  # fmt: skip
        if rng.random() >= 1 / (1 + math.exp(-logit)):
            return None
        months = int(rng.choice([12, 6], p=[0.85, 0.15]))
        return self.add_lease(lease["unit_id"], lease["tenant_id"], end, months, offer, lease["id"])

    def turnover(self, pid: int, uid: int, move_out: date) -> None:
        if move_out <= AS_OF:
            self.work_order(pid, uid, "turnover", datetime.combine(move_out, time(9)), "normal")

    # ---------------------------------------------------------------- finance
    def operating_expenses(self) -> None:
        lease_prop = {}
        unit_prop = {u["id"]: u["property_id"] for u in self.ds.units}
        for lease in self.ds.leases:
            lease_prop[lease["id"]] = unit_prop[lease["unit_id"]]
        collected: dict[tuple[int, date], float] = {}
        for r in self.ds.rent_ledger:
            if r["paid_on"] is not None:
                key = (lease_prop[r["lease_id"]], r["paid_on"].replace(day=1))
                collected[key] = collected.get(key, 0.0) + r["amount_paid"]
        for p in self.ds.properties:
            n = self.prop_traits[p["id"]]["n_units"]
            for period in PERIODS:
                weather = 1 + 0.35 * abs(math.cos(2 * math.pi * (period.month - 1) / 12))
                lines = {
                    "property_tax": n * 175,
                    "insurance": n * 42,
                    "utilities": n * 58 * weather,
                    "payroll": n * 68,
                    "marketing": n * 7,
                    "management_fee": 0.04 * collected.get((p["id"], period), 0.0),
                }
                for cat, amount in lines.items():
                    self.ds.operating_expenses.append(
                        {
                            "id": self.next_id("operating_expenses"),
                            "property_id": p["id"],
                            "period": period,
                            "category": cat,
                            "amount": _money(amount * self.rng.uniform(0.97, 1.03)),
                        }
                    )

    def run(self) -> Dataset:
        self.properties()
        self.vendors()
        self.units()
        self.spikes()
        for unit in self.ds.units:
            self.simulate_unit(unit)
        for p in self.ds.properties:  # common-area work orders (no unit)
            self.unit_work_orders(p["id"], None, scale=self.prop_traits[p["id"]]["n_units"] * 0.02)
        self.operating_expenses()
        self.ds.meta.update({t: str(len(getattr(self.ds, t))) for t in Dataset.TABLE_ORDER})
        return self.ds


def generate(seed: int = 42) -> Dataset:
    return _Gen(seed).run()
